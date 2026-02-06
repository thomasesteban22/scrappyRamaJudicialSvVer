# scraper/browser.py

import os
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    """Driver con webdriver-manager para compatibilidad automática."""

    # Configurar opciones
    options = Options()

    # Configuración anti-detección
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Preferencias para evitar detección
    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
    })

    # Configuración VPS/Docker
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Headless para producción
    if ENV.upper() == "PRODUCTION":
        options.add_argument("--headless=new")
        options.add_argument("--remote-debugging-port=9222")

    # User-Agent aleatorio
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    ]

    options.add_argument(f"user-agent={random.choice(user_agents)}")

    # Tamaño de ventana y otras configuraciones
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=es-ES")

    try:
        # Usar webdriver-manager para obtener ChromeDriver compatible
        logging.info("Instalando/obteniendo ChromeDriver compatible...")

        # Método 1: webdriver-manager automático
        from selenium.webdriver.chrome.service import Service as ChromeService
        service = ChromeService(ChromeDriverManager().install())

        # Iniciar driver
        driver = webdriver.Chrome(service=service, options=options)

        # Método alternativo si falla:
        # driver = webdriver.Chrome(options=options)

    except Exception as e:
        logging.error(f"Error con webdriver-manager: {e}, intentando método alternativo...")
        try:
            # Método alternativo: ChromeDriver del sistema
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e2:
            logging.error(f"Error método alternativo: {e2}")
            # Último recurso: sin service
            driver = webdriver.Chrome(options=options)

    # Eliminar rastros de automatización
    try:
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Ocultar más propiedades
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)
    except Exception as e:
        logging.warning(f"No se pudieron aplicar medidas anti-detección: {e}")

    # Configurar timeouts
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)

    logging.info(f"✅ Driver creado para worker {worker_id}")
    logging.info(f"   Chrome: {driver.capabilities['browserVersion']}")
    logging.info(f"   ChromeDriver: {driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0]}")

    return driver


def is_page_maintenance(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(k in body_text for k in ("mantenimiento", "temporalmente fuera"))
    except:
        return False