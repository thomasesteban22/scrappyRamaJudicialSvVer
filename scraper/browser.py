# scraper/browser.py
import os
import random
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from .config import ENV
from .logger import log

# ========== SILENCIAR LOGS EXTERNOS ==========
# Ya están silenciados en logger.py, pero por si acaso:
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
os.environ['TOR_LOG'] = 'notice stderr'


def wait_for_tor_circuit(timeout=120):
    """
    Espera ACTIVAMENTE hasta que TOR tenga un circuito de salida funcionando.
    AHORA: Solo muestra logs en consola si son importantes.
    Todos los logs detallados van al archivo.
    """
    start_time = time.time()

    # Mensaje inicial (solo una vez, va al archivo)
    log.tor("Verificando circuito TOR...")

    # 1. Obtener IP directa (sin proxy)
    direct_ip = None
    try:
        direct_response = requests.get('https://api.ipify.org', timeout=10)
        if direct_response.status_code == 200:
            direct_ip = direct_response.text.strip()
            log.tor(f"IP Directa: {direct_ip}")
    except Exception as e:
        log.tor(f"No se pudo obtener IP directa: {e}")

    # 2. Intentar con TOR hasta que funcione
    attempt = 0
    last_log_time = 0

    while time.time() - start_time < timeout:
        attempt += 1
        try:
            session = requests.Session()
            session.proxies = {
                'http': 'socks5://127.0.0.1:9050',
                'https': 'socks5://127.0.0.1:9050'
            }
            session.timeout = 15

            # Obtener IP por TOR
            response = session.get('https://api.ipify.org', timeout=15)

            if response.status_code == 200:
                tor_ip = response.text.strip()

                # Verificar que NO es la misma IP directa
                if direct_ip and tor_ip != direct_ip:
                    elapsed = int(time.time() - start_time)
                    log.tor(f"✅ TOR LISTO! IP: {tor_ip} (en {elapsed}s)")
                    # Mensaje corto en consola
                    log.info(f"TOR listo ({elapsed}s)")
                    return True
                elif not direct_ip:
                    log.tor(f"✅ TOR responde con IP: {tor_ip}")
                    log.info("TOR listo")
                    return True
                else:
                    log.tor(f"⚠️ TOR tiene misma IP que directa ({tor_ip})")

        except Exception as e:
            # Solo log cada 15 segundos para no saturar
            current_time = time.time()
            if current_time - last_log_time > 15:
                elapsed = int(time.time() - start_time)
                log.tor(f"Esperando TOR... ({elapsed}s/{timeout}s)")
                last_log_time = current_time

        time.sleep(3)

    log.error(f"❌ TOR no estableció circuito después de {timeout} segundos")
    return False


def new_chrome_driver(worker_id=None):
    """Driver que espera ACTIVAMENTE a que TOR esté listo."""

    # Mensaje minimalista en consola
    if worker_id is not None:
        log.progreso(f"Iniciando driver {worker_id}...")
    else:
        log.progreso("Iniciando driver...")

    # ========== PASO 1: ESPERAR A QUE TOR ESTÉ LISTO ==========
    if not wait_for_tor_circuit(timeout=120):
        log.error("❌ No se puede continuar sin TOR")
        raise Exception("TOR no está funcionando después de 120 segundos")

    # ========== PASO 2: CONFIGURAR OPCIONES DE CHROME ==========
    options = Options()

    # 2.1 Anti-detección
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)

    # 2.2 Preferencias para evitar detección
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.images": 1,
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    }
    options.add_experimental_option("prefs", prefs)

    # 2.3 Configuración para VPS/Docker
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")

    # 2.4 Headless para producción
    if ENV.upper() == "PRODUCTION":
        options.add_argument("--headless=new")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--remote-debugging-address=0.0.0.0")

    # 2.5 User-Agent realista
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    selected_ua = random.choice(user_agents)
    options.add_argument(f"user-agent={selected_ua}")
    log.tor(f"User-Agent: {selected_ua[:60]}...")

    # 2.6 Tamaño y configuración de pantalla
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=es-ES")
    options.add_argument("--accept-lang=es-ES,es;q=0.9")

    # 2.7 Configurar proxy TOR
    options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')

    # 2.8 Timeouts en página
    options.page_load_strategy = "eager"

    # ========== PASO 3: INICIAR DRIVER ==========
    try:
        # 3.1 Obtener ChromeDriver compatible
        log.tor("Obteniendo ChromeDriver...")
        chromedriver_path = ChromeDriverManager().install()
        service = ChromeService(executable_path=chromedriver_path)

        # 3.2 Crear driver
        driver = webdriver.Chrome(service=service, options=options)
        log.tor("✅ Driver creado")

        # 3.3 Eliminar rastros de automation
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)

        # 3.4 Configurar timeouts
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.implicitly_wait(15)

        # ========== PASO 4: VERIFICAR TOR EN EL NAVEGADOR ==========
        # Solo verificamos, pero sin saturar la consola
        log.tor("Verificando TOR en navegador...")
        try:
            driver.set_page_load_timeout(45)
            driver.get("https://check.torproject.org")
            time.sleep(5)

            if "Congratulations" in driver.page_source:
                log.tor("✅ Navegador usando TOR")

                driver.get("https://api.ipify.org")
                time.sleep(3)
                browser_ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                log.tor(f"IP navegador: {browser_ip}")
            else:
                log.tor("⚠️ Navegador NO está usando TOR")

        except Exception as e:
            log.tor(f"Error verificando TOR: {e}")

        # Siempre navegar al sitio objetivo
        try:
            driver.get("https://consultaprocesos.ramajudicial.gov.co")
            time.sleep(3)
        except:
            pass

        log.exito("Driver listo")
        return driver

    except Exception as e:
        log.error(f"Error creando driver: {e}")
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
                log.advertencia(f"Página en mantenimiento: {keyword}")
                return True

        return False
    except Exception as e:
        log.debug(f"Error verificando mantenimiento: {e}")
        return False


def test_javascript(driver):
    """Verifica que JavaScript está funcionando."""
    try:
        result = driver.execute_script("""
            return {
                hasDocument: typeof document !== 'undefined',
                hasWindow: typeof window !== 'undefined'
            }
        """)

        if result.get('hasDocument') and result.get('hasWindow'):
            log.debug("JavaScript OK")
            return True
        else:
            log.advertencia("JavaScript podría no estar funcionando")
            return False
    except Exception as e:
        log.error(f"Error en test JavaScript: {e}")
        return False


def check_tor_connection(driver):
    """Verifica que está usando TOR."""
    try:
        driver.get("https://check.torproject.org")
        time.sleep(3)

        if "Congratulations" in driver.page_source:
            log.tor("✅ Navegador usando TOR")
            return True
        else:
            log.tor("⚠️ No se detecta TOR")
            return False
    except Exception as e:
        log.tor(f"Error verificando TOR: {e}")
        return False


def handle_modal_error(driver, numero):
    """Maneja el modal de error de red."""
    try:
        modal = driver.find_element(By.XPATH,
                                    "//div[contains(@class, 'v-dialog--active')]"
                                    )

        log.advertencia(f"Modal de error detectado para {numero}")

        volver_btn = modal.find_element(By.XPATH,
                                        ".//button[contains(text(), 'Volver')]"
                                        )

        driver.execute_script("arguments[0].click();", volver_btn)
        log.accion("Cerrando modal...")
        time.sleep(3)

        if wait_for_tor_circuit(timeout=60):
            log.tor("TOR recuperado")
            return True
        else:
            log.error("TOR no se recuperó")
            return False

    except Exception as e:
        log.debug(f"No hay modal de error: {e}")
        return False