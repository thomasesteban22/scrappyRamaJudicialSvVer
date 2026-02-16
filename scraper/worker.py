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
from .logger import log  # ← IMPORTAR NUESTRO LOGGER

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
        # Solo log en archivo, no en consola
        log.debug(f"Screenshot guardado: {step_name}")
    except Exception as e:
        log.error(f"Error guardando debug {step_name}: {e}")


def worker_task(numero, driver, results, actes, errors, lock):
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx

    # Título del proceso en consola (más limpio)
    log.separador()
    log.progreso(f"[{idx}/{total}] {numero}")
    log.separador()

    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)
    log.debug(f"Fecha corte: {cutoff}")  # Solo al archivo

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
            log.debug("Campo de texto encontrado")  # Solo archivo
        except TimeoutException:
            log.error("No se encontró el campo de texto")
            save_debug_info(driver, numero, "02_error_no_input")
            raise Exception("Campo de texto no encontrado")

        # ========== PASO 4: INGRESAR EL NÚMERO DE RADICACIÓN ==========
        log.accion("Ingresando número...")

        # Limpiar campo primero
        input_field.clear()
        time.sleep(0.5)

        # Ingresar número carácter por carácter
        for char in str(numero):
            input_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.1))

        # Verificar que se ingresó correctamente
        entered_value = input_field.get_attribute("value")
        log.debug(f"Número ingresado: {entered_value}")  # Solo archivo

        # Buscar el contador para verificar
        try:
            counter = driver.find_element(By.XPATH, "//div[contains(@class, 'v-counter')]")
            counter_text = counter.text
            log.debug(f"Contador: {counter_text}")  # Solo archivo
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
            log.debug("Click en Consultar ejecutado")  # Solo archivo

        except Exception as e:
            log.error(f"Error haciendo click: {e}")
            try:
                form = driver.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                log.debug("Submit del formulario ejecutado")  # Solo archivo
            except:
                raise

        # ========== PASO 7: ESPERAR RESULTADOS ==========
        log.accion("Esperando resultados...")
        time.sleep(15)

        save_debug_info(driver, numero, "04_despues_consultar")

        # ========== PASO 8: BUSCAR TABLA DE RESULTADOS ==========
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//table"))
            )

            tables = driver.find_elements(By.XPATH, "//table")
            log.debug(f"Encontradas {len(tables)} tablas")  # Solo archivo

            # Buscar tabla con resultados
            for table in tables:
                try:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        log.proceso(f"Resultados encontrados")  # En consola
                        log.debug(f"Tabla con {len(rows)} filas")  # Solo archivo
                        save_debug_info(driver, numero, "05_tabla_resultados")

                        # Extraer datos de la primera fila
                        cells = rows[0].find_elements(By.TAG_NAME, "td")

                        if len(cells) >= 3:
                            # Número de radicación
                            try:
                                num_btn = cells[1].find_element(By.TAG_NAME, "button")
                                proceso_num = num_btn.text.strip()
                            except:
                                proceso_num = cells[1].text.strip()
                            log.debug(f"Proceso: {proceso_num}")  # Solo archivo

                            # Fecha de última actuación
                            try:
                                fecha_btn = cells[2].find_element(By.TAG_NAME, "button")
                                fecha_text = fecha_btn.text.strip()
                                log.proceso(f"Fecha: {fecha_text}")  # En consola

                                # Parsear fecha
                                fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()

                                if fecha_obj >= cutoff:
                                    log.exito("✓ DENTRO del período")  # En consola

                                    # Hacer click en la fecha
                                    driver.execute_script("arguments[0].click();", fecha_btn)
                                    time.sleep(8)

                                    save_debug_info(driver, numero, "06_click_fecha")

                                    # ========== PASO 9: EXTRAER ACTUACIONES ==========
                                    try:
                                        act_tables = driver.find_elements(By.XPATH, "//table")
                                        for act_table in act_tables:
                                            act_rows = act_table.find_elements(By.XPATH, ".//tbody//tr")
                                            if len(act_rows) > 1:
                                                log.proceso(f"Extrayendo actuaciones...")  # En consola
                                                log.debug(f"Encontradas {len(act_rows) - 1} actuaciones")  # Archivo

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
                                                                log.debug(f"✅ {act_fecha}: {act_nombre[:50]}...")  # Archivo
                                                        except:
                                                            continue
                                                break
                                    except Exception as e:
                                        log.error(f"Error extrayendo actuaciones: {e}")

                                    # Volver
                                    driver.back()
                                    time.sleep(5)
                                else:
                                    log.proceso("⏭️ Fuera de período")  # En consola
                            except Exception as e:
                                log.debug(f"No se pudo extraer fecha: {e}")  # Solo archivo
                        break
                except:
                    continue

        except TimeoutException:
            log.advertencia("No se encontraron resultados")  # En consola
            save_debug_info(driver, numero, "05_sin_resultados")

        # ========== PASO 10: FINALIZAR ==========
        with lock:
            results.append((numero, driver.current_url))

        log.exito("Proceso completado")  # En consola
        save_debug_info(driver, numero, "99_completado")

    except Exception as e:
        log.error(f"Error: {str(e)[:200]}")  # En consola
        save_debug_info(driver, numero, "99_error")
        with lock:
            errors.append((numero, str(e)[:200]))
        raise