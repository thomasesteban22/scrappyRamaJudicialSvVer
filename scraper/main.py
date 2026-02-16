# scraper/main.py
import os
import csv
import smtplib
import time
import threading
import itertools
import sys
from queue import Queue
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Importar nuestro logger primero
from .logger import log

# Configuración de directorios debug (igual que antes)
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# --- IMPORTS DE TU PROYECTO ---
from .config import (
    OUTPUT_DIR,
    NUM_THREADS,
    PDF_PATH,
    EMAIL_USER,
    EMAIL_PASS,
    SCHEDULE_TIME,
    ENV,
    DEBUG_SCRAPER,
    DIAS_BUSQUEDA
)
from .loader import cargar_procesos
from .browser import new_chrome_driver
from .worker import worker_task
import scraper.worker as worker
from .reporter import generar_pdf


# ---------------- FUNCIONES ---------------- #

def setup_environment():
    """Configura entorno para evitar detección"""
    # Limpiar variables de entorno de Selenium
    os.environ.pop('SE_DRIVER_PATH', None)
    os.environ.pop('SE_BINARY_PATH', None)

    # Verificar Xvfb
    display = os.environ.get('DISPLAY', ':99')
    os.environ['DISPLAY'] = display

    # Log de entorno (solo a archivo)
    log.debug(f"DISPLAY configurado: {display}")
    log.debug(f"Entorno Python: {sys.version}")


def save_debug_page(driver, step_name="step", numero="unknown"):
    """Guarda screenshot y HTML para inspección (solo logs a archivo)."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss_path = os.path.join(SCREENSHOT_DIR, f"{numero}_{step_name}_{timestamp}.png")
    html_path = os.path.join(HTML_DIR, f"{numero}_{step_name}_{timestamp}.html")
    try:
        driver.save_screenshot(ss_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log.debug(f"Captura guardada: {step_name} para {numero}")
    except Exception as e:
        log.error(f"Error guardando debug: {e}")


def probar_procesos(lista_procesos):
    """
    Ejecuta worker_task para una lista de procesos.
    Útil para modo DEBUG con múltiples procesos.
    """
    import itertools, threading
    from .browser import new_chrome_driver, wait_for_tor_circuit
    from .worker import worker_task
    import scraper.worker as worker

    log.titulo(f"MODO PRUEBA - {len(lista_procesos)} PROCESOS")

    # ========== PASO 1: ESPERAR A QUE TOR ESTÉ LISTO ==========
    log.progreso("Verificando TOR...")
    if not wait_for_tor_circuit(timeout=180):
        log.error("❌ TOR no está listo después de 180 segundos. Abortando prueba.")
        return

    # ========== PASO 2: TOR LISTO, INICIAR DRIVER ==========
    log.exito("TOR listo. Iniciando driver...")

    # Inicialización
    results, actes, errors = [], [], []
    lock = threading.Lock()
    worker.process_counter = itertools.count(1)
    worker.TOTAL_PROCESSES = len(lista_procesos)

    # Crear driver
    driver = new_chrome_driver(0)

    try:
        log.progreso(f"Ejecutando {len(lista_procesos)} procesos...")

        for i, numero in enumerate(lista_procesos, 1):
            log.separador()
            log.progreso(f"[{i}/{len(lista_procesos)}] {numero}")

            try:
                save_debug_page(driver, f"inicio_{i}", numero)
                worker_task(numero, driver, results, actes, errors, lock)
                save_debug_page(driver, f"fin_{i}", numero)
                log.exito(f"Proceso {i} completado")
            except Exception as e:
                log.error(f"Error en proceso {i}: {e}")
                save_debug_page(driver, f"error_{i}", numero)

            # Pequeña pausa entre procesos
            time.sleep(2)

        log.titulo("RESULTADOS FINALES")
        log.resultado(f"Total procesos: {len(lista_procesos)}")
        log.resultado(f"Actuaciones encontradas: {len(actes)}")
        log.resultado(f"Errores: {len(errors)}")

        if actes:
            log.progreso("Primeras 10 actuaciones:")
            for i, act in enumerate(actes[:10], 1):
                log.proceso(f"  {i}. {act[1]} - {act[2][:80]}...")

        if errors:
            log.advertencia("Procesos con error:")
            for num, msg in errors:
                log.advertencia(f"  • {num}: {msg[:100]}")

    except Exception as e:
        log.error(f"Error general en prueba: {e}")
    finally:
        driver.quit()
        log.exito("Driver cerrado")


def exportar_csv(actes, start_ts):
    """Exporta las actuaciones a CSV."""
    fecha_registro = date.fromtimestamp(start_ts).isoformat()
    csv_path = os.path.join(OUTPUT_DIR, "actuaciones.csv")
    headers = [
        "idInterno",
        "quienRegistro",
        "fechaRegistro",
        "fechaEstado",
        "etapa",
        "actuacion",
        "observacion"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for numero, fecha, actu, anota, _url in actes:
            writer.writerow([
                numero,
                "Sistema",
                fecha_registro,
                fecha,
                "",
                actu,
                anota
            ])
    log.resultado(f"CSV generado: {csv_path}")


def send_report_email():
    """Envía el reporte por correo."""
    now = datetime.now()
    fecha_str = now.strftime("%A %d-%m-%Y a las %I:%M %p").capitalize()

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(EMAIL_USER, EMAIL_PASS)

        msg = MIMEMultipart()
        msg["Subject"] = f"Reporte Diario de Actuaciones - {fecha_str}"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER

        cuerpo = f"Adjunto encontrarás el reporte de actuaciones generado el {fecha_str}."
        msg.attach(MIMEText(cuerpo, "plain"))

        if os.path.exists(PDF_PATH):
            with open(PDF_PATH, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(PDF_PATH))
                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(PDF_PATH))
                msg.attach(part)

        smtp.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
        smtp.quit()
        log.exito("Correo enviado")

    except Exception as e:
        log.error(f"Error enviando correo: {e}")


def ejecutar_ciclo():
    """Ejecuta un ciclo completo de scraping, reporte, CSV y correo."""

    log.titulo("INICIANDO CICLO DE SCRAPING")
    log.resultado(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    log.resultado(f"🎯 Período: últimos {DIAS_BUSQUEDA} días")
    log.resultado(f"🔄 Hilos: {NUM_THREADS}")
    log.separador()

    # Reiniciar contador de procesos
    worker.process_counter = itertools.count(1)

    start_ts = time.time()

    # Borro PDF y CSV antiguos
    if os.path.exists(PDF_PATH):
        os.remove(PDF_PATH)
    csv_old = os.path.join(OUTPUT_DIR, "actuaciones.csv")
    if os.path.exists(csv_old):
        os.remove(csv_old)

    # Carga de procesos
    procesos = cargar_procesos()
    TOTAL = len(procesos)
    worker.TOTAL_PROCESSES = TOTAL

    log.progreso(f"Procesos a escanear: {TOTAL}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Preparar cola y threads
    q = Queue()
    for num in procesos:
        q.put(num)
    for _ in range(NUM_THREADS):
        q.put(None)

    drivers = [new_chrome_driver(i) for i in range(NUM_THREADS)]
    results, actes, errors = [], [], []
    lock = threading.Lock()
    threads = []

    def loop(driver):
        while True:
            numero = q.get()
            q.task_done()
            if numero is None:
                break
            for intento in range(10):
                try:
                    worker_task(numero, driver, results, actes, errors, lock)
                    break
                except Exception as exc:
                    log.advertencia(f"{numero}: intento {intento + 1}/10 fallido")
                    if intento == 9:
                        with lock:
                            errors.append((numero, str(exc)[:200]))
        driver.quit()

    for drv in drivers:
        t = threading.Thread(target=loop, args=(drv,), daemon=True)
        t.start()
        threads.append(t)

    q.join()
    for t in threads:
        t.join()

    # Reportes y envío
    generar_pdf(TOTAL, actes, errors, start_ts, time.time())
    exportar_csv(actes, start_ts)

    if ENV == 'production':
        try:
            send_report_email()
        except Exception as e:
            log.error(f"Error enviando correo: {e}")

    # Resumen
    err = len(errors)
    esc = TOTAL - err

    log.titulo("RESUMEN DEL CICLO")
    log.resultado(f"✅ Escaneados: {esc}")
    log.resultado(f"❌ Errores: {err}")
    log.resultado(f"📋 Actuaciones: {len(actes)}")

    if err and DEBUG_SCRAPER:
        log.advertencia("Procesos con error:")
        for num, msg in errors[:5]:  # Solo primeros 5 en consola
            log.advertencia(f"  • {num}: {msg[:100]}")

    log.separador()


def log_ip_salida():
    """Obtiene y loguea la IP de salida."""
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        log.info(f"IP Saliente: {ip}")
    except Exception as e:
        log.debug(f"No se pudo obtener IP de salida: {e}")


# ---------------- MAIN ---------------- #

def main():
    """Punto de entrada principal."""

    log.titulo("SCRAPER RAMA JUDICIAL")
    log.resultado(f"🌍 Entorno: {ENV}")
    log.resultado(f"🔧 Debug: {'ACTIVADO' if DEBUG_SCRAPER else 'DESACTIVADO'}")
    log.resultado(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log.separador()

    # Configurar entorno
    setup_environment()

    # Log de IP de salida
    log_ip_salida()

    if DEBUG_SCRAPER:
        # Modo prueba: lista de procesos
        procesos_prueba = [
            "08296408900120190029100",
            "11001310300120080020700",
            "11001310300120080023700",
            "11001310300120130071600",
            "11001310300120150030300"
        ]
        probar_procesos(procesos_prueba)

    else:
        # Modo producción - scheduler
        log.progreso(f"Scheduler iniciado. Próxima ejecución: {SCHEDULE_TIME}")

        bogota_tz = ZoneInfo("America/Bogota")
        hh, mm = map(int, SCHEDULE_TIME.split(":"))

        while True:
            now = datetime.now(bogota_tz)
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_sec = (target - now).total_seconds()

            # Conteo regresivo con avisos cada hora
            remaining = wait_sec
            while remaining > 0:
                if remaining > 3600:
                    hrs = int(remaining // 3600)
                    log.progreso(f"Faltan {hrs} hora(s) para próxima ejecución")
                    time.sleep(3600)
                    remaining -= 3600
                else:
                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    if mins > 0 or secs > 0:
                        log.progreso(f"Faltan {mins} min {secs} seg")
                    time.sleep(remaining)
                    remaining = 0

            ejecutar_ciclo()


if __name__ == "__main__":
    main()