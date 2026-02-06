# scraper/browser.py
import os
import random
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
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

    # Preferencias
    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
    })

    # Configuración VPS
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Headless para producción
    if ENV.upper() == "PRODUCTION":
        options.add_argument("--headless=new")
        options.add_argument("--remote-debugging-port=9222")

    # User-Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")

    # Tamaño y configuración
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=es-ES")

    # Configurar proxy TOR
    options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')

    try:
        # Iniciar driver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Eliminar rastros de automation
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Timeouts
        driver.set_page_load_timeout(90)  # Más tiempo para TOR
        driver.implicitly_wait(20)

        logging.info(f"✅ Driver {worker_id} creado con proxy TOR")

        # Verificar conexión TOR
        try:
            driver.get("https://check.torproject.org")
            time.sleep(3)
            if "Congratulations" in driver.page_source:
                logging.info("🎉 Conectado exitosamente a través de TOR")
            else:
                logging.warning("⚠️ Podría no estar usando TOR")
        except:
            logging.warning("No se pudo verificar conexión TOR")

        return driver

    except Exception as e:
        logging.error(f"❌ Error creando driver: {e}")

        # Fallback: intentar sin proxy
        try:
            logging.warning("Intentando sin proxy TOR...")
            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--headless=new")
            options.add_argument("--disable-web-security")
            options.add_argument("--ignore-certificate-errors")

            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logging.warning("⚠️ Driver creado SIN TOR (riesgo de bloqueo)")
            return driver
        except Exception as e2:
            logging.error(f"❌ Error fatal: {e2}")
            raise


def is_page_maintenance(driver):
    """Detecta si la página está en mantenimiento."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body_text = body.text.lower()

        maintenance_keywords = [
            "mantenimiento",
            "temporalmente fuera",
            "estamos trabajando",
            "servicio no disponible",
            "under maintenance",
            "en construcción"
        ]

        for keyword in maintenance_keywords:
            if keyword in body_text:
                logging.warning(f"⚠️ Página en mantenimiento: {keyword}")
                return True

        return False
    except Exception as e:
        logging.debug(f"Error verificando mantenimiento: {e}")
        return False


def test_javascript(driver):
    """Verifica que JavaScript está funcionando."""
    try:
        # Ejecutar test simple
        result = driver.execute_script("return typeof document !== 'undefined'")
        if result:
            logging.info("✅ JavaScript funcionando")
            return True
        else:
            logging.warning("⚠️ JavaScript podría no estar funcionando")
            return False
    except Exception as e:
        logging.error(f"❌ Error en test JavaScript: {e}")
        return False


def check_tor_connection(driver):
    """Verifica que está usando TOR."""
    try:
        # Navegar a página de verificación
        driver.get("https://check.torproject.org")
        time.sleep(3)

        if "Congratulations" in driver.page_source:
            logging.info("✅ Navegando a través de TOR confirmado")
            return True
        else:
            logging.warning("⚠️ No se detecta TOR activo")
            return False
    except:
        return False