# scraper/browser.py
import os
import random
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    """Driver que usa TOR."""

    options = Options()

    # Configuración anti-detección
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if ENV.upper() == "PRODUCTION":
        options.add_argument("--headless=new")

    # User-Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")

    options.add_argument("--window-size=1920,1080")

    # IMPORTANTE: Configurar proxy TOR
    options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')

    try:
        # Iniciar driver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Eliminar rastros
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Timeouts
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(15)

        logging.info(f"✅ Driver {worker_id} creado con proxy TOR")

        return driver

    except Exception as e:
        logging.error(f"❌ Error creando driver: {e}")
        raise