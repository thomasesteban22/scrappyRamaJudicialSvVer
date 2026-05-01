# scraper/session_manager.py
import requests
from .logger import log

API_BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"

_session = None

def get_session(force_refresh=False):
    global _session
    if _session is None or force_refresh:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin":          "https://consultaprocesos.ramajudicial.gov.co",
            "Referer":         "https://consultaprocesos.ramajudicial.gov.co/",
            "Sec-Fetch-Dest":  "empty",
            "Sec-Fetch-Mode":  "cors",
            "Sec-Fetch-Site":  "same-site",
        })
        log.exito("Sesión requests lista")
    return _session


def api_get_procesos(numero: str, pagina: int = 1) -> dict | None:
    url    = f"{API_BASE}/Procesos/Consulta/NumeroRadicacion"
    params = {"numero": str(numero), "SoloActivos": "false", "pagina": pagina}
    for attempt in range(2):
        try:
            r = get_session(force_refresh=(attempt > 0)).get(url, params=params, timeout=30)
            if r.status_code == 403 and attempt == 0:
                log.advertencia("403 — reintentando...")
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
                log.advertencia("403 — reintentando...")
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"Error api_get_actuaciones({id_proceso}): {e}")
            if attempt == 0:
                continue
    return None


import time as _time
_original_get = None

def _patched_get(self_unused, url, **kwargs):
    _time.sleep(1.5)
    return _original_get(url, **kwargs)
