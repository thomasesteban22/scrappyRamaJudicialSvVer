# scraper/mailer.py

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from .config import EMAIL_USER, EMAIL_PASS, PDF_PATH

def send_report_email():
    """
    Envía un correo con el PDF generado como adjunto.
    Usa las credenciales y rutas definidas en config.py.
    """
    # Formatear fecha y hora para el cuerpo del mensaje
    now = datetime.now()
    fecha_str = now.strftime("%A %d-%m-%Y a las %I:%M %p").capitalize()

    # Crear mensaje multipart
    msg = MIMEMultipart()
    msg["Subject"] = "Reporte Diario de Actuaciones"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    # Cuerpo del correo
    cuerpo = f"Adjunto encontrarás el reporte de actuaciones generado el {fecha_str}."
    msg.attach(MIMEText(cuerpo, "plain"))

    # Adjuntar el PDF
    with open(PDF_PATH, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(PDF_PATH))
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(PDF_PATH)
        )
        msg.attach(part)

    # Enviar por SMTP SSL
    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtp.login(EMAIL_USER, EMAIL_PASS)
    smtp.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
    smtp.quit()

    print("Correo enviado exitosamente.")
