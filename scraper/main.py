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
        for numero, fecha, actu, anota, _url in actes:
            writer.writerow([numero, "Sistema", fecha_registro, fecha, "", actu, anota])
    log.resultado(f"CSV generado: {csv_path}")


def send_report_email():
    now = datetime.now()
    fecha_str = now.strftime("%A %d-%m-%Y a las %I:%M %p").capitalize()
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(EMAIL_USER, EMAIL_PASS)
        msg = MIMEMultipart()
        msg["Subject"] = f"Reporte Diario de Actuaciones - {fecha_str}"
        msg["From"]    = EMAIL_USER
        msg["To"]      = EMAIL_USER
        msg.attach(MIMEText(
            f"Adjunto encontrarás el reporte de actuaciones generado el {fecha_str}.",
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


def probar_procesos(lista_procesos):
    log.titulo(f"MODO PRUEBA — {len(lista_procesos)} PROCESOS")
    results, actes, errors = [], [], []
    lock = threading.Lock()
    worker.process_counter = itertools.count(1)
    worker.TOTAL_PROCESSES = len(lista_procesos)

    log.progreso("Obteniendo sesión via Bright Data...")
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
    if actes:
        for i, act in enumerate(actes[:10], 1):
            log.proceso(f"  {i}. {act[1]} — {act[2][:80]}...")
    if errors:
        for num, msg in errors:
            log.advertencia(f"  • {num}: {msg[:100]}")


def ejecutar_ciclo():
    log.titulo("INICIANDO CICLO DE SCRAPING")
    log.resultado(f"📅 Fecha:   {datetime.now().strftime('%d/%m/%Y')}")
    log.resultado(f"🎯 Período: últimos {DIAS_BUSQUEDA} días")
    log.resultado(f"🔄 Hilos:   {NUM_THREADS}")
    log.separador()

    start_ts = time.time()
    worker.process_counter = itertools.count(1)

    for path in [PDF_PATH, os.path.join(OUTPUT_DIR, "actuaciones.csv")]:
        if os.path.exists(path):
            os.remove(path)

    procesos = cargar_procesos()
    TOTAL = len(procesos)
    worker.TOTAL_PROCESSES = TOTAL
    log.progreso(f"Procesos a escanear: {TOTAL}")

    log.progreso("Obteniendo sesión via Bright Data...")
    get_session()
    log.exito("Sesión lista — iniciando threads")

    q = Queue()
    for num in procesos:
        q.put(num)
    for _ in range(NUM_THREADS):
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
                    log.advertencia(f"{numero}: intento {intento+1}/10 — {exc}")
                    if intento == 9:
                        with lock:
                            errors.append((numero, str(exc)[:200]))

    threads = []
    for _ in range(NUM_THREADS):
        t = threading.Thread(target=loop, daemon=True)
        t.start()
        threads.append(t)

    q.join()
    for t in threads:
        t.join()

    generar_pdf(TOTAL, actes, errors, start_ts, time.time())
    exportar_csv(actes, start_ts)

    if ENV == 'production':
        try:
            send_report_email()
        except Exception as e:
            log.error(f"Error enviando correo: {e}")

    log.titulo("RESUMEN DEL CICLO")
    log.resultado(f"✅ Escaneados:  {TOTAL - len(errors)}")
    log.resultado(f"❌ Errores:     {len(errors)}")
    log.resultado(f"📋 Actuaciones: {len(actes)}")
    log.separador()


def main():
    log.titulo("SCRAPER RAMA JUDICIAL")
    log.resultado(f"🌍 Entorno: {ENV}")
    log.resultado(f"🔧 Debug:   {'ACTIVADO' if DEBUG_SCRAPER else 'DESACTIVADO'}")
    log.resultado(f"📅 Fecha:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log.separador()

    setup_environment()
    log_ip_salida()

    if DEBUG_SCRAPER:
        probar_procesos([
            "08296408900120190029100",
            "11001310300120080020700",
            "11001310300120080023700",
            "11001310300120130071600",
            "11001310300120150030300"
        ])
    else:
        bogota_tz = ZoneInfo("America/Bogota")
        hh, mm    = map(int, SCHEDULE_TIME.split(":"))
        log.progreso(f"Scheduler iniciado. Próxima ejecución: {SCHEDULE_TIME}")

        while True:
            now    = datetime.now(bogota_tz)
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            remaining = (target - now).total_seconds()
            while remaining > 0:
                if remaining > 3600:
                    log.progreso(f"Próxima ejecución en {int(remaining//3600)} hora(s)")
                    time.sleep(3600)
                    remaining -= 3600
                else:
                    log.progreso(f"Próxima ejecución en {int(remaining//60)}m {int(remaining%60)}s")
                    time.sleep(remaining)
                    remaining = 0

            ejecutar_ciclo()


if __name__ == "__main__":
    main()