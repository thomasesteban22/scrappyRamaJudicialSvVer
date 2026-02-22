# scraper/browser.py
import os
import random
import time
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

from .config import ENV, DEBUG_SCRAPER
from .logger import log

os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'


def new_chrome_driver(worker_id=None):
    """
    Crea un driver de Chrome con undetected-chromedriver.
    Usa Xvfb (display virtual) en producción en lugar de --headless,
    lo que evita la detección de automatización.
    """
    label = f"driver {worker_id}" if worker_id is not None else "driver"
    log.progreso(f"Iniciando {label}...")

    options = uc.ChromeOptions()

    # ── Configuración base ────────────────────────────────────────────────────
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=es-CO")
    options.add_argument("--accept-lang=es-CO,es;q=0.9")

    # ── Preferencias de perfil ────────────────────────────────────────────────
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.images": 1,
    }
    options.add_experimental_option("prefs", prefs)

    # ── User-Agent realista ───────────────────────────────────────────────────
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    selected_ua = random.choice(user_agents)
    options.add_argument(f"--user-agent={selected_ua}")
    log.debug(f"User-Agent: {selected_ua[:70]}...")

    # ── Estrategia de carga ───────────────────────────────────────────────────
    options.page_load_strategy = "eager"

    try:
        log.debug("Creando instancia de Chrome (undetected)...")

        driver = uc.Chrome(
            options=options,
            headless=False,        # IMPORTANTE: false = usa Xvfb, no headless real
            use_subprocess=True,   # Evita que el proceso hijo herede señales
            version_main=None,     # Autodetecta versión de Chrome instalado
        )

        # ── Timeouts ──────────────────────────────────────────────────────────
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.implicitly_wait(15)

        # ── Ocultar propiedades de automatización adicionales ─────────────────
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                // Ocultar webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Chrome runtime simulado
                window.chrome = {
                    runtime: {
                        connect: () => {},
                        sendMessage: () => {},
                    },
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // Plugins simulados (navegador real tiene plugins)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });

                // Idiomas
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['es-CO', 'es', 'en-US', 'en'],
                });

                // Permisos no devuelven "denied" automáticamente
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """
        })

        log.exito(f"✅ {label} listo")

        # ── Verificación en modo debug ─────────────────────────────────────────
        if DEBUG_SCRAPER:
            _verificar_driver(driver)

        return driver

    except Exception as e:
        log.error(f"Error creando {label}: {e}")
        raise


def _verificar_driver(driver):
    """Verificación rápida del driver en modo debug."""
    try:
        log.debug("Verificando driver (modo debug)...")
        driver.get("https://bot.sannysoft.com")
        time.sleep(3)
        log.debug("Página de verificación cargada")

        import requests
        try:
            ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
            log.debug(f"IP de salida: {ip}")
        except Exception:
            log.debug("No se pudo obtener IP de salida")

    except Exception as e:
        log.debug(f"Error en verificación: {e}")


def is_page_maintenance(driver):
    """Detecta si la página está en mantenimiento."""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        keywords = [
            "mantenimiento", "temporalmente fuera", "estamos trabajando",
            "servicio no disponible", "under maintenance", "en construcción"
        ]
        for kw in keywords:
            if kw in body_text:
                log.advertencia(f"Página en mantenimiento: '{kw}'")
                return True
        return False
    except Exception as e:
        log.debug(f"Error verificando mantenimiento: {e}")
        return False


def handle_modal_error(driver, numero):
    """Intenta cerrar cualquier modal activo."""
    try:
        modal = driver.find_element(
            By.XPATH, "//div[contains(@class, 'v-dialog--active')]"
        )
        log.advertencia(f"Modal detectado para {numero}")
        buttons = modal.find_elements(By.XPATH, ".//button")
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
            log.accion("Modal cerrado")
            time.sleep(2)
            return True
        log.debug("Modal sin botón de cierre")
        return False
    except Exception as e:
        log.debug(f"Sin modal activo: {e}")
        return False


def human_delay(min_s=1.0, max_s=3.0):
    """Pausa aleatoria para simular comportamiento humano."""
    time.sleep(random.uniform(min_s, max_s))