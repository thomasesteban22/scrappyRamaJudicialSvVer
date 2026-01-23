import os
from dotenv import load_dotenv
load_dotenv()

ENV            = os.getenv("ENVIRONMENT", "production").upper()
EXCEL_PATH     = os.getenv(f"EXCEL_PATH_{ENV}")
PDF_PATH       = os.getenv(f"INFORMACION_PATH_{ENV}")
EMAIL_USER     = os.getenv("EMAIL_USER")
EMAIL_PASS     = os.getenv("EMAIL_PASS")

DIAS_BUSQUEDA  = int(os.getenv("DIAS_BUSQUEDA", 5))
WAIT_TIME      = float(os.getenv("WAIT_TIME", 0))
NUM_THREADS    = int(os.getenv("NUM_THREADS", 1))

OUTPUT_DIR     = os.path.dirname(PDF_PATH)
LOG_TXT_PATH   = os.path.join(OUTPUT_DIR, "report.txt")

# Hora programada para arrancar (HH:MM, 24 h), zona America/Bogota
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "01:00")
