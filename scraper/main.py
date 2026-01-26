import os
import csv
import smtplib
import time
import threading
import logging
import requests
import itertools
from queue import Queue
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# 1) Silencia TensorFlow y Chrome/DevTools
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['WEBVIEW_LOG_LEVEL'] = '3'

# 2) Config global de logging: sólo INFO y superiores
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
# Silencia logs muy ruidosos
for noisy in ('selenium', 'urllib3', 'absl', 'google_apis'):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from .config import (
    OUTPUT_DIR,
    NUM_THREADS,
    PDF_PATH,
    EMAIL_USER,
    EMAIL_PASS,
    SCHEDULE_TIME  # ej. "01:00"
)
from .loader import cargar_procesos
from .browser import new_chrome_driver
from .worker import worker_task
import scraper.worker as worker
from .reporter import generar_pdf


def exportar_csv(actes, start_ts):
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
    print(f"CSV generado: {csv_path}")


def send_report_email():
    now = datetime.now()
    fecha_str = now.strftime("%A %d-%m-%Y a las %I:%M %p").capitalize()
    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtp.login(EMAIL_USER, EMAIL_PASS)

    msg = MIMEMultipart()
    msg["Subject"] = "Reporte Diario de Actuaciones"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    cuerpo = f"Adjunto encontrarás el reporte de actuaciones generado el {fecha_str}."
    msg.attach(MIMEText(cuerpo, "plain"))

    with open(PDF_PATH, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(PDF_PATH))
        part.add_header(
            'Content-Disposition',
            'attachment',
            filename=os.path.basename(PDF_PATH)
        )
        msg.attach(part)

    smtp.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
    smtp.quit()
    print("Correo enviado exitosamente.", flush=True)


def ejecutar_ciclo():
    """Ejecuta un ciclo completo de scraping, reporte, CSV y correo."""
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

    logging.info(f"Total de procesos a escanear: {TOTAL}")
    logging.info(">>> INICIO DE CICLO <<<")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Prep cola y threads
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
            numero = q.get();
            q.task_done()
            if numero is None:
                break
            for intento in range(10):
                try:
                    worker_task(numero, driver, results, actes, errors, lock)
                    break
                except Exception as exc:
                    logging.warning(f"{numero}: intento {intento + 1}/10 fallido ({exc})")
                    if intento == 9:
                        with lock:
                            errors.append((numero, str(exc)))
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
    try:
        send_report_email()
    except Exception as e:
        logging.error(f"Error enviando correo: {e}")

    # Resumen
    err = len(errors)
    esc = TOTAL - err
    logging.info(f"=== RESUMEN CICLO === Total: {TOTAL} | Escaneados: {esc} | Errores: {err}")
    if err:
        logging.error("Procesos con error:")
        for num, msg in errors:
            logging.error(f"  • {num}: {msg}")
    logging.info(">>> FIN DE CICLO <<<\n")

def log_ip_salida():
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        logging.info(f"IP SALIENTE DEL CONTENEDOR: {ip}")
    except Exception as e:
        logging.error(f"No se pudo obtener IP de salida: {e}")



def main():
    logging.info("Scheduler iniciado, esperando el primer ciclo diario...")

    # Log de IP de salida
    log_ip_salida()

    bogota_tz = ZoneInfo("America/Bogota")
    hh, mm = map(int, SCHEDULE_TIME.split(":"))

    while True:
        now = datetime.now(bogota_tz)
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_sec = (target - now).total_seconds()

        # Conteo regresivo con avisos cada hora (y último aviso minutos/segundos)
        remaining = wait_sec
        while remaining > 0:
            if remaining > 3600:
                hrs = int(remaining // 3600)
                logging.info(f"Faltan {hrs} hora(s) para la próxima ejecución.")
                time.sleep(3600)
                remaining -= 3600
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                logging.info(f"Faltan {mins} minuto(s) y {secs} segundo(s) para la ejecución.")
                time.sleep(remaining)
                remaining = 0

        # Hora de arrancar un nuevo ciclo
        ejecutar_ciclo()



if __name__ == "__main__":
    main()
