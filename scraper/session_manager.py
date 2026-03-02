# scraper/session_manager.py
import time
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import BD_USER, BD_PASS, BD_HOST, BD_PORT
from .logger import log

WEB_URL  = "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion"
API_BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"

_session: requests.Session | None = None
_session_created_at: datetime | None = None
SESSION_TTL_MINUTES = 45


def _create_session_via_browser() -> requests.Session:
    """
    Abre la página UNA sola vez con Bright Data Browser API,
    extrae las cookies y construye una sesión requests con ellas.
    Costo: ~1MB = $0.000008 por ejecución diaria.
    """
    log.progreso("Iniciando Browser API (1 page load)...")

    options = Options()
    options.add_argument("--lang=es-CO")

    remote_url = f"https://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"
    driver = None

    try:
        driver = webdriver.Remote(
            command_executor=remote_url,
            options=options,
        )
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)

        log.debug("Cargando página para obtener cookies...")
        driver.get(WEB_URL)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
        )
        time.sleep(3)

        cookies = driver.get_cookies()
        ua      = driver.execute_script("return navigator.userAgent")

        log.exito(f"Sesión obtenida — {len(cookies)} cookies")

        session = requests.Session()
        for c in cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))

        session.headers.update({
            "User-Agent":      ua,
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin":          "https://consultaprocesos.ramajudicial.gov.co",
            "Referer":         "https://consultaprocesos.ramajudicial.gov.co/",
            "Sec-Fetch-Dest":  "empty",
            "Sec-Fetch-Mode":  "cors",
            "Sec-Fetch-Site":  "same-site",
        })
        return session

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        log.debug("Browser API cerrado")


def get_session(force_refresh: bool = False) -> requests.Session:
    global _session, _session_created_at
    now = datetime.now()
    expired = (
        _session_created_at is None
        or (now - _session_created_at) > timedelta(minutes=SESSION_TTL_MINUTES)
    )
    if _session is None or expired or force_refresh:
        _session = _create_session_via_browser()
        _session_created_at = now
        log.exito(f"Sesión válida hasta ~{(now + timedelta(minutes=SESSION_TTL_MINUTES)).strftime('%H:%M')}")
    return _session


def api_get_procesos(numero: str, pagina: int = 1) -> dict | None:
    url    = f"{API_BASE}/Procesos/Consulta/NumeroRadicacion"
    params = {"numero": str(numero), "SoloActivos": "false", "pagina": pagina}
    for attempt in range(2):
        try:
            r = get_session(force_refresh=(attempt > 0)).get(url, params=params, timeout=30)
            if r.status_code == 403 and attempt == 0:
                log.advertencia("403 — renovando sesión...")
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"Error api_get_procesos({numero}): {e}")
            if attempt == 0:
                continue
    return None


def api_get_actuaciones(id_proceso: int, pagina: int = 1) -> dict | None:
    url    = f"{API_BASE}/Proceso/Actuaciones/{id_proceso}"
    params = {"pagina": pagina}
    for attempt in range(2):
        try:
            r = get_session(force_refresh=(attempt > 0)).get(url, params=params, timeout=30)
            if r.status_code == 403 and attempt == 0:
                log.advertencia("403 — renovando sesión...")
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"Error api_get_actuaciones({id_proceso}): {e}")
            if attempt == 0:
                continue
    return None