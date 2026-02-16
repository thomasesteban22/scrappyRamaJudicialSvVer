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
from .browser import is_page_maintenance, test_javascript, wait_for_tor_circuit
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
    """Guarda screenshot y HTML."""
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


def handle_network_modal(driver, numero):
    """
    Detecta y maneja el modal de error de red.
    Retorna True si se manejó un modal, False si no.
    """
    try:
        # Buscar modal activo
        modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-dialog--active')]")

        if modals:
            log.advertencia(f"Modal detectado para {numero}")
            save_debug_info(driver, numero, "modal_detectado")

            # Buscar cualquier botón dentro del modal
            buttons = modals[0].find_elements(By.XPATH, ".//button")
            if buttons:
                log.accion("Cerrando modal...")
                driver.execute_script("arguments[0].click();", buttons[0])
                time.sleep(3)

                # Reintentar la consulta
                log.accion("Reintentando consulta...")
                try:
                    consultar_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH,
                                                    "//button[.//span[contains(text(), 'Consultar')]]"
                                                    ))
                    )
                    driver.execute_script("arguments[0].click();", consultar_btn)
                    log.debug("Reintento de consulta ejecutado")
                    return True
                except:
                    pass
        return False
    except Exception as e:
        log.debug(f"Error manejando modal: {e}")
        return False


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
            # 1. Verificar si hay modal de error
            modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'v-dialog--active')]")
            if modals:
                return 'modal'

            # 2. Verificar si hay tabla de resultados
            tables = driver.find_elements(By.XPATH, "//table")
            if tables:
                # Verificar que la tabla tenga filas
                for table in tables:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        return 'success'

            # 3. Verificar si hay mensaje de "no se encontraron"
            no_results = driver.find_elements(By.XPATH,
                                              "//*[contains(text(), 'No se encontraron') or contains(text(), 'Sin resultados')]"
                                              )
            if no_results:
                return 'no_results'

            # 4. Verificar si hay indicadores de carga
            loading = driver.find_elements(By.XPATH,
                                           "//*[contains(@class, 'v-progress-circular')]"
                                           )
            if not loading:
                # Si no hay loading y no hay resultados, esperar un poco más
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

    try:
        # ========== PASO 1: VERIFICAR TOR ==========
        if not wait_for_tor_circuit(timeout=30):
            log.advertencia("TOR no listo, continuando...")

        # ========== PASO 2: CARGAR PÁGINA DE CONSULTA ==========
        log.accion("Cargando consulta...")
        driver.get("https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion")
        time.sleep(5)
        save_debug_info(driver, numero, "01_pagina_cargada")

        # ========== PASO 3: ESPERAR QUE EL CAMPO DE TEXTO ESTÉ DISPONIBLE ==========
        try:
            input_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
            )
            log.debug("Campo de texto encontrado")
        except TimeoutException:
            log.error("No se encontró el campo de texto")
            save_debug_info(driver, numero, "02_error_no_input")
            raise Exception("Campo de texto no encontrado")

        # ========== PASO 4: INGRESAR EL NÚMERO DE RADICACIÓN ==========
        log.accion("Ingresando número...")

        input_field.clear()
        time.sleep(0.5)

        for char in str(numero):
            input_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.1))

        entered_value = input_field.get_attribute("value")
        log.debug(f"Número ingresado: {entered_value}")

        try:
            counter = driver.find_element(By.XPATH, "//div[contains(@class, 'v-counter')]")
            log.debug(f"Contador: {counter.text}")
        except:
            pass

        save_debug_info(driver, numero, "03_numero_ingresado")
        time.sleep(random.uniform(1, 2))

        # ========== PASO 5: SELECCIONAR "TODOS LOS PROCESOS" ==========
        try:
            radio_buttons = driver.find_elements(By.XPATH,
                                                 "//div[contains(@class, 'v-radio')]//label"
                                                 )
            for radio in radio_buttons:
                if "Todos los Procesos" in radio.text:
                    log.accion("Opción: Todos los Procesos")
                    radio.click()
                    time.sleep(1)
                    break
        except Exception as e:
            log.debug(f"No se pudo seleccionar radio button: {e}")

        # ========== PASO 6: HACER CLICK EN CONSULTAR ==========
        log.accion("Consultando...")

        try:
            consultar_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                                            "//button[.//span[contains(text(), 'Consultar')]]"
                                            ))
            )
            driver.execute_script("arguments[0].click();", consultar_btn)
            log.debug("Click en Consultar ejecutado")

        except Exception as e:
            log.error(f"Error haciendo click: {e}")
            try:
                form = driver.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                log.debug("Submit del formulario ejecutado")
            except:
                raise

        # ========== PASO 7: ESPERAR RESULTADOS CON MANEJO DE MODAL ==========
        log.accion("Esperando resultados...")

        # Primer intento de espera
        result_status = wait_for_results(driver, timeout=45)

        # Si hay modal, manejarlo y reintentar
        if result_status == 'modal':
            log.advertencia("Modal de error detectado, intentando recuperación...")
            save_debug_info(driver, numero, "modal_error")

            if handle_network_modal(driver, numero):
                log.accion("Reintentando después de modal...")
                result_status = wait_for_results(driver, timeout=45)
            else:
                log.error("No se pudo recuperar del modal")
                raise Exception("Error de red no recuperable")

        save_debug_info(driver, numero, "04_despues_consultar")

        # ========== PASO 8: PROCESAR RESULTADOS SEGÚN EL ESTADO ==========
        if result_status == 'success':
            log.proceso("Resultados encontrados")

            tables = driver.find_elements(By.XPATH, "//table")

            for table in tables:
                try:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        log.debug(f"Tabla con {len(rows)} filas")
                        save_debug_info(driver, numero, "05_tabla_resultados")

                        cells = rows[0].find_elements(By.TAG_NAME, "td")

                        if len(cells) >= 3:
                            # Número de radicación
                            try:
                                num_btn = cells[1].find_element(By.TAG_NAME, "button")
                                proceso_num = num_btn.text.strip()
                            except:
                                proceso_num = cells[1].text.strip()
                            log.debug(f"Proceso: {proceso_num}")

                            # Fecha de última actuación
                            try:
                                fecha_btn = cells[2].find_element(By.TAG_NAME, "button")
                                fecha_text = fecha_btn.text.strip()
                                log.proceso(f"Fecha: {fecha_text}")

                                fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()

                                if fecha_obj >= cutoff:
                                    log.exito("✓ DENTRO del período")

                                    driver.execute_script("arguments[0].click();", fecha_btn)
                                    time.sleep(8)
                                    save_debug_info(driver, numero, "06_click_fecha")

                                    # Extraer actuaciones
                                    try:
                                        act_tables = driver.find_elements(By.XPATH, "//table")
                                        for act_table in act_tables:
                                            act_rows = act_table.find_elements(By.XPATH, ".//tbody//tr")
                                            if len(act_rows) > 1:
                                                log.proceso("Extrayendo actuaciones...")
                                                log.debug(f"Encontradas {len(act_rows) - 1} actuaciones")

                                                for row in act_rows[1:]:
                                                    act_cells = row.find_elements(By.TAG_NAME, "td")
                                                    if len(act_cells) >= 3:
                                                        act_fecha = act_cells[0].text.strip()
                                                        act_nombre = act_cells[1].text.strip()
                                                        act_anotacion = act_cells[2].text.strip()

                                                        try:
                                                            act_fecha_obj = datetime.strptime(act_fecha,
                                                                                              "%Y-%m-%d").date()
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
                                    except Exception as e:
                                        log.error(f"Error extrayendo actuaciones: {e}")

                                    driver.back()
                                    time.sleep(5)
                                else:
                                    log.proceso("⏭️ Fuera de período")
                            except Exception as e:
                                log.debug(f"No se pudo extraer fecha: {e}")
                        break
                except:
                    continue

        elif result_status == 'no_results':
            log.proceso("No hay resultados para este proceso")
            save_debug_info(driver, numero, "sin_resultados")

        elif result_status == 'timeout':
            log.advertencia("Timeout esperando resultados")
            save_debug_info(driver, numero, "timeout_resultados")

        # ========== PASO 9: FINALIZAR ==========
        with lock:
            results.append((numero, driver.current_url))

        log.exito("Proceso completado")
        save_debug_info(driver, numero, "99_completado")

    except Exception as e:
        log.error(f"Error: {str(e)[:200]}")
        save_debug_info(driver, numero, "99_error")
        with lock:
            errors.append((numero, str(e)[:200]))
        raise