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

from .logger import log
from .config import (
    OUTPUT_DIR, NUM_THREADS, PDF_PATH,
    EMAIL_USER, EMAIL_PASS, SCHEDULE_TIME,
    ENV, DEBUG_SCRAPER, DIAS_BUSQUEDA
)
from .loader import cargar_procesos
from .worker import worker_task
from .session_manager import get_session
import scraper.worker as worker
from .reporter import generar_pdf
from .api_client import enviar_actuaciones
from . import magna_client


# ─── Config helpers ────────────────────────────────────────────────────
def get_runtime_config():
    """Lee la config actual desde Magna; cae a valores del .env si falla."""
    cfg = magna_client.get_config()
    return {
        "dias_busqueda": int(cfg.get("dias_busqueda") or DIAS_BUSQUEDA),
        "schedule_time": cfg.get("schedule_time") or SCHEDULE_TIME,
        "num_threads":   int(cfg.get("num_threads") or NUM_THREADS),
        "activo":        bool(cfg.get("activo", 1)),
    }


def setup_environment():
    log.debug(f"Python: {sys.version}")


def log_ip_salida():
    try:
        import requests
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        log.info(f"IP de salida: {ip}")
    except Exception as e:
        log.debug(f"No se pudo obtener IP: {e}")


def exportar_csv(actes, start_ts):
    fecha_registro = date.fromtimestamp(start_ts).isoformat()
    csv_path = os.path.join(OUTPUT_DIR, "actuaciones.csv")
    headers = ["idInterno", "quienRegistro", "fechaRegistro",
               "fechaEstado", "etapa", "actuacion", "observacion"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for numero, fecha, actu, anota, _url, _fecha_inicial in actes:
            writer.writerow([numero, "Sistema", fecha_registro, fecha, "", actu, anota])
    log.resultado(f"CSV generado: {csv_path}")


def send_report_email():
    now = datetime.now()
    fecha_str = now.strftime("%A %d-%m-%Y a las %I:%M %p").capitalize()
    try:
        smtp = smtplib.SMTP("smtp.gmail.com", 587)
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        msg = MIMEMultipart()
        msg["Subject"] = f"Reporte Diario de Actuaciones - {fecha_str}"
        msg["From"]    = EMAIL_USER
        msg["To"]      = EMAIL_USER
        msg.attach(MIMEText(
            f"Adjunto encontraras el reporte de actuaciones generado el {fecha_str}.",
            "plain"
        ))
        if os.path.exists(PDF_PATH):
            with open(PDF_PATH, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(PDF_PATH))
                part.add_header('Content-Disposition', 'attachment',
                                filename=os.path.basename(PDF_PATH))
                msg.attach(part)
        smtp.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
        smtp.quit()
        log.exito("Correo enviado")
    except Exception as e:
        log.error(f"Error enviando correo: {e}")


# ─── Ejecucion del ciclo ──────────────────────────────────────────────
def ejecutar_ciclo(tipo="automatica", iniciado_por="scheduler", ejec_id_externo=None):
    """
    Ejecuta un ciclo de scraping.

    Args:
        tipo: 'automatica' o 'manual'
        iniciado_por: nombre del usuario o 'scheduler'
        ejec_id_externo: si se pasa, se usa esa ejecucion (ya creada por la API).
                         Si es None, se crea una nueva. Esto evita duplicar
                         ejecuciones cuando el trigger viene del panel web.
    """
    cfg = get_runtime_config()
    dias_busqueda = cfg["dias_busqueda"]
    num_threads   = cfg["num_threads"]

    # Usar ejecucion existente o crear una nueva
    if ejec_id_externo:
        ejec_id = ejec_id_externo
        log.progreso(f"Ejecucion #{ejec_id} (creada por API, {tipo}, por {iniciado_por})")
    else:
        ejec_id = magna_client.crear_ejecucion(tipo=tipo, iniciado_por=iniciado_por)
        if ejec_id:
            log.progreso(f"Ejecucion #{ejec_id} registrada en Magna ({tipo}, por {iniciado_por})")

    log.titulo("INICIANDO CICLO DE SCRAPING")
    log.resultado(f"Fecha:   {datetime.now().strftime('%d/%m/%Y')}")
    log.resultado(f"Periodo: ultimos {dias_busqueda} dias")
    log.resultado(f"Hilos:   {num_threads}")
    log.separador()

    start_ts = time.time()
    worker.process_counter = itertools.count(1)

    # Pasar dias_busqueda al worker via env (lo lee config.py)
    os.environ["DIAS_BUSQUEDA"] = str(dias_busqueda)

    for path in [PDF_PATH, os.path.join(OUTPUT_DIR, "actuaciones.csv")]:
        if os.path.exists(path):
            os.remove(path)

    procesos = cargar_procesos()
    TOTAL = len(procesos)
    worker.TOTAL_PROCESSES = TOTAL
    log.progreso(f"Procesos a escanear: {TOTAL}")

    if TOTAL == 0:
        log.advertencia("Sin procesos para escanear, abortando")
        magna_client.actualizar_ejecucion(
            ejec_id, estado="completada",
            procesos_total=0, procesos_exitosos=0, procesos_error=0,
            actuaciones_encontradas=0, actuaciones_insertadas=0, actuaciones_duplicadas=0,
        )
        return

    log.progreso("Obteniendo sesion...")
    get_session()
    log.exito("Sesion lista, iniciando threads")

    q = Queue()
    for num in procesos:
        q.put(num)
    for _ in range(num_threads):
        q.put(None)

    results, actes, errors = [], [], []
    lock = threading.Lock()

    def loop():
        while True:
            numero = q.get()
            q.task_done()
            if numero is None:
                break
            for intento in range(10):
                try:
                    worker_task(numero, None, results, actes, errors, lock)
                    break
                except Exception as exc:
                    log.advertencia(f"{numero}: intento {intento+1}/10 - {exc}")
                    if intento == 9:
                        with lock:
                            errors.append((numero, str(exc)[:200]))

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=loop, daemon=True)
        t.start()
        threads.append(t)

    q.join()
    for t in threads:
        t.join()

    generar_pdf(TOTAL, actes, errors, start_ts, time.time())

    # Enviar a Magna y capturar resultado (con execution_id para guardar detalles)
    resultado_envio = enviar_actuaciones(actes, execution_id=ejec_id) or {}
    insertadas = resultado_envio.get("insertadas", 0)
    duplicadas = resultado_envio.get("duplicadas", 0)

    exportar_csv(actes, start_ts)

    if ENV == 'production':
        try:
            send_report_email()
        except Exception as e:
            log.error(f"Error enviando correo: {e}")

    log.titulo("RESUMEN DEL CICLO")
    log.resultado(f"Escaneados:  {TOTAL - len(errors)}")
    log.resultado(f"Errores:     {len(errors)}")
    log.resultado(f"Actuaciones: {len(actes)}")
    log.resultado(f"Insertadas:  {insertadas}")
    log.resultado(f"Duplicadas:  {duplicadas}")
    log.separador()

    # Cerrar ejecucion en Magna
    magna_client.actualizar_ejecucion(
        ejec_id,
        estado="completada",
        procesos_total=TOTAL,
        procesos_exitosos=TOTAL - len(errors),
        procesos_error=len(errors),
        actuaciones_encontradas=len(actes),
        actuaciones_insertadas=insertadas,
        actuaciones_duplicadas=duplicadas,
    )


def probar_procesos(lista_procesos):
    log.titulo(f"MODO PRUEBA - {len(lista_procesos)} PROCESOS")
    results, actes, errors = [], [], []
    lock = threading.Lock()
    worker.process_counter = itertools.count(1)
    worker.TOTAL_PROCESSES = len(lista_procesos)

    log.progreso("Obteniendo sesion...")
    get_session()

    for i, numero in enumerate(lista_procesos, 1):
        log.separador()
        try:
            worker_task(numero, None, results, actes, errors, lock)
            log.exito(f"Proceso {i} completado")
        except Exception as e:
            log.error(f"Error en proceso {i}: {e}")
        time.sleep(1)

    log.titulo("RESULTADOS")
    log.resultado(f"Procesos:     {len(lista_procesos)}")
    log.resultado(f"Actuaciones:  {len(actes)}")
    log.resultado(f"Errores:      {len(errors)}")


# ─── Trigger de ejecucion manual ─────────────────────────────────────
TRIGGER_FILE = "/app/data/.run_now"


def chequear_trigger_manual():
    """
    Si existe el archivo trigger, lo borra y devuelve (True, usuario, ejec_id).

    Formato del trigger file:
      - "usuario|ejec_id"  -> cuando viene del FastAPI (ejecucion ya creada)
      - "usuario"          -> formato viejo, sin ejec_id (compat)
      - vacio              -> usa "manual" sin ejec_id
    """
    if not os.path.exists(TRIGGER_FILE):
        return False, "", None

    usuario = "manual"
    ejec_id = None

    try:
        with open(TRIGGER_FILE, "r") as f:
            contenido = f.read().strip()

        if contenido:
            if "|" in contenido:
                # Formato nuevo: "usuario|ejec_id"
                partes = contenido.split("|", 1)
                usuario = partes[0] or "manual"
                try:
                    ejec_id = int(partes[1])
                except (ValueError, IndexError):
                    ejec_id = None
            else:
                # Formato viejo: solo el usuario
                usuario = contenido
    except Exception:
        usuario = "manual"

    try:
        os.remove(TRIGGER_FILE)
    except Exception:
        pass

    return True, usuario, ejec_id


# ─── Main loop ────────────────────────────────────────────────────────
def main():
    log.titulo("SCRAPER RAMA JUDICIAL")
    log.resultado(f"Entorno: {ENV}")
    log.resultado(f"Debug:   {'ACTIVADO' if DEBUG_SCRAPER else 'DESACTIVADO'}")
    log.resultado(f"Fecha:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log.separador()

    setup_environment()
    log_ip_salida()

    if DEBUG_SCRAPER:
        probar_procesos([
            "08296408900120190029100",
            "11001310300120080020700",
            "11001310300120080023700",
            "11001310300120130071600",
            "11001310300120150030300",
        ])
        return

    bogota_tz = ZoneInfo("America/Bogota")
    cfg = get_runtime_config()
    schedule_time = cfg["schedule_time"]
    log.progreso(f"Scheduler iniciado. Proxima ejecucion: {schedule_time}")
    log.progreso(f"Estado scraper: {'ACTIVO' if cfg['activo'] else 'PAUSADO'}")

    while True:
        # Releer config en cada vuelta para ver cambios
        cfg = get_runtime_config()
        schedule_time = cfg["schedule_time"]
        hh, mm = map(int, schedule_time.split(":"))

        now    = datetime.now(bogota_tz)
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)

        remaining = (target - now).total_seconds()
        log.progreso(f"Proximo ciclo programado: {schedule_time} (en {int(remaining//3600)}h {int((remaining%3600)//60)}m)")

        # Esperar hasta el target, pero chequeando trigger manual cada 10s
        while remaining > 0:
            tick = min(10, remaining)
            time.sleep(tick)
            remaining -= tick

            # Ejecucion manual solicitada?
            triggered, usuario, ejec_id_existente = chequear_trigger_manual()
            if triggered:
                log.progreso(f"Ejecucion manual solicitada por {usuario}")
                if ejec_id_existente:
                    log.progreso(f"   Usando ejecucion existente #{ejec_id_existente} (creada por API)")
                cfg = get_runtime_config()
                if cfg["activo"]:
                    ejecutar_ciclo(
                        tipo="manual",
                        iniciado_por=usuario,
                        ejec_id_externo=ejec_id_existente
                    )
                else:
                    log.advertencia("Scraper pausado, ignorando trigger manual")
                # Romper el wait y recalcular el siguiente target
                break

        else:
            # Llegamos al horario programado sin interrupciones
            cfg = get_runtime_config()
            if cfg["activo"]:
                ejecutar_ciclo(tipo="automatica", iniciado_por="scheduler")
            else:
                log.advertencia("Scraper pausado, saltando ciclo programado")


if __name__ == "__main__":
    main()
