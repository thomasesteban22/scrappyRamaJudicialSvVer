# scraper/browser.py

import os
import time
import logging
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    # =========================
    # INSTALAR CHROMEDRIVER CORRECTO
    # =========================
    chromedriver_autoinstaller.install()  # descarga e instala la versión correcta automáticamente

    opts = webdriver.ChromeOptions()

    # =========================
    # OCULTAR SELENIUM
    # =========================
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)

    # =========================
    # FLAGS CRÍTICOS VPS / DOCKER
    # =========================
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")

    # =========================
    # IDIOMA REAL COLOMBIA
    # =========================
    opts.add_argument("--lang=es-CO")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "intl.accept_languages": "es-CO,es"
    }
    opts.add_experimental_option("prefs", prefs)

    # =========================
    # HEADLESS Y USER-AGENT
    # =========================
    if ENV.upper() == "PRODUCTION":
        opts.add_argument("--headless=new")
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36")
        opts.page_load_strategy = "eager"  # Mejor para SPAs con JS pesado

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
    # ANTI DETECCIÓN JS
    # =========================
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """)

    # =========================
    # ZONA HORARIA COLOMBIA
    # =========================
    try:
        driver.execute_cdp_cmd(
            "Emulation.setTimezoneOverride",
            {"timezoneId": "America/Bogota"}
        )
    except Exception:
        pass

    # =========================
    # TIMEOUTS GLOBALES
    # =========================
    driver.set_page_load_timeout(120)  # aumento de timeout para páginas JS
    driver.implicitly_wait(10)

    return driver


def is_page_maintenance(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(k in body_text for k in ("mantenimiento", "temporalmente fuera"))
    except Exception:
        return False