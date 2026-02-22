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

# Dominio esperado en driver.current_url para que CORS permita el fetch
EXPECTED_DOMAIN = "consultaprocesos.ramajudicial.gov.co"


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
        log.debug(f"Debug guardado: {step_name}")
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


def ensure_on_site(driver) -> bool:
    """
    Verifica que Chrome esté en el dominio correcto.
    Si no, navega a la página principal y espera que cargue.
    Esto es crítico para que el fetch() no falle por CORS.
    """
    current = driver.current_url
    if EXPECTED_DOMAIN in current:
        log.debug(f"Ya en dominio correcto: {current[:60]}")
        return True

    log.debug(f"Fuera del dominio ({current[:40]}...) — navegando...")
    try:
        driver.get(WEB_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
        )
        human_delay(2.0, 3.5)
        log.debug(f"Ahora en: {driver.current_url[:60]}")
        return True
    except Exception as e:
        log.error(f"Error navegando al sitio: {e}")
        return False


def fetch_api(driver, url: str) -> dict | None:
    """
    Ejecuta fetch() desde el contexto JavaScript de Chrome.
    IMPORTANTE: Chrome debe estar en el dominio consultaprocesos.ramajudicial.gov.co
    para que el servidor CORS permita la request al puerto 448.
    """
    # Garantizar que estamos en el dominio correcto antes de hacer el fetch
    if not ensure_on_site(driver):
        return None

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
    .then(data => {
        if (data !== undefined) callback({ok: true, data: data});
    })
    .catch(e => callback({error: 0, message: e.toString()}));
    """
    try:
        # Timeout generoso para el script async
        driver.set_script_timeout(45)
        result = driver.execute_async_script(script, url)
        if result and result.get("ok"):
            return result["data"]
        log.error(f"fetch_api error en {url}: {result}")
        return None
    except Exception as e:
        log.error(f"Error ejecutando fetch_api: {e}")
        return None


def api_get_procesos(driver, numero: str, pagina: int = 1) -> dict | None:
    url = f"{API_BASE}/Procesos/Consulta/NumeroRadicacion?numero={numero}&SoloActivos=false&pagina={pagina}"
    log.debug(f"GET procesos: {numero}")
    return fetch_api(driver, url)


def api_get_actuaciones(driver, id_proceso: int, pagina: int = 1) -> dict | None:
    url = f"{API_BASE}/Proceso/Actuaciones/{id_proceso}?pagina={pagina}"
    log.debug(f"GET actuaciones: idProceso={id_proceso}")
    return fetch_api(driver, url)


# ── Task principal ────────────────────────────────────────────────────────────

def worker_task(numero, driver, results, actes, errors, lock):
    """
    Flujo:
      1. Garantizar que Chrome esté en consultaprocesos.ramajudicial.gov.co
      2. fetch() desde JS dentro del navegador → sin CORS, sin 403
      3. Filtrar actuaciones dentro del período de búsqueda
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

            # ── 1. Consultar procesos ─────────────────────────────────────────
            # ensure_on_site() se llama dentro de fetch_api automáticamente
            data = api_get_procesos(driver, str(numero))
            save_debug_info(driver, numero, f"01_after_fetch_a{attempt}")

            if data is None:
                raise Exception("API sin respuesta")

            save_debug_response(data, f"{numero}_procesos")

            procesos = data.get("procesos", [])
            if not procesos:
                log.proceso("Sin resultados para este número")
                break

            log.proceso(f"Procesos encontrados: {len(procesos)}")

            # ── 2. Revisar actuaciones por proceso ────────────────────────────
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

                log.proceso(f"✓ {llave}: descargando actuaciones (idProceso={id_proceso})")
                human_delay(0.5, 1.5)

                act_data = api_get_actuaciones(driver, id_proceso)
                if act_data is None:
                    log.advertencia(f"Sin actuaciones para {llave}")
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

                log.exito(f"{llave}: {encontradas} actuaciones en el período")

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