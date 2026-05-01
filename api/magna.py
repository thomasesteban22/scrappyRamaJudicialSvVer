"""Cliente para la API de Magna (Node.js en Hostinger)."""
import os
import requests
from typing import Optional

MAGNA_BASE  = os.getenv('MAGNA_BASE', 'https://magnaabogados.com/api/scraper')
MAGNA_TOKEN = os.getenv('MAGNA_TOKEN', '')

_HEADERS = {
    "x-scraper-token": MAGNA_TOKEN,
    "Content-Type":    "application/json"
}


def _url(path: str) -> str:
    return f"{MAGNA_BASE}{path}"


def get_config() -> dict:
    r = requests.get(_url("/config"), headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def get_procesos() -> list[str]:
    r = requests.get(_url("/procesos"), headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("procesos", [])


def crear_ejecucion(tipo: str, iniciado_por: str) -> int:
    r = requests.post(
        _url("/ejecuciones"),
        json={"tipo": tipo, "iniciado_por": iniciado_por},
        headers=_HEADERS,
        timeout=15
    )
    r.raise_for_status()
    return r.json()["id"]


def actualizar_ejecucion(id_ejec: int, **stats) -> None:
    r = requests.put(
        _url(f"/ejecuciones/{id_ejec}"),
        json=stats,
        headers=_HEADERS,
        timeout=15
    )
    r.raise_for_status()


def enviar_actuaciones(actuaciones: list[dict]) -> dict:
    r = requests.post(
        _url("/actuaciones"),
        json={"actuaciones": actuaciones},
        headers=_HEADERS,
        timeout=60
    )
    r.raise_for_status()
    return r.json()
