# scraper/browser.py - VERSIÓN CON TOR
import os
import random
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

from .tor_manager import TorController
from .free_proxy_manager import FreeProxyManager
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    """Driver que usa TOR primario y proxies gratuitos como fallback."""

    # Inicializar controladores
    tor = TorController()
    proxy_manager = FreeProxyManager()

    # 1. Intentar con TOR primero
    use_tor = tor.start()

    options = Options()

    # 2. Configuración anti-detección (mismo que antes)
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
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")

    # 3. Configurar proxy según disponibilidad
    if use_tor:
        # Configurar TOR
        options = tor.create_selenium_options(options)
        logging.info("🚀 Usando TOR como proxy")
    else:
        # Fallback a proxy gratuito
        free_proxy = proxy_manager.get_tested_proxy()
        if free_proxy:
            options.add_argument(f'--proxy-server={free_proxy}')
            logging.info(f"🔄 Usando proxy gratuito: {free_proxy}")
        else:
            logging.warning("⚠️ Sin proxy disponible, usando conexión directa (riesgo de bloqueo)")

    try:
        # 4. Iniciar driver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # 5. Eliminar rastros de automation
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 6. Verificar conexión
        if use_tor:
            driver.get("https://check.torproject.org")
            time.sleep(2)
            if "Congratulations" in driver.page_source:
                logging.info("🎉 Navegando a través de TOR confirmado")

        # 7. Timeouts
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(15)

        logging.info(f"✅ Driver {worker_id} creado exitosamente")

        # Pasar controladores al driver para uso posterior
        driver.tor_controller = tor if use_tor else None
        driver.proxy_manager = proxy_manager

        return driver

    except Exception as e:
        logging.error(f"❌ Error creando driver: {e}")

        # Último intento: driver sin proxy
        try:
            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--headless=new")

            driver = webdriver.Chrome(options=options)
            logging.warning("⚠️ Driver creado SIN proxy (alto riesgo de bloqueo)")
            return driver
        except:
            raise