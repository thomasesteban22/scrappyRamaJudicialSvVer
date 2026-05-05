# scraper/api_client.py
import requests
import os
from .logger import log

MAGNA_URL   = os.getenv('MAGNA_URL', 'https://magnaabogados.com/api/scraper/actuaciones')
MAGNA_TOKEN = os.getenv('MAGNA_TOKEN', 'token-scraper-magna-2026')


def enviar_actuaciones(actes: list, execution_id: int = None) -> dict:
    """
    Envia un lote de actuaciones a Magna.

    Args:
        actes: lista de tuplas (numProceso, fechaActuacion, actuacion, anotacion, url, fechaInicial)
        execution_id: ID de la ejecucion actual (opcional). Si se pasa, Magna guarda
                      el detalle de cada actuacion procesada en scraper_ejecucion_detalles.
    """
    if not actes:
        log.debug("Sin actuaciones para enviar")
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}

    payload = {
        "actuaciones": [
            {
                "numProceso":     numero,
                "fechaActuacion": fecha_actuacion,
                "fechaEstado":    fecha_inicial,
                "actuacion":      nombre[:100],
                "observacion":    anotacion,
                "etapa":          ""
            }
            for numero, fecha_actuacion, nombre, anotacion, _url, fecha_inicial in actes
        ]
    }

    if execution_id is not None:
        payload["execution_id"] = execution_id

    try:
        r = requests.post(
            MAGNA_URL,
            json=payload,
            headers={
                "x-scraper-token": MAGNA_TOKEN,
                "Content-Type":    "application/json"
            },
            timeout=60
        )
        r.raise_for_status()
        resultado = r.json()
        log.exito(
            f"Magna DB: {resultado.get('insertadas',0)} insertadas, "
            f"{resultado.get('duplicadas',0)} duplicadas, "
            f"{resultado.get('errores',0)} errores"
        )
        return resultado
    except Exception as e:
        log.error(f"Error enviando actuaciones a Magna: {e}")
        return {"insertadas": 0, "duplicadas": 0, "errores": 1}
