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


def wait_for_tor_ready(timeout=180):
    """Esperar a que TOR esté completamente listo."""
    import requests
    import time

    logging.info("⏳ Esperando a que TOR se conecte...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            session = requests.Session()
            session.proxies = {
                'http': 'socks5://127.0.0.1:9050',
                'https': 'socks5://127.0.0.1:9050'
            }
            session.timeout = 10

            response = session.get('https://api.ipify.org', timeout=15)

            if response.status_code == 200:
                tor_ip = response.text.strip()
                # También probar sin proxy para comparar
                try:
                    direct_response = requests.get('https://api.ipify.org', timeout=10)
                    direct_ip = direct_response.text.strip()

                    if tor_ip != direct_ip:
                        logging.info(f"✅ TOR listo: IP TOR={tor_ip}, IP Directa={direct_ip}")
                        return True
                    else:
                        logging.warning(f"⚠️ Misma IP: {tor_ip} (TOR podría no estar funcionando)")
                except:
                    logging.info(f"✅ TOR respondiendo con IP: {tor_ip}")
                    return True

        except Exception as e:
            elapsed = int(time.time() - start_time)
            logging.info(f"⏳ Esperando TOR... ({elapsed}s/{timeout}s)")
            time.sleep(5)

    logging.error(f"❌ Timeout esperando TOR después de {timeout} segundos")
    return False


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
        # 1. ESPERAR que TOR esté listo ANTES de crear driver
        if not wait_for_tor_ready(timeout=120):
            logging.warning("⚠️ TOR no está listo, continuando de todos modos...")

        # 2. Crear driver (resto del código igual)
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # 3. Verificar TOR en el navegador
        driver.set_page_load_timeout(120)  # Aumentar timeout

        try:
            driver.get("https://check.torproject.org")
            time.sleep(5)

            if "Congratulations" in driver.page_source:
                logging.info("🎉 Navegando exitosamente a través de TOR")
                # Obtener IP real
                driver.get("https://api.ipify.org")
                tor_ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                logging.info(f"🌐 IP actual a través de TOR: {tor_ip}")
            else:
                logging.warning("⚠️ No se detecta TOR en el navegador")

        except Exception as e:
            logging.warning(f"Error verificando TOR en navegador: {e}")

        return driver

    except Exception as e:
        logging.error(f"❌ Error creando driver: {e}")
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