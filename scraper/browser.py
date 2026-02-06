# scraper/browser.py
import os
import random
import logging
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("webdriver_manager").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None):
    """Driver que imita completamente un navegador humano y evita CORS."""

    # =========================
    # CONFIGURACIÓN DE OPCIONES AVANZADA
    # =========================
    options = Options()

    # =========================
    # 1. ANTI-DETECCIÓN COMPLETA
    # =========================
    # Eliminar todos los rastros de automation
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", [
        "enable-automation",
        "enable-logging",
        "disable-popup-blocking"
    ])
    options.add_experimental_option('useAutomationExtension', False)

    # Preferencias para deshabilitar features de automation
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.images": 1,

        # IMPORTANTE: Habilitar WebGL y hardware acceleration
        "hardware_acceleration_mode.enabled": True,
        "enable-webgl": True,
        "enable-accelerated-2d-canvas": True,

        # Habilitar todas las features de JS
        "profile.default_content_setting_values.javascript": 1,
        "profile.default_content_setting_values.cookies": 1,
        "profile.default_content_setting_values.plugins": 1,
        "profile.default_content_setting_values.popups": 1,

        # Deshabilitar automation detection
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    }
    options.add_experimental_option("prefs", prefs)

    # =========================
    # 2. CONFIGURACIÓN PARA VPS/DOCKER
    # =========================
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # =========================
    # 3. HEADLESS OPTIMIZADO (no detectable)
    # =========================
    if ENV.upper() == "PRODUCTION":
        # Usar el nuevo headless que es menos detectable
        options.add_argument("--headless=new")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--remote-debugging-address=0.0.0.0")

        # Configurar para que parezca tener display real
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-features=VizDisplayCompositor")

    # =========================
    # 4. USER-AGENT REALISTA CON ROTACIÓN
    # =========================
    user_agents = [
        # Chrome en Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",

        # Chrome en Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",

        # Chrome en Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",

        # Firefox (para diversidad)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    ]

    selected_ua = random.choice(user_agents)
    options.add_argument(f"user-agent={selected_ua}")
    logging.info(f"User-Agent: {selected_ua}")

    # =========================
    # 5. HEADERS Y CONFIGURACIÓN DE RED CRÍTICOS
    # =========================
    # Añadir headers para evitar CORS
    options.add_argument("--disable-web-security")  # ⚠️ Importante para CORS
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")

    # Habilitar todas las features necesarias
    options.add_argument("--enable-javascript")
    options.add_argument("--enable-cookies")
    options.add_argument("--enable-plugins")

    # Configuración regional
    options.add_argument("--lang=es-ES")
    options.add_argument("--accept-lang=es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7")

    # Habilitar hardware para que JS funcione completamente
    options.add_argument("--enable-gpu-rasterization")
    options.add_argument("--enable-zero-copy")
    options.add_argument("--enable-features=VaapiVideoDecoder")

    # =========================
    # 6. PERFIL TEMPORAL ÚNICO
    # =========================
    profile_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{worker_id}_")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument(f"--disk-cache-dir={profile_dir}/cache")
    options.add_argument(f"--media-cache-dir={profile_dir}/media")

    # Habilitar cache y almacenamiento
    options.add_argument("--enable-local-file-accesses")
    options.add_argument("--allow-file-access-from-files")

    # =========================
    # 7. INICIAR DRIVER CON WEBDRIVER-MANAGER
    # =========================
    try:
        logging.info("Configurando ChromeDriver compatible...")
        service = ChromeService(ChromeDriverManager().install())

        # Iniciar driver
        driver = webdriver.Chrome(service=service, options=options)

    except Exception as e:
        logging.error(f"Error con webdriver-manager: {e}")
        try:
            # Fallback: usar Service estándar
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e2:
            logging.error(f"Error método alternativo: {e2}")
            # Último recurso
            driver = webdriver.Chrome(options=options)

    # =========================
    # 8. EJECUTAR CDP COMMANDS PARA MODIFICAR NAVIGATOR
    # =========================
    try:
        # 8.1 Eliminar webdriver property completamente
        driver.execute_script("""
            // Eliminar la propiedad webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Sobrescribir navigator completo
            const originalNavigator = window.navigator;
            window.navigator = new Proxy(originalNavigator, {
                get: (target, prop) => {
                    if (prop === 'webdriver') return undefined;
                    if (prop === 'plugins') return { length: 5 };
                    if (prop === 'languages') return ['es-ES', 'es', 'en-US', 'en'];
                    if (prop === 'language') return 'es-ES';
                    return target[prop];
                }
            });

            // Sobrescribir chrome
            window.chrome = {
                runtime: {
                    id: 'fake-runtime-id',
                    getManifest: () => ({ version: '1.0' })
                },
                loadTimes: function() {
                    return {
                        requestTime: Date.now() - 1000,
                        startLoadTime: Date.now() - 2000,
                        commitLoadTime: Date.now() - 1500,
                        finishDocumentLoadTime: Date.now() - 500,
                        finishLoadTime: Date.now(),
                        firstPaintTime: Date.now() - 400,
                        firstPaintAfterLoadTime: Date.now() - 300,
                        navigationType: 'Reload',
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false,
                        npnNegotiatedProtocol: 'http/1.1',
                        wasAlternateProtocolAvailable: false,
                        connectionInfo: 'http/1.1'
                    };
                },
                csi: function() {
                    return {
                        onloadT: Date.now() - 1000,
                        pageT: Date.now() - 2000,
                        startE: Date.now() - 3000,
                        tran: 15
                    };
                },
                app: {
                    isInstalled: false,
                    InstallState: 'not_installed',
                    RunningState: 'cannot_run'
                }
            };

            // Sobrescribir permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Sobrescribir getParameter para WebGL
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };

            console.log('Navigator modificado exitosamente');
        """)

        logging.info("✅ Navigator modificado exitosamente")

    except Exception as e:
        logging.warning(f"No se pudieron aplicar modificaciones al Navigator: {e}")

    # =========================
    # 9. CONFIGURAR ZONA HORARIA Y GEOLOCALIZACIÓN
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
                "latitude": 4.609710,
                "longitude": -74.081750,
                "accuracy": 100
            }
        )

        # Idioma español Colombia
        driver.execute_cdp_cmd(
            "Emulation.setLocaleOverride",
            {"locale": "es-CO"}
        )

        # Configurar resolución de pantalla
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1920,
                "height": 1080,
                "deviceScaleFactor": 1,
                "mobile": False,
                "viewport": {
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 1080,
                    "scale": 1
                }
            }
        )

        logging.info("✅ Configuración regional aplicada")

    except Exception as e:
        logging.debug(f"Configuración regional no aplicada: {e}")

    # =========================
    # 10. CONFIGURAR INTERCEPTOR DE PETICIONES
    # =========================
    try:
        # Habilitar network interception
        driver.execute_cdp_cmd('Network.enable', {})

        # Configurar headers para todas las peticiones
        driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/',
                'User-Agent': selected_ua
            }
        })

        # Configurar para ignorar CORS
        driver.execute_cdp_cmd('Network.setRequestInterception', {
            'patterns': [{
                'urlPattern': '*',
                'resourceType': 'XHR',
                'interceptionStage': 'Request'
            }]
        })

        logging.info("✅ Interceptor de peticiones configurado")

    except Exception as e:
        logging.warning(f"No se pudo configurar interceptor: {e}")

    # =========================
    # 11. TIMEOUTS Y CONFIGURACIÓN FINAL
    # =========================
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(45)
    driver.implicitly_wait(15)

    # Verificar que JavaScript está funcionando
    try:
        js_test = driver.execute_script("return typeof window !== 'undefined' && window.document !== null")
        if js_test:
            logging.info("✅ JavaScript funcionando correctamente")
        else:
            logging.warning("⚠️ JavaScript podría no estar funcionando")
    except:
        logging.error("❌ Error ejecutando JavaScript")

    logging.info(f"🚀 Driver {worker_id} creado exitosamente")
    logging.info(f"   Perfil: {profile_dir}")
    logging.info(f"   User-Agent: {selected_ua[:60]}...")

    return driver


def is_page_maintenance(driver):
    """Verifica si la página está en mantenimiento."""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        maintenance_keywords = [
            "mantenimiento", "temporalmente fuera", "estamos trabajando",
            "servicio no disponible", "under maintenance", "en construcción"
        ]

        for keyword in maintenance_keywords:
            if keyword in body_text:
                logging.warning(f"⚠️ Página en mantenimiento detectado: {keyword}")
                return True

        return False
    except Exception as e:
        logging.debug(f"Error verificando mantenimiento: {e}")
        return False


def test_javascript(driver):
    """Verifica que JavaScript está funcionando correctamente."""
    try:
        # Ejecutar varios tests de JavaScript
        tests = [
            "return typeof document !== 'undefined'",
            "return typeof window !== 'undefined'",
            "return navigator.userAgent.includes('Chrome')",
            "return document.readyState === 'complete'"
        ]

        results = []
        for test in tests:
            try:
                result = driver.execute_script(test)
                results.append(result)
            except:
                results.append(False)

        all_passed = all(results)
        if all_passed:
            logging.info("✅ Todos los tests de JavaScript pasaron")
        else:
            logging.warning(f"⚠️ Tests de JavaScript: {results}")

        return all_passed

    except Exception as e:
        logging.error(f"❌ Error en tests de JavaScript: {e}")
        return False