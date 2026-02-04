# scraper/browser.py

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)

def new_chrome_driver(worker_id=None):
    opts = webdriver.ChromeOptions()

    # =========================
    # OCULTAR SELENIUM
    # =========================
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)



    # =========================
    # FLAGS CRÍTICOS VPS
    # =========================
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")

    # =========================
    # HEADLESS
    # =========================
    if ENV.upper() == "PRODUCTION":
        opts.add_argument("--headless=new")

    # =========================
    # PREFS (NO bloquear CSS)
    # =========================
    prefs = {
        "profile.managed_default_content_settings.images": 2
    }
    opts.add_experimental_option("prefs", prefs)

    # =========================
    # ESTRATEGIA DE CARGA
    # =========================
    opts.page_load_strategy = "normal"

    # =========================
    # PERFIL AISLADO
    # =========================
    base = os.path.join(os.getcwd(), "tmp_profiles")
    os.makedirs(base, exist_ok=True)
    stamp = worker_id if worker_id is not None else int(time.time() * 1000)
    profile_dir = os.path.join(base, f"profile_{stamp}")
    opts.add_argument(f"--user-data-dir={profile_dir}")

    # =========================
    # CHROME BIN (opcional)
    # =========================
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin and os.path.isfile(chrome_bin):
        opts.binary_location = chrome_bin

    # =========================
    # DRIVER
    # =========================
    service = Service()
    driver = webdriver.Chrome(service=service, options=opts)

    # =========================
    # TIMEOUTS GLOBALES
    # =========================
    driver.set_page_load_timeout(90)   # ⬅️ más tolerante a latencia
    driver.implicitly_wait(10)

    return driver


def is_page_maintenance(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(k in body_text for k in ("mantenimiento", "temporalmente fuera"))
    except Exception:
        return False
