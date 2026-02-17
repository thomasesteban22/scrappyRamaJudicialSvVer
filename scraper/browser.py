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
from stem import Signal
from stem.control import Controller
from .config import ENV
from .logger import log

# ========== SILENCIAR LOGS EXTERNOS ==========
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
os.environ['TOR_LOG'] = 'notice stderr'


def renew_tor_circuit():
    """
    Solicita a TOR una nueva identidad (nuevo circuito de salida).
    Retorna True si se logra, False en caso contrario.
    """
    try:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()  # Usa cookie de autenticación
            controller.signal(Signal.NEWNYM)
            time.sleep(5)  # Esperar a que se establezca el nuevo circuito
            log.tor("Circuito TOR renovado exitosamente")
            return True
    except Exception as e:
        log.error(f"Error renovando circuito TOR: {e}")
        return False


def wait_for_tor_circuit(timeout=180):
    """
    Espera ACTIVAMENTE hasta que TOR tenga un circuito de salida funcionando.
    Con logging detallado para diagnosticar por qué falla.
    """
    start_time = time.time()

    log.info(f"Verificando conexión TOR (timeout={timeout}s)...")
    log.tor("Iniciando verificación de circuito TOR")

    # 1. Obtener IP directa (sin proxy)
    direct_ip = None
    try:
        log.tor("Obteniendo IP directa...")
        direct_response = requests.get('https://api.ipify.org', timeout=10)
        if direct_response.status_code == 200:
            direct_ip = direct_response.text.strip()
            log.tor(f"✅ IP Directa obtenida: {direct_ip}")
        else:
            log.tor(f"⚠️ Respuesta inesperada al obtener IP directa: {direct_response.status_code}")
    except Exception as e:
        log.tor(f"No se pudo obtener IP directa: {e}")

    attempts = 0
    last_log_time = 0
    consecutive_errors = 0

    log.tor(f"Iniciando búsqueda de circuito TOR (timeout={timeout}s)")

    while time.time() - start_time < timeout:
        attempts += 1
        try:
            log.tor(f"Intento {attempts} - Creando sesión TOR...")
            session = requests.Session()
            session.proxies = {
                'http': 'socks5://127.0.0.1:9050',
                'https': 'socks5://127.0.0.1:9050'
            }
            session.timeout = 15

            log.tor(f"Intento {attempts} - Consultando api.ipify.org a través de TOR...")
            response = session.get('https://api.ipify.org', timeout=15)

            if response.status_code == 200:
                tor_ip = response.text.strip()
                log.tor(f"Intento {attempts} - Respuesta recibida desde TOR: {tor_ip}")

                if direct_ip and tor_ip != direct_ip:
                    elapsed = int(time.time() - start_time)
                    log.tor(f"✅ TOR FUNCIONANDO! IP diferente: {tor_ip} vs {direct_ip}")
                    log.exito(f"Conexión TOR establecida ({elapsed} segundos)")
                    return True
                elif not direct_ip:
                    elapsed = int(time.time() - start_time)
                    log.tor(f"✅ TOR responde con IP: {tor_ip} (sin IP directa)")
                    log.exito(f"Conexión TOR establecida ({elapsed} segundos)")
                    return True
                else:
                    log.tor(f"⚠️ TOR devolvió la MISMA IP que directa ({tor_ip}) - posible problema")
                    consecutive_errors += 1
            else:
                log.tor(f"⚠️ Intento {attempts} - Código de respuesta inesperado: {response.status_code}")
                consecutive_errors += 1

        except requests.exceptions.ConnectionError as e:
            log.tor(f"⚠️ Intento {attempts} - Error de conexión: {type(e).__name__}")
            if "SOCKS" in str(e):
                log.tor("   → Esto puede indicar que TOR no está escuchando en el puerto 9050")
            consecutive_errors += 1
        except requests.exceptions.Timeout as e:
            log.tor(f"⚠️ Intento {attempts} - Timeout: {type(e).__name__}")
            consecutive_errors += 1
        except Exception as e:
            log.tor(f"⚠️ Intento {attempts} - Error inesperado: {type(e).__name__}: {str(e)[:100]}")
            consecutive_errors += 1

        current_time = time.time()
        elapsed = int(current_time - start_time)
        if current_time - last_log_time > 15:
            porcentaje = min(100, int((elapsed / timeout) * 100))
            log.progreso(f"Esperando TOR... {porcentaje}% ({elapsed}s/{timeout}s) - {attempts} intentos")
            if consecutive_errors > 5:
                log.tor(f"   ⚠️ {consecutive_errors} errores consecutivos - posible problema de red")
            last_log_time = current_time

        time.sleep(5)

    log.error(f"❌ TOR no estableció circuito después de {timeout} segundos")
    log.error(f"   • Intentos realizados: {attempts}")
    log.error(f"   • Errores consecutivos al final: {consecutive_errors}")
    log.error(f"   • IP Directa: {direct_ip if direct_ip else 'No disponible'}")
    log.info("📌 Posibles soluciones:")
    log.info("   • Verificar que TOR esté instalado y corriendo: 'ps aux | grep tor'")
    log.info("   • Verificar conectividad: 'curl --socks5 127.0.0.1:9050 https://api.ipify.org'")
    log.info("   • Revisar logs de TOR: 'tail -f /var/log/tor/log'")
    log.info("   • Aumentar timeout en la configuración")
    return False


def new_chrome_driver(worker_id=None):
    """
    Crea un driver de Chrome configurado para usar TOR.
    NOTA: Esta función ASUME que TOR ya está funcionando.
    NO verifica TOR nuevamente.
    """
    if worker_id is not None:
        log.progreso(f"Iniciando driver {worker_id}...")
    else:
        log.progreso("Iniciando driver...")

    options = Options()

    # Anti-detección
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)

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

    # Configuración para VPS/Docker
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")

    if ENV.upper() == "PRODUCTION":
        options.add_argument("--headless=new")
        options.add_argument("--remote-debugging-port=9222")

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    selected_ua = random.choice(user_agents)
    options.add_argument(f"user-agent={selected_ua}")
    log.tor(f"User-Agent: {selected_ua[:60]}...")

    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=es-ES")
    options.add_argument("--accept-lang=es-ES,es;q=0.9")

    # Proxy TOR
    options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')

    options.page_load_strategy = "eager"

    try:
        log.tor("Obteniendo ChromeDriver...")
        chromedriver_path = ChromeDriverManager().install()
        service = ChromeService(executable_path=chromedriver_path)

        driver = webdriver.Chrome(service=service, options=options)
        log.tor("✅ Driver creado")

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

        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.implicitly_wait(15)

        if ENV.upper() != "PRODUCTION":
            try:
                driver.set_page_load_timeout(30)
                log.tor("Verificando TOR en navegador...")
                driver.get("https://check.torproject.org")
                time.sleep(3)
                if "Congratulations" in driver.page_source:
                    log.tor("✅ Navegador usando TOR")
                else:
                    log.tor("⚠️ Navegador NO está usando TOR")
                driver.get("https://api.ipify.org")
                time.sleep(2)
                browser_ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                log.tor(f"IP del navegador: {browser_ip}")
                driver.get("https://consultaprocesos.ramajudicial.gov.co")
            except Exception as e:
                log.tor(f"Error en verificación: {e}")

        log.exito("Driver listo")
        return driver

    except Exception as e:
        log.error(f"Error creando driver: {e}")
        raise


def is_page_maintenance(driver):
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body_text = body.text.lower()
        maintenance_keywords = [
            "mantenimiento", "temporalmente fuera", "estamos trabajando",
            "servicio no disponible", "under maintenance", "en construcción"
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


def handle_modal_error(driver, numero):
    """
    Intenta cerrar cualquier modal activo.
    Retorna True si logra cerrar alguno, False si no.
    """
    try:
        modal = driver.find_element(By.XPATH, "//div[contains(@class, 'v-dialog--active')]")
        log.advertencia(f"Modal detectado para {numero}")
        buttons = modal.find_elements(By.XPATH, ".//button")
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
            log.accion("Botón del modal clickeado")
            time.sleep(2)
            return True
        else:
            log.debug("No se encontró botón en el modal")
            return False
    except Exception as e:
        log.debug(f"No hay modal: {e}")
        return False