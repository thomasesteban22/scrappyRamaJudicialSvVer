"""Cliente de la API de Magna usado por el scraper para leer config/procesos
y reportar ejecuciones."""
import os
import requests
from .logger import log

MAGNA_BASE  = os.getenv("MAGNA_BASE",  "https://magnaabogados.com/api/scraper")
MAGNA_TOKEN = os.getenv("MAGNA_TOKEN", "")

_HEADERS = {
    "x-scraper-token": MAGNA_TOKEN,
    "Content-Type":    "application/json",
}


def get_config() -> dict:
    """Lee la configuración actual del panel. Si falla, devuelve dict vacío."""
    try:
        r = requests.get(f"{MAGNA_BASE}/config", headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"No se pudo leer config de Magna: {e}")
        return {}


def get_procesos() -> list[str]:
    """Lee la lista de numProceso activos desde Magna. Devuelve lista vacía si falla."""
    try:
        r = requests.get(f"{MAGNA_BASE}/procesos", headers=_HEADERS, timeout=30)
        r.raise_for_status()
        return r.json().get("procesos", [])
    except Exception as e:
        log.error(f"No se pudo leer procesos de Magna: {e}")
        return []


def crear_ejecucion(tipo: str = "automatica", iniciado_por: str = "scheduler") -> int | None:
    try:
        r = requests.post(
            f"{MAGNA_BASE}/ejecuciones",
            json={"tipo": tipo, "iniciado_por": iniciado_por},
            headers=_HEADERS, timeout=15
        )
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        log.error(f"No se pudo crear ejecución: {e}")
        return None


def actualizar_ejecucion(id_ejec: int, **stats) -> None:
    if not id_ejec:
        return
    try:
        r = requests.put(
            f"{MAGNA_BASE}/ejecuciones/{id_ejec}",
            json=stats,
            headers=_HEADERS, timeout=15
        )
        r.raise_for_status()
    except Exception as e:
        log.error(f"No se pudo actualizar ejecución {id_ejec}: {e}")
