# scraper/worker.py
import time
import random
import itertools
import os
import requests
from datetime import date, timedelta, datetime

from .config import DIAS_BUSQUEDA, DEBUG_SCRAPER
from .logger import log

# ── Directorios de debug ──────────────────────────────────────────────────────
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
RESPONSE_DIR = os.path.join(DEBUG_DIR, "responses")
if DEBUG_SCRAPER:
    os.makedirs(RESPONSE_DIR, exist_ok=True)

process_counter = itertools.count(1)
TOTAL_PROCESSES = 0

# ── Configuración de la API ───────────────────────────────────────────────────
API_BASE   = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
WEB_BASE   = "https://consultaprocesos.ramajudicial.gov.co"

HEADERS = {
    "Accept":              "application/json, text/plain, */*",
    "Accept-Language":     "es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding":     "gzip, deflate, br",
    "Origin":              WEB_BASE,
    "Referer":             f"{WEB_BASE}/",
    "Sec-Fetch-Dest":      "empty",
    "Sec-Fetch-Mode":      "cors",
    "Sec-Fetch-Site":      "same-site",
    "User-Agent":          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}


# ── API calls ─────────────────────────────────────────────────────────────────

def api_get_procesos(numero: str, pagina: int = 1) -> dict | None:
    """
    GET /api/v2/Procesos/Consulta/NumeroRadicacion
        ?numero=<NUM>&SoloActivos=false&pagina=1
    """
    url = f"{API_BASE}/Procesos/Consulta/NumeroRadicacion"
    params = {
        "numero":      numero,
        "SoloActivos": "false",
        "pagina":      pagina,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Error consultando procesos para {numero}: {e}")
        return None


def api_get_actuaciones(id_proceso: int, pagina: int = 1) -> dict | None:
    """
    GET /api/v2/Proceso/Actuaciones/<idProceso>?pagina=1
    Confirmado en DevTools: /api/v2/Proceso/Actuaciones/28775804?pagina=1
    """
    url = f"{API_BASE}/Proceso/Actuaciones/{id_proceso}"
    params = {"pagina": pagina}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Error consultando actuaciones para idProceso {id_proceso}: {e}")
        return None


def save_debug_response(data: dict, nombre: str):
    """Guarda la respuesta JSON si DEBUG_SCRAPER está activo."""
    if not DEBUG_SCRAPER:
        return
    import json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESPONSE_DIR, f"{nombre}_{timestamp}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.debug(f"Response guardada: {nombre}")
    except Exception as e:
        log.error(f"Error guardando response debug: {e}")


def human_delay(min_s: float = 0.5, max_s: float = 2.0):
    """Pausa aleatoria para no saturar el servidor."""
    time.sleep(random.uniform(min_s, max_s))


# ── Task principal ────────────────────────────────────────────────────────────

def worker_task(numero, driver, results, actes, errors, lock):
    """
    Consulta un proceso judicial vía API REST directamente.
    El parámetro `driver` se mantiene por compatibilidad con main.py
    pero ya no se usa — Selenium ya no es necesario.

    Flujo equivalente al manual:
      1. GET procesos  → tabla con lista de procesos
      2. Filtro por fechaUltimaActuacion >= cutoff
      3. GET actuaciones/{idProceso} → tabla de actuaciones
      4. Filtro actuaciones dentro del período
    """
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx

    log.separador()
    log.progreso(f"[{idx}/{total}] {numero}")
    log.separador()

    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)
    log.debug(f"Fecha corte: {cutoff}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            log.accion(f"Intento {attempt+1}/{max_retries}")
            human_delay(0.5, 1.5)

            # ── 1. Consultar lista de procesos ────────────────────────────────
            data = api_get_procesos(str(numero))
            if data is None:
                raise Exception("Sin respuesta de la API de procesos")

            save_debug_response(data, f"{numero}_procesos")

            procesos = data.get("procesos", [])
            if not procesos:
                log.proceso("Sin resultados para este número")
                break

            log.proceso(f"Procesos encontrados: {len(procesos)}")

            # ── 2. Iterar procesos y revisar actuaciones ──────────────────────
            for proceso in procesos:
                id_proceso   = proceso.get("idProceso")
                llave        = proceso.get("llaveProceso", str(numero))
                fecha_ultima = proceso.get("fechaUltimaActuacion", "")

                # Filtro rápido: si la última actuación ya está fuera del
                # período, no tiene sentido descargar el detalle
                try:
                    fecha_ultima_obj = datetime.fromisoformat(fecha_ultima).date()
                except Exception:
                    fecha_ultima_obj = None

                if fecha_ultima_obj and fecha_ultima_obj < cutoff:
                    log.proceso(f"⏭️  {llave}: última actuación {fecha_ultima_obj} — fuera del período")
                    continue

                log.proceso(f"✓ {llave}: descargando actuaciones (idProceso={id_proceso})")
                human_delay(0.3, 1.0)

                # ── 3. Consultar actuaciones del proceso ──────────────────────
                act_data = api_get_actuaciones(id_proceso)
                if act_data is None:
                    log.advertencia(f"No se pudieron obtener actuaciones para {llave}")
                    continue

                save_debug_response(act_data, f"{numero}_{id_proceso}_actuaciones")

                # La API puede devolver la lista bajo distintas claves
                # según la versión — intentamos las más comunes
                actuaciones = (
                    act_data.get("actuaciones")
                    or act_data.get("Actuaciones")
                    or []
                )
                log.debug(f"Total actuaciones recibidas: {len(actuaciones)}")

                encontradas = 0
                for act in actuaciones:
                    act_fecha_str = act.get("fechaActuacion", "")
                    act_nombre    = act.get("actuacion", "").strip()
                    act_anotacion = act.get("anotacion", "").strip()

                    try:
                        act_fecha_obj = datetime.fromisoformat(act_fecha_str).date()
                    except Exception:
                        continue

                    if act_fecha_obj >= cutoff:
                        with lock:
                            actes.append((
                                numero,
                                act_fecha_obj.isoformat(),
                                act_nombre,
                                act_anotacion,
                                f"{API_BASE}/Proceso/Actuaciones/{id_proceso}"
                            ))
                        encontradas += 1
                        log.debug(f"✅ {act_fecha_obj}: {act_nombre[:60]}...")

                log.exito(f"{llave}: {encontradas} actuaciones dentro del período")

            break  # Éxito → salir del bucle de reintentos

        except Exception as e:
            log.error(f"Error en intento {attempt+1}: {e}")
            if attempt == max_retries - 1:
                with lock:
                    errors.append((numero, str(e)[:200]))
                log.error(f"❌ {numero} fallido tras {max_retries} intentos")
                return
            wait_time = 8 * (attempt + 1)
            log.info(f"Esperando {wait_time}s antes de reintentar...")
            time.sleep(wait_time)

    with lock:
        results.append((numero, f"{API_BASE}/Procesos/Consulta/NumeroRadicacion"))
    log.exito("Proceso completado")