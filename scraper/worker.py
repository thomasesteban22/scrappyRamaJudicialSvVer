# scraper/worker.py
import time
import random
import itertools
import os
import json
from datetime import date, timedelta, datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import DIAS_BUSQUEDA, DEBUG_SCRAPER
from .logger import log

# ── Directorios de debug ──────────────────────────────────────────────────────
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")
RESPONSE_DIR = os.path.join(DEBUG_DIR, "responses")
if DEBUG_SCRAPER:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)
    os.makedirs(RESPONSE_DIR, exist_ok=True)

process_counter = itertools.count(1)
TOTAL_PROCESSES = 0

# ── Configuración ─────────────────────────────────────────────────────────────
API_BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
WEB_BASE = "https://consultaprocesos.ramajudicial.gov.co"
WEB_URL  = f"{WEB_BASE}/Procesos/NumeroRadicacion"


# ── Helpers ───────────────────────────────────────────────────────────────────

def human_delay(min_s: float = 0.8, max_s: float = 2.5):
    time.sleep(random.uniform(min_s, max_s))


def save_debug_info(driver, numero, step_name):
    if not DEBUG_SCRAPER:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        driver.save_screenshot(os.path.join(SCREENSHOT_DIR, f"{numero}_{step_name}_{timestamp}.png"))
        with open(os.path.join(HTML_DIR, f"{numero}_{step_name}_{timestamp}.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception as e:
        log.debug(f"Error guardando debug {step_name}: {e}")


def save_debug_response(data, nombre: str):
    if not DEBUG_SCRAPER:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESPONSE_DIR, f"{nombre}_{timestamp}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.debug(f"Response guardada: {nombre}")
    except Exception as e:
        log.debug(f"Error guardando response: {e}")


def fetch_via_chrome(driver, url: str) -> dict | None:
    """
    Ejecuta un fetch() directamente dentro de Chrome usando JavaScript.
    La request sale con el fingerprint TLS real del navegador y todas
    sus cookies — el servidor no puede distinguirlo de un usuario real.
    """
    script = """
    const url = arguments[0];
    const callback = arguments[1];
    fetch(url, {
        method: 'GET',
        headers: {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7',
        },
        credentials: 'include'
    })
    .then(r => {
        if (!r.ok) {
            callback({error: r.status, message: r.statusText});
            return;
        }
        return r.json();
    })
    .then(data => callback({ok: true, data: data}))
    .catch(e => callback({error: 0, message: e.toString()}));
    """
    try:
        result = driver.execute_async_script(script, url)
        if result and result.get("ok"):
            return result["data"]
        else:
            log.error(f"fetch_via_chrome error: {result}")
            return None
    except Exception as e:
        log.error(f"Error en fetch_via_chrome: {e}")
        return None


def api_get_procesos(driver, numero: str, pagina: int = 1) -> dict | None:
    url = f"{API_BASE}/Procesos/Consulta/NumeroRadicacion?numero={numero}&SoloActivos=false&pagina={pagina}"
    return fetch_via_chrome(driver, url)


def api_get_actuaciones(driver, id_proceso: int, pagina: int = 1) -> dict | None:
    url = f"{API_BASE}/Proceso/Actuaciones/{id_proceso}?pagina={pagina}"
    return fetch_via_chrome(driver, url)


def warm_up_session(driver) -> bool:
    """
    Navega a la página principal para que Chrome establezca
    cookies de sesión y el sitio reconozca la IP como válida.
    """
    try:
        log.debug("Navegando a la página principal...")
        driver.get(WEB_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
        )
        human_delay(2.0, 4.0)
        log.debug("Sesión establecida")
        return True
    except Exception as e:
        log.error(f"Error calentando sesión: {e}")
        return False


# ── Task principal ────────────────────────────────────────────────────────────

def worker_task(numero, driver, results, actes, errors, lock):
    """
    Flujo:
      1. Chrome navega a la página (warm-up de sesión, solo 1 vez)
      2. fetch() desde JavaScript en el contexto del navegador llama a la API
         → misma IP, mismo fingerprint TLS, mismas cookies → sin 403
      3. Filtramos actuaciones dentro del período
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

            # ── 1. Warm-up solo en primer intento ────────────────────────────
            if attempt == 0:
                if not warm_up_session(driver):
                    raise Exception("No se pudo establecer sesión en Chrome")
                save_debug_info(driver, numero, f"01_warmed_a{attempt}")

            # ── 2. Consultar procesos desde el contexto del navegador ─────────
            log.debug(f"Consultando procesos para {numero}...")
            data = api_get_procesos(driver, str(numero))

            if data is None:
                log.advertencia("Sin respuesta, renovando sesión...")
                warm_up_session(driver)
                raise Exception("API sin respuesta — reintentando")

            save_debug_response(data, f"{numero}_procesos")

            procesos = data.get("procesos", [])
            if not procesos:
                log.proceso("Sin resultados para este número")
                break

            log.proceso(f"Procesos encontrados: {len(procesos)}")

            # ── 3. Revisar actuaciones por proceso ────────────────────────────
            for proceso in procesos:
                id_proceso   = proceso.get("idProceso")
                llave        = proceso.get("llaveProceso", str(numero))
                fecha_ultima = proceso.get("fechaUltimaActuacion", "")

                # Filtro rápido por fecha
                try:
                    fecha_ultima_obj = datetime.fromisoformat(fecha_ultima).date()
                except Exception:
                    fecha_ultima_obj = None

                if fecha_ultima_obj and fecha_ultima_obj < cutoff:
                    log.proceso(f"⏭️  {llave}: última actuación {fecha_ultima_obj} — fuera del período")
                    continue

                log.proceso(f"✓ {llave}: descargando actuaciones (idProceso={id_proceso})")
                human_delay(0.5, 1.5)

                # ── 4. Consultar actuaciones ──────────────────────────────────
                act_data = api_get_actuaciones(driver, id_proceso)
                if act_data is None:
                    log.advertencia(f"No se pudieron obtener actuaciones para {llave}")
                    continue

                save_debug_response(act_data, f"{numero}_{id_proceso}_actuaciones")

                actuaciones = (
                    act_data.get("actuaciones")
                    or act_data.get("Actuaciones")
                    or []
                )
                log.debug(f"Total actuaciones: {len(actuaciones)}")

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

            break  # Éxito

        except Exception as e:
            log.error(f"Error en intento {attempt+1}: {e}")
            if attempt == max_retries - 1:
                with lock:
                    errors.append((numero, str(e)[:200]))
                log.error(f"❌ {numero} fallido tras {max_retries} intentos")
                return
            wait_time = 10 * (attempt + 1)
            log.info(f"Esperando {wait_time}s antes de reintentar...")
            time.sleep(wait_time)

    with lock:
        results.append((numero, WEB_URL))
    log.exito("Proceso completado")