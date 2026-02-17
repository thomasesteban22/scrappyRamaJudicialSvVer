# scraper/worker.py
import time
import random
import itertools
import os
from datetime import date, timedelta, datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .config import DIAS_BUSQUEDA
from .browser import is_page_maintenance, test_javascript, handle_modal_error, renew_tor_circuit
from .logger import log

# Configuración
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

process_counter = itertools.count(1)
TOTAL_PROCESSES = 0


def save_debug_info(driver, numero, step_name):
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


def wait_for_results(driver, timeout=60):
    """
    Espera a que la página cargue resultados o muestre modal de error.
    Retorna:
        'success' - Resultados encontrados
        'no_results' - Mensaje de "no se encontraron"
        'modal' - Modal de error detectado
        'timeout' - Timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Modal activo
            modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-dialog--active')]")
            if modals:
                return 'modal'

            # Tablas de resultados
            tables = driver.find_elements(By.XPATH, "//table")
            if tables:
                for table in tables:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        return 'success'

            # Mensaje de "no se encontraron"
            no_results = driver.find_elements(By.XPATH,
                "//*[contains(text(), 'No se encontraron') or contains(text(), 'Sin resultados')]"
            )
            if no_results:
                return 'no_results'

            # Indicadores de carga
            loading = driver.find_elements(By.XPATH, "//*[contains(@class, 'v-progress-circular')]")
            if not loading:
                time.sleep(2)

        except Exception as e:
            log.debug(f"Error en wait_for_results: {e}")

        time.sleep(2)

    return 'timeout'


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

            # ========== CARGAR PÁGINA ==========
            log.accion("Cargando consulta...")
            driver.get("https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion")
            time.sleep(5)
            save_debug_info(driver, numero, f"01_pagina_cargada_a{attempt}")

            # ========== CAMPO DE TEXTO ==========
            input_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
            )
            input_field.clear()
            for char in str(numero):
                input_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.1))
            log.debug(f"Número ingresado: {numero}")
            try:
                counter = driver.find_element(By.XPATH, "//div[contains(@class, 'v-counter')]")
                log.debug(f"Contador: {counter.text}")
            except:
                pass
            save_debug_info(driver, numero, f"03_numero_ingresado_a{attempt}")
            time.sleep(random.uniform(1, 2))

            # ========== RADIO BUTTON ==========
            try:
                radio_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-radio')]//label")
                for radio in radio_buttons:
                    if "Todos los Procesos" in radio.text:
                        log.accion("Opción: Todos los Procesos")
                        radio.click()
                        time.sleep(1)
                        break
            except Exception as e:
                log.debug(f"No se pudo seleccionar radio: {e}")

            # ========== CLICK CONSULTAR ==========
            consultar_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Consultar')]]"))
            )
            driver.execute_script("arguments[0].click();", consultar_btn)
            log.accion("Consultando...")

            # ========== ESPERAR RESULTADOS ==========
            result_status = wait_for_results(driver, timeout=45)
            save_debug_info(driver, numero, f"04_despues_consultar_a{attempt}")

            if result_status == 'success':
                log.proceso("Resultados encontrados")
                # Procesar tabla
                tables = driver.find_elements(By.XPATH, "//table")
                for table in tables:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        log.debug(f"Tabla con {len(rows)} filas")
                        save_debug_info(driver, numero, f"05_tabla_resultados_a{attempt}")
                        cells = rows[0].find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 3:
                            # Número de radicación
                            try:
                                num_btn = cells[1].find_element(By.TAG_NAME, "button")
                                proceso_num = num_btn.text.strip()
                            except:
                                proceso_num = cells[1].text.strip()
                            log.debug(f"Proceso: {proceso_num}")

                            # Fecha
                            try:
                                fecha_btn = cells[2].find_element(By.TAG_NAME, "button")
                                fecha_text = fecha_btn.text.strip()
                                log.proceso(f"Fecha: {fecha_text}")
                                fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()

                                if fecha_obj >= cutoff:
                                    log.exito("✓ DENTRO del período")
                                    driver.execute_script("arguments[0].click();", fecha_btn)
                                    time.sleep(8)
                                    save_debug_info(driver, numero, f"06_click_fecha_a{attempt}")

                                    # Extraer actuaciones
                                    act_tables = driver.find_elements(By.XPATH, "//table")
                                    for act_table in act_tables:
                                        act_rows = act_table.find_elements(By.XPATH, ".//tbody//tr")
                                        if len(act_rows) > 1:
                                            log.proceso("Extrayendo actuaciones...")
                                            log.debug(f"Encontradas {len(act_rows)-1} actuaciones")
                                            for row in act_rows[1:]:
                                                act_cells = row.find_elements(By.TAG_NAME, "td")
                                                if len(act_cells) >= 3:
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
                                                    except:
                                                        continue
                                            break
                                    driver.back()
                                    time.sleep(5)
                                else:
                                    log.proceso("⏭️ Fuera de período")
                            except Exception as e:
                                log.debug(f"No se pudo extraer fecha: {e}")
                        break
                # Éxito, salir del bucle de reintentos
                break

            elif result_status == 'no_results':
                log.proceso("No hay resultados para este proceso")
                break

            elif result_status == 'modal':
                log.advertencia(f"Modal detectado en intento {attempt+1}")
                save_debug_info(driver, numero, f"modal_a{attempt}")
                # Intentar cerrar modal (por si acaso)
                handle_modal_error(driver, numero)
                # Renovar circuito TOR (o fallback)
                if renew_tor_circuit():
                    log.exito("Circuito TOR renovado, reintentando...")
                    continue  # Siguiente intento
                else:
                    log.error("No se pudo renovar circuito TOR, pero se intentará de todos modos")
                    # Aún así, reintentamos
                    continue

            elif result_status == 'timeout':
                log.advertencia("Timeout esperando resultados")
                if attempt == max_retries - 1:
                    raise Exception("Timeout después de reintentos")
                else:
                    if renew_tor_circuit():
                        log.exito("Circuito TOR renovado, reintentando...")
                        continue
                    else:
                        continue

        except Exception as e:
            log.error(f"Error en intento {attempt+1}: {e}")
            if attempt == max_retries - 1:
                raise
            else:
                if renew_tor_circuit():
                    log.exito("Circuito TOR renovado, reintentando...")
                    continue
                else:
                    continue

    # Registrar resultado final
    with lock:
        results.append((numero, driver.current_url))
    log.exito("Proceso completado")
    save_debug_info(driver, numero, "99_completado")