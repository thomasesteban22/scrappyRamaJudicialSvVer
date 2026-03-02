# scraper/worker.py
import time
import random
import itertools
import os
import json
from datetime import date, timedelta, datetime

from .config import DIAS_BUSQUEDA, DEBUG_SCRAPER
from .session_manager import api_get_procesos, api_get_actuaciones
from .logger import log

DEBUG_DIR    = os.path.join(os.getcwd(), "debug")
RESPONSE_DIR = os.path.join(DEBUG_DIR, "responses")
if DEBUG_SCRAPER:
    os.makedirs(RESPONSE_DIR, exist_ok=True)

process_counter = itertools.count(1)
TOTAL_PROCESSES = 0
WEB_URL = "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion"


def human_delay(min_s=0.5, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))


def save_debug_response(data, nombre):
    if not DEBUG_SCRAPER:
        return
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESPONSE_DIR, f"{nombre}_{ts}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.debug(f"Error guardando response: {e}")


def worker_task(numero, driver, results, actes, errors, lock):
    # driver se ignora — usamos session_manager con Bright Data
    idx   = next(process_counter)
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

            # ── Consultar procesos ────────────────────────────────────────────
            data = api_get_procesos(str(numero))
            if data is None:
                raise Exception("Sin respuesta de la API")

            save_debug_response(data, f"{numero}_procesos")
            procesos = data.get("procesos", [])

            if not procesos:
                log.proceso("Sin resultados")
                break

            log.proceso(f"Procesos: {len(procesos)}")

            # ── Iterar procesos ───────────────────────────────────────────────
            for proceso in procesos:
                id_proceso   = proceso.get("idProceso")
                llave        = proceso.get("llaveProceso", str(numero))
                fecha_ultima = proceso.get("fechaUltimaActuacion", "")

                try:
                    fecha_ultima_obj = datetime.fromisoformat(fecha_ultima).date()
                except Exception:
                    fecha_ultima_obj = None

                if fecha_ultima_obj and fecha_ultima_obj < cutoff:
                    log.proceso(f"⏭️  {llave}: {fecha_ultima_obj} — fuera del período")
                    continue

                log.proceso(f"✓ {llave}: actuaciones (idProceso={id_proceso})")
                human_delay(0.3, 1.0)

                # ── Consultar actuaciones ─────────────────────────────────────
                act_data = api_get_actuaciones(id_proceso)
                if act_data is None:
                    log.advertencia(f"Sin actuaciones para {llave}")
                    continue

                save_debug_response(act_data, f"{numero}_{id_proceso}_actuaciones")
                actuaciones = act_data.get("actuaciones") or act_data.get("Actuaciones") or []
                log.debug(f"Actuaciones: {len(actuaciones)}")

                encontradas = 0
                for act in actuaciones:
                    try:
                        act_fecha_obj = datetime.fromisoformat(
                            act.get("fechaActuacion", "")
                        ).date()
                    except Exception:
                        continue
                    if act_fecha_obj >= cutoff:
                        with lock:
                            actes.append((
                                numero,
                                act_fecha_obj.isoformat(),
                                act.get("actuacion", "").strip(),
                                act.get("anotacion", "").strip(),
                                f"idProceso:{id_proceso}"
                            ))
                        encontradas += 1

                log.exito(f"{llave}: {encontradas} actuaciones en el período")

            break  # Éxito

        except Exception as e:
            log.error(f"Error en intento {attempt+1}: {e}")
            if attempt == max_retries - 1:
                with lock:
                    errors.append((numero, str(e)[:200]))
                return
            time.sleep(8 * (attempt + 1))

    with lock:
        results.append((numero, WEB_URL))
    log.exito("Proceso completado")