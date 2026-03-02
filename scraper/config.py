# scraper/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ========== ENTORNO ==========
ENV          = os.getenv('ENVIRONMENT', 'development')
HEADLESS     = os.getenv('HEADLESS', 'true').lower() == 'true'
DEBUG_SCRAPER = os.getenv('DEBUG_SCRAPER', '0') == '1'

# ========== RUTAS ==========
EXCEL_PATH_PRODUCTION   = os.getenv('EXCEL_PATH_PRODUCTION',  './data/FOLDERESBASENUEVA.xlsm')
EXCEL_PATH_DEVELOPMENT  = os.getenv('EXCEL_PATH_DEVELOPMENT', './data/procesos_test.xlsm')
INFORMACION_PATH_PRODUCTION  = os.getenv('INFORMACION_PATH_PRODUCTION',  './output/actuaciones.pdf')
INFORMACION_PATH_DEVELOPMENT = os.getenv('INFORMACION_PATH_DEVELOPMENT', './output/actuaciones.pdf')

# ========== EMAIL ==========
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# ========== SCRAPER ==========
DIAS_BUSQUEDA = int(os.getenv('DIAS_BUSQUEDA', '1'))
WAIT_TIME     = int(os.getenv('WAIT_TIME', '6'))
NUM_THREADS   = int(os.getenv('NUM_THREADS', '1'))
SCHEDULE_TIME = os.getenv('SCHEDULE_TIME', '01:00')

# ========== CLOUDFLARE WORKER PROXY ==========
CF_WORKER_URL  = os.getenv('CF_WORKER_URL', '')   # https://workercf.magnaabogados.workers.dev
CF_AUTH_TOKEN  = os.getenv('CF_AUTH_TOKEN', '')   # Token secreto configurado en el Worker

# ========== DIRECTORIOS ==========
OUTPUT_DIR = "./output"
PDF_PATH   = INFORMACION_PATH_PRODUCTION  if ENV == 'production' else INFORMACION_PATH_DEVELOPMENT
EXCEL_PATH = EXCEL_PATH_PRODUCTION        if ENV == 'production' else EXCEL_PATH_DEVELOPMENT
LOG_DIR    = "/app/logs"

os.makedirs(OUTPUT_DIR,             exist_ok=True)
os.makedirs("./debug",              exist_ok=True)
os.makedirs("./debug/screenshots",  exist_ok=True)
os.makedirs("./debug/html",         exist_ok=True)
os.makedirs(LOG_DIR,                exist_ok=True)


# ========== BRIGHT DATA ==========
BD_USER = os.getenv('BD_USER', '')
BD_PASS = os.getenv('BD_PASS', '')
BD_HOST = os.getenv('BD_HOST', 'brd.superproxy.io')
BD_PORT = os.getenv('BD_PORT', '9515')