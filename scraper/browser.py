# scraper/browser.py
import os
import random
import logging
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("webdriver_manager").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def wait_for_tor_circuit(timeout=120):
    """
    Espera ACTIVAMENTE hasta que TOR tenga un circuito de salida funcionando.
    No solo espera tiempo, sino que VERIFICA que puede salir a internet.
    """
    import requests
    import time

    logging.info("=" * 60)
    logging.info("🔍 VERIFICANDO CIRCUITO TOR")
    logging.info("=" * 60)

    start_time = time.time()

    # 1. Obtener IP directa (sin proxy)
    direct_ip = None
    try:
        direct_response = requests.get('https://api.ipify.org', timeout=10)
        if direct_response.status_code == 200:
            direct_ip = direct_response.text.strip()
            logging.info(f"   📡 IP Directa: {direct_ip}")
    except Exception as e:
        logging.warning(f"   ⚠️ No se pudo obtener IP directa: {e}")

    # 2. Intentar con TOR hasta que funcione
    attempt = 0
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
                    logging.info(f"   ✅ TOR LISTO! IP: {tor_ip} (diferente a {direct_ip})")
                    logging.info(f"   ⏱️  Tiempo de espera: {int(time.time() - start_time)}s")
                    return True
                elif not direct_ip:
                    logging.info(f"   ✅ TOR responde con IP: {tor_ip}")
                    return True
                else:
                    logging.warning(f"   ⚠️ TOR tiene misma IP que directa ({tor_ip}) - aún no listo")

        except requests.exceptions.ConnectionError as e:
            if "SOCKS" in str(e):
                elapsed = int(time.time() - start_time)
                logging.info(f"   ⏳ TOR iniciando... ({elapsed}s/{timeout}s)")
            else:
                logging.debug(f"   🔄 Intento {attempt}: {e.__class__.__name__}")
        except Exception as e:
            logging.debug(f"   🔄 Intento {attempt}: {e.__class__.__name__}")

        # Esperar antes de reintentar
        time.sleep(3)

    logging.error(f"   ❌ TOR no estableció circuito después de {timeout} segundos")
    return False


def new_chrome_driver(worker_id=None):
    """Driver que espera ACTIVAMENTE a que TOR esté listo."""

    logging.info(f"\n{'=' * 60}")
    logging.info(f"🚀 INICIANDO DRIVER PARA WORKER {worker_id}")
    logging.info(f"{'=' * 60}")

    # ========== PASO 1: ESPERAR A QUE TOR ESTÉ LISTO ==========
    if not wait_for_tor_circuit(timeout=120):
        logging.error("❌ No se puede continuar sin TOR")
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
    logging.info(f"   📱 User-Agent: {selected_ua[:60]}...")

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
        logging.info("   📥 Instalando/obteniendo ChromeDriver...")
        chromedriver_path = ChromeDriverManager().install()
        service = ChromeService(executable_path=chromedriver_path)

        # 3.2 Crear driver
        driver = webdriver.Chrome(service=service, options=options)
        logging.info("   ✅ Driver creado exitosamente")

        # 3.3 Eliminar rastros de automation
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Sobrescribir chrome object
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
        logging.info("   🔍 Verificando TOR en el navegador...")

        try:
            # 4.1 Navegar a check.torproject.org
            driver.set_page_load_timeout(45)
            driver.get("https://check.torproject.org")
            time.sleep(5)

            page_source = driver.page_source
            if "Congratulations" in page_source:
                logging.info("   🎉 NAVEGADOR CONFIRMADO usando TOR")

                # 4.2 Obtener IP real del navegador
                driver.get("https://api.ipify.org")
                time.sleep(3)
                browser_ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                logging.info(f"   🌐 IP del navegador: {browser_ip}")

                # 4.3 Volver a página principal
                driver.get("https://consultaprocesos.ramajudicial.gov.co")
                time.sleep(3)
            else:
                logging.warning("   ⚠️ Navegador NO está usando TOR")

        except Exception as e:
            logging.warning(f"   ⚠️ Error verificando TOR en navegador: {e}")
            # Intentar navegar directamente al sitio
            try:
                driver.get("https://consultaprocesos.ramajudicial.gov.co")
                time.sleep(3)
            except:
                pass

        logging.info(f"✅ Driver {worker_id} listo para usar")
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
        result = driver.execute_script("""
            return {
                hasDocument: typeof document !== 'undefined',
                hasWindow: typeof window !== 'undefined',
                userAgent: navigator.userAgent
            }
        """)

        if result.get('hasDocument') and result.get('hasWindow'):
            logging.info("✅ JavaScript funcionando correctamente")
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
        driver.get("https://check.torproject.org")
        time.sleep(3)

        if "Congratulations" in driver.page_source:
            logging.info("✅ Navegando a través de TOR confirmado")
            return True
        else:
            logging.warning("⚠️ No se detecta TOR activo")
            return False
    except Exception as e:
        logging.error(f"Error verificando TOR: {e}")
        return False


def handle_modal_error(driver, numero):
    """Maneja el modal de error de red."""
    try:
        # Buscar modal activo
        modal = driver.find_element(By.XPATH,
                                    "//div[contains(@class, 'v-dialog--active')]"
                                    )

        logging.warning(f"⚠️ Modal de error detectado para {numero}")

        # Buscar botón Volver
        volver_btn = modal.find_element(By.XPATH,
                                        ".//button[contains(text(), 'Volver')]"
                                        )

        # Hacer click
        driver.execute_script("arguments[0].click();", volver_btn)
        logging.info(f"   ✅ Click en Volver ejecutado")
        time.sleep(3)

        # Esperar a que TOR se recupere
        if wait_for_tor_circuit(timeout=60):
            logging.info(f"   ✅ TOR recuperado")
            return True
        else:
            logging.error(f"   ❌ TOR no se recuperó")
            return False

    except Exception as e:
        logging.debug(f"No hay modal de error o no se pudo manejar: {e}")
        return False