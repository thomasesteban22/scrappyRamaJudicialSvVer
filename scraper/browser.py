# scraper/browser.py

import os
import time
import logging
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from .config import ENV

logging.getLogger("selenium").setLevel(logging.WARNING)


def new_chrome_driver(worker_id=None, headless=False):  # Añade parámetro opcional
    chromedriver_autoinstaller.install()

    opts = webdriver.ChromeOptions()

    # =========================
    # CONFIGURACIÓN AVANZADA ANTI-DETECCIÓN
    # =========================
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches",
                                 ["enable-automation", "enable-logging", "disable-popup-blocking"])
    opts.add_experimental_option('useAutomationExtension', False)

    # WebDriver false flag
    opts.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    })

    # =========================
    # CONFIGURACIÓN VPS/DOCKER
    # =========================
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--single-process")  # Importante para Docker
    opts.add_argument("--disable-setuid-sandbox")

    # =========================
    # HEADLESS MODE MEJORADO
    # =========================
    if ENV.upper() == "PRODUCTION" or headless:
        opts.add_argument("--headless=new")  # Nueva sintaxis headless
        opts.add_argument("--remote-debugging-port=9222")
        opts.add_argument("--disable-web-security")
        opts.add_argument("--allow-running-insecure-content")

    # =========================
    # USER AGENT REALISTA Y OTROS HEADERS
    # =========================
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    import random
    opts.add_argument(f"--user-agent={random.choice(user_agents)}")

    # =========================
    # WINDOW SIZE Y OTRAS CONFIGURACIONES
    # =========================
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=es-ES")

    # =========================
    # PERFIL AISLADO
    # =========================
    import tempfile
    profile_dir = tempfile.mkdtemp()
    opts.add_argument(f"--user-data-dir={profile_dir}")

    # =========================
    # MEJORAR PERFORMANCE EN DOCKER
    # =========================
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-features=VizDisplayCompositor")

    # =========================
    # CAPABILITIES
    # =========================
    caps = opts.to_capabilities()
    caps['goog:chromeOptions'] = {}
    caps['goog:chromeOptions']['excludeSwitches'] = ['enable-automation']

    # =========================
    # INICIAR DRIVER
    # =========================
    service = Service()

    try:
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception as e:
        # Fallback sin service
        driver = webdriver.Chrome(options=opts)

    # =========================
    # EXECUTE CDP COMMANDS PARA EVITAR DETECCIÓN
    # =========================
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": driver.execute_script("return navigator.userAgent").replace("Headless", ""),
        "platform": "Win32"
    })

    # Eliminar webdriver property
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # Ocultar más propiedades
    driver.execute_script("""
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['es-ES', 'es', 'en-US', 'en']
        });
    """)

    # =========================
    # TIMEZONE Y LOCALE
    # =========================
    try:
        driver.execute_cdp_cmd(
            "Emulation.setTimezoneOverride",
            {"timezoneId": "America/Bogota"}
        )
        driver.execute_cdp_cmd(
            "Emulation.setLocaleOverride",
            {"locale": "es-CO"}
        )
    except:
        pass

    # =========================
    # TIMEOUTS
    # =========================
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)
    driver.implicitly_wait(10)

    return driver


def is_page_maintenance(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(k in body_text for k in ("mantenimiento", "temporalmente fuera"))
    except Exception:
        return False