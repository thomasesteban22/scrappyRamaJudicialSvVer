# scraper/browser.py

import os
import time
import random
import logging
import tempfile
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    """Crea un driver de Chrome optimizado para VPS/Docker con Xvfb."""

    # =========================
    # CONFIGURACIÓN BÁSICA
    # =========================
    chromedriver_autoinstaller.install()

    opts = webdriver.ChromeOptions()

    # =========================
    # ANTI-DETECCIÓN AVANZADA
    # =========================
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches",
                                 ["enable-automation", "enable-logging", "disable-popup-blocking"])
    opts.add_experimental_option('useAutomationExtension', False)

    # Preferencias para parecer más humano
    opts.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.images": 1,
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    })

    # =========================
    # CONFIGURACIÓN VPS/DOCKER CON XVFB
    # =========================
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--disable-client-side-phishing-detection")
    opts.add_argument("--disable-component-update")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-domain-reliability")
    opts.add_argument("--disable-features=AudioServiceOutOfProcess")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("--disable-hang-monitor")
    opts.add_argument("--disable-ipc-flooding-protection")
    opts.add_argument("--disable-prompt-on-repost")
    opts.add_argument("--disable-sync")

    # =========================
    # HEADLESS MODE PARA PRODUCCIÓN
    # =========================
    if ENV.upper() == "PRODUCTION":
        # Usar el nuevo headless mode
        opts.add_argument("--headless=new")
        opts.add_argument("--remote-debugging-port=9222")
        opts.add_argument("--disable-web-security")
        opts.add_argument("--allow-running-insecure-content")
        opts.add_argument("--disable-features=IsolateOrigins,site-per-process")
        opts.page_load_strategy = "eager"

    # =========================
    # USER-AGENT REALISTA Y ROTACIÓN
    # =========================
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    selected_ua = random.choice(user_agents)
    opts.add_argument(f"user-agent={selected_ua}")
    logging.info(f"User-Agent seleccionado: {selected_ua[:50]}...")

    # =========================
    # OTRAS CONFIGURACIONES
    # =========================
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=es-ES")
    opts.add_argument("--accept-lang=es-ES,es;q=0.9")

    # =========================
    # PERFIL TEMPORAL ÚNICO
    # =========================
    profile_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{worker_id or ''}_")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument(f"--disk-cache-dir={profile_dir}/cache")

    # =========================
    # CONFIGURAR CHROME BINARY
    # =========================
    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome-stable")
    if os.path.isfile(chrome_bin):
        opts.binary_location = chrome_bin

    # =========================
    # LOGGING Y CAPABILITIES
    # =========================
    caps = DesiredCapabilities.CHROME.copy()
    caps['goog:loggingPrefs'] = {'browser': 'SEVERE', 'performance': 'ALL'}
    caps['acceptInsecureCerts'] = True

    # =========================
    # INICIAR DRIVER
    # =========================
    service = None
    try:
        # Intentar con Service primero
        service = Service(
            executable_path=os.environ.get("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver"),
            service_args=['--verbose']
        )
        driver = webdriver.Chrome(service=service, options=opts, desired_capabilities=caps)
    except Exception as e:
        logging.warning(f"Error con Service, intentando sin él: {e}")
        try:
            driver = webdriver.Chrome(options=opts, desired_capabilities=caps)
        except Exception as e2:
            logging.error(f"Error crítico iniciando Chrome: {e2}")
            raise

    # =========================
    # ANTI-DETECCIÓN: ELIMINAR RASTROS
    # =========================
    try:
        # Quitar propiedad webdriver
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Sobrescribir otras propiedades
        driver.execute_script("""
            // Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Plugins modificados
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-ES', 'es', 'en-US', 'en']
            });

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        # CDP Commands para modificar navigator
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": driver.execute_script("return navigator.userAgent"),
            "platform": "Win32",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Chromium", "version": "120"},
                    {"brand": "Google Chrome", "version": "120"},
                    {"brand": "Not=A?Brand", "version": "99"}
                ],
                "fullVersion": "120.0.0.0",
                "platform": "Windows",
                "platformVersion": "10.0.0",
                "architecture": "x86",
                "model": ""
            }
        })

    except Exception as e:
        logging.warning(f"No se pudieron aplicar todas las medidas anti-detección: {e}")

    # =========================
    # CONFIGURACIÓN REGIONAL
    # =========================
    try:
        # Zona horaria Colombia
        driver.execute_cdp_cmd(
            "Emulation.setTimezoneOverride",
            {"timezoneId": "America/Bogota"}
        )

        # Geolocalización Bogotá
        driver.execute_cdp_cmd(
            "Emulation.setGeolocationOverride",
            {
                "latitude": 4.7110,
                "longitude": -74.0721,
                "accuracy": 100
            }
        )

        # Idioma español
        driver.execute_cdp_cmd(
            "Emulation.setLocaleOverride",
            {"locale": "es-CO"}
        )

    except Exception as e:
        logging.debug(f"No se pudo configurar región: {e}")

    # =========================
    # TIMEOUTS Y CONFIGURACIÓN FINAL
    # =========================
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)
    driver.implicitly_wait(10)

    logging.info(f"✅ Driver creado exitosamente para worker {worker_id}")
    logging.info(f"   Perfil: {profile_dir}")
    logging.info(f"   User-Agent: {selected_ua[:40]}...")

    return driver


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


def safe_find_element(driver, by, value, timeout=10):
    """Busca elemento de forma segura con timeout."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception as e:
        logging.debug(f"Elemento no encontrado {by}={value}: {e}")
        return None


def take_screenshot(driver, filename):
    """Toma screenshot y lo guarda."""
    try:
        screenshot_dir = "/app/debug/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, filename)
        driver.save_screenshot(path)
        logging.info(f"📸 Screenshot guardado: {path}")
        return path
    except Exception as e:
        logging.error(f"Error tomando screenshot: {e}")
        return None