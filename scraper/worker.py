# scraper/worker.py
import time
import random
import itertools
import os
import requests as req_lib
from datetime import date, timedelta, datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .config import DIAS_BUSQUEDA, DEBUG_SCRAPER
from .browser import handle_modal_error
from .logger import log

# ── Directorios de debug ──────────────────────────────────────────────────────
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")
if DEBUG_SCRAPER:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)

process_counter = itertools.count(1)
TOTAL_PROCESSES = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def save_debug_info(driver, numero, step_name):
    """Guarda screenshot y HTML solo si DEBUG_SCRAPER está activado."""
    if not DEBUG_SCRAPER:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss_path = os.path.join(SCREENSHOT_DIR, f"{numero}_{step_name}_{timestamp}.png")
    html_path = os.path.join(HTML_DIR, f"{numero}_{step_name}_{timestamp}.html")
    try:
        driver.save_screenshot(ss_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log.debug(f"Screenshot guardado: {step_name}")
    except Exception as e:
        log.error(f"Error guardando debug {step_name}: {e}")


def human_delay(min_s=1.0, max_s=3.5):
    """Pausa aleatoria para simular comportamiento humano."""
    time.sleep(random.uniform(min_s, max_s))


def wait_for_results(driver, timeout=60):
    """
    Espera a que la página cargue resultados o muestre modal.
    Retorna: 'success', 'no_results', 'modal', 'timeout'
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Modal activo (bloqueo / error del sitio)
            modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-dialog--active')]")
            if modals:
                return 'modal'

            # Tablas de resultados
            tables = driver.find_elements(By.XPATH, "//table")
            for table in tables:
                rows = table.find_elements(By.XPATH, ".//tbody//tr")
                if rows:
                    return 'success'

            # Mensaje de sin resultados
            no_results = driver.find_elements(By.XPATH,
                "//*[contains(text(), 'No se encontraron') or contains(text(), 'Sin resultados')]")
            if no_results:
                return 'no_results'

        except Exception as e:
            log.debug(f"Error en wait_for_results: {e}")

        time.sleep(2)

    return 'timeout'


# ── Task principal ────────────────────────────────────────────────────────────

def worker_task(numero, driver, results, actes, errors, lock):
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

            # ── Cargar página ─────────────────────────────────────────────────
            driver.get("https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion")
            human_delay(3, 6)
            save_debug_info(driver, numero, f"01_pagina_cargada_a{attempt}")

            # ── Ingresar número ───────────────────────────────────────────────
            input_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
            )
            input_field.clear()
            human_delay(0.3, 0.8)
            for char in str(numero):
                input_field.send_keys(char)
                time.sleep(random.uniform(0.08, 0.18))
            log.debug(f"Número ingresado: {numero}")

            try:
                counter = driver.find_element(By.XPATH, "//div[contains(@class, 'v-counter')]")
                log.debug(f"Contador: {counter.text}")
            except Exception:
                pass

            save_debug_info(driver, numero, f"02_numero_ingresado_a{attempt}")
            human_delay(1, 2)

            # ── Radio "Todos los Procesos" ─────────────────────────────────────
            try:
                radios = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-radio')]//label")
                for r in radios:
                    if "Todos los Procesos" in r.text:
                        log.accion("Seleccionando: Todos los Procesos")
                        r.click()
                        human_delay(0.5, 1.2)
                        break
            except Exception as e:
                log.debug(f"No se pudo seleccionar radio: {e}")

            # ── Click en Consultar ─────────────────────────────────────────────
            consultar_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Consultar')]]"))
            )
            human_delay(0.5, 1.5)
            driver.execute_script("arguments[0].click();", consultar_btn)
            log.accion("Consultando...")

            # ── Esperar resultados ─────────────────────────────────────────────
            result_status = wait_for_results(driver, timeout=45)
            save_debug_info(driver, numero, f"03_despues_consultar_a{attempt}")

            # ── Procesar resultado ─────────────────────────────────────────────
            if result_status == 'success':
                log.proceso("Resultados encontrados")
                tables = driver.find_elements(By.XPATH, "//table")
                for table in tables:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if not rows:
                        continue

                    log.debug(f"Tabla con {len(rows)} filas")
                    save_debug_info(driver, numero, f"04_tabla_resultados_a{attempt}")

                    cells = rows[0].find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        try:
                            fecha_btn = cells[2].find_element(By.TAG_NAME, "button")
                            fecha_text = fecha_btn.text.strip()
                            log.proceso(f"Última actuación: {fecha_text}")
                            fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()

                            if fecha_obj >= cutoff:
                                log.exito("✓ DENTRO del período")
                                driver.execute_script("arguments[0].click();", fecha_btn)
                                human_delay(6, 10)
                                save_debug_info(driver, numero, f"05_click_fecha_a{attempt}")

                                # Extraer actuaciones del detalle
                                act_tables = driver.find_elements(By.XPATH, "//table")
                                for act_table in act_tables:
                                    act_rows = act_table.find_elements(By.XPATH, ".//tbody//tr")
                                    if len(act_rows) <= 1:
                                        continue

                                    log.proceso(f"Extrayendo {len(act_rows)-1} actuaciones...")
                                    for row in act_rows[1:]:
                                        act_cells = row.find_elements(By.TAG_NAME, "td")
                                        if len(act_cells) < 3:
                                            continue
                                        act_fecha = act_cells[0].text.strip()
                                        act_nombre = act_cells[1].text.strip()
                                        act_anotacion = act_cells[2].text.strip()
                                        try:
                                            act_fecha_obj = datetime.strptime(act_fecha, "%Y-%m-%d").date()
                                            if act_fecha_obj >= cutoff:
                                                with lock:
                                                    actes.append((
                                                        numero,
                                                        act_fecha,
                                                        act_nombre,
                                                        act_anotacion,
                                                        driver.current_url
                                                    ))
                                                log.debug(f"✅ {act_fecha}: {act_nombre[:50]}...")
                                        except Exception:
                                            continue
                                    break

                                driver.back()
                                human_delay(4, 7)
                            else:
                                log.proceso("⏭️ Fuera del período, se omite")

                        except Exception as e:
                            log.debug(f"No se pudo extraer fecha: {e}")
                    break  # Solo procesa la primera tabla con filas

                break  # Éxito → salir del bucle de reintentos

            elif result_status == 'no_results':
                log.proceso("Sin resultados para este número")
                break

            elif result_status == 'modal':
                log.advertencia(f"Modal detectado en intento {attempt+1}")
                save_debug_info(driver, numero, f"modal_a{attempt}")
                handle_modal_error(driver, numero)
                # Espera progresiva antes de reintentar
                wait_time = 5 * (attempt + 1)
                log.info(f"Esperando {wait_time}s antes de reintentar...")
                time.sleep(wait_time)
                continue

            elif result_status == 'timeout':
                log.advertencia(f"Timeout en intento {attempt+1}")
                if attempt == max_retries - 1:
                    raise Exception("Timeout persistente después de todos los reintentos")
                wait_time = 10 * (attempt + 1)
                log.info(f"Esperando {wait_time}s antes de reintentar...")
                time.sleep(wait_time)
                continue

        except Exception as e:
            log.error(f"Error en intento {attempt+1}: {e}")
            if attempt == max_retries - 1:
                raise
            wait_time = 8 * (attempt + 1)
            log.info(f"Esperando {wait_time}s antes de reintentar...")
            time.sleep(wait_time)
            continue

    with lock:
        results.append((numero, driver.current_url))
    log.exito("Proceso completado")
    save_debug_info(driver, numero, "99_completado")