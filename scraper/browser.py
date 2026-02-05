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
    # DESCARGAR E INSTALAR CHROMEDRIVER
    # =========================
    chromedriver_autoinstaller.install()  # descarga la versión correcta automáticamente

    opts = webdriver.ChromeOptions()

    # =========================
    # OCULTAR SELENIUM
    # =========================
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)

    # =========================
    # FLAGS CRÍTICOS PARA VPS / DOCKER
    # =========================
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-client-side-phishing-detection")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-sync")
    opts.add_argument("--metrics-recording-only")
    opts.add_argument("--no-first-run")
    opts.add_argument("--safebrowsing-disable-auto-update")
    opts.add_argument("--enable-features=NetworkServiceInProcess")
    opts.add_argument("--window-size=1920,1080")

    # =========================
    # HEADLESS Y USER-AGENT PARA PRODUCCIÓN
    # =========================
    if ENV.upper() == "PRODUCTION":
        opts.add_argument("--headless=new")  # ⚡ Crucial para VPS
        opts.add_argument("--remote-debugging-port=9222")
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36")
        opts.page_load_strategy = "eager"

    # =========================
    # PERFIL AISLADO POR WORKER
    # =========================
    base = os.path.join(os.getcwd(), "tmp_profiles")
    os.makedirs(base, exist_ok=True)
    stamp = worker_id if worker_id is not None else int(time.time() * 1000)
    profile_dir = os.path.join(base, f"profile_{stamp}")
    opts.add_argument(f"--user-data-dir={profile_dir}")

    # =========================
    # CHROME BIN OPCIONAL (en Docker a veces es necesario)
    # =========================
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin and os.path.isfile(chrome_bin):
        opts.binary_location = chrome_bin

    # =========================
    # INICIAR DRIVER
    # =========================
    service = Service()
    driver = webdriver.Chrome(service=service, options=opts)

    # =========================
    # ANTI DETECCIÓN
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
    # TIMEOUTS
    # =========================
    driver.set_page_load_timeout(120)  # Para SPAs con JS pesado
    driver.implicitly_wait(10)

    return driver


def is_page_maintenance(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(k in body_text for k in ("mantenimiento", "temporalmente fuera"))
    except Exception:
        return False