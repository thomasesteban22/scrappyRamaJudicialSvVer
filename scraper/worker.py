# scraper/worker.py - VERSIÓN CORREGIDA

import time
import random
import logging
import itertools
import os
from datetime import date, timedelta, datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .config import DIAS_BUSQUEDA
from .browser import is_page_maintenance, test_javascript, wait_for_tor_circuit

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
        logging.info(f"📸 {step_name}: Screenshot guardado")
    except Exception as e:
        logging.error(f"Error guardando debug {step_name}: {e}")


def worker_task(numero, driver, results, actes, errors, lock):
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx

    logging.info(f"\n{'=' * 60}")
    logging.info(f"🚀 [{idx}/{total}] INICIANDO PROCESO {numero}")
    logging.info(f"{'=' * 60}")

    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:
        # ========== PASO 1: VERIFICAR TOR ==========
        if not wait_for_tor_circuit(timeout=30):
            logging.warning(f"[{idx}/{total}] ⚠️ TOR no listo, continuando...")

        # ========== PASO 2: CARGAR PÁGINA DE CONSULTA ==========
        logging.info(f"[{idx}/{total}] 🌐 Cargando página de consulta...")
        driver.get("https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion")
        time.sleep(5)
        save_debug_info(driver, numero, "01_pagina_cargada")

        # ========== PASO 3: ESPERAR QUE EL CAMPO DE TEXTO ESTÉ DISPONIBLE ==========
        try:
            # Esperar explícitamente por el campo de texto
            input_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
            )
            logging.info(f"[{idx}/{total}] ✅ Campo de texto encontrado")
        except TimeoutException:
            logging.error(f"[{idx}/{total}] ❌ No se encontró el campo de texto")
            save_debug_info(driver, numero, "02_error_no_input")
            raise Exception("Campo de texto no encontrado")

        # ========== PASO 4: INGRESAR EL NÚMERO DE RADICACIÓN ==========
        logging.info(f"[{idx}/{total}] ✍️ Ingresando número: {numero}")

        # Limpiar campo primero
        input_field.clear()
        time.sleep(0.5)

        # Ingresar número carácter por carácter (simula escritura humana)
        for char in str(numero):
            input_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.1))

        # Verificar que se ingresó correctamente
        entered_value = input_field.get_attribute("value")
        logging.info(f"[{idx}/{total}] ✅ Número ingresado: {entered_value}")

        # Buscar el contador para verificar
        try:
            counter = driver.find_element(By.XPATH, "//div[contains(@class, 'v-counter')]")
            counter_text = counter.text
            logging.info(f"[{idx}/{total}] 📊 Contador: {counter_text}")
        except:
            pass

        save_debug_info(driver, numero, "03_numero_ingresado")

        # Pequeña pausa antes de hacer click
        time.sleep(random.uniform(1, 2))

        # ========== PASO 5: SELECCIONAR "TODOS LOS PROCESOS" ==========
        try:
            # Buscar el radio button de "Todos los Procesos"
            radio_buttons = driver.find_elements(By.XPATH,
                                                 "//div[contains(@class, 'v-radio')]//label"
                                                 )

            for radio in radio_buttons:
                if "Todos los Procesos" in radio.text:
                    logging.info(f"[{idx}/{total}] 🔘 Seleccionando: {radio.text}")
                    radio.click()
                    time.sleep(1)
                    break
        except Exception as e:
            logging.warning(f"[{idx}/{total}] ⚠️ No se pudo seleccionar radio button: {e}")

        # ========== PASO 6: HACER CLICK EN CONSULTAR ==========
        logging.info(f"[{idx}/{total}] 🖱️ Haciendo click en Consultar...")

        try:
            # Buscar el botón Consultar
            consultar_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                                            "//button[.//span[contains(text(), 'Consultar')]]"
                                            ))
            )

            # Hacer click con JavaScript (más confiable)
            driver.execute_script("arguments[0].click();", consultar_btn)
            logging.info(f"[{idx}/{total}] ✅ Click en Consultar ejecutado")

        except Exception as e:
            logging.error(f"[{idx}/{total}] ❌ Error haciendo click: {e}")
            # Intentar submit del formulario
            try:
                form = driver.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                logging.info(f"[{idx}/{total}] ✅ Submit del formulario ejecutado")
            except:
                raise

        # ========== PASO 7: ESPERAR RESULTADOS ==========
        logging.info(f"[{idx}/{total}] ⏳ Esperando resultados...")
        time.sleep(15)  # TOR es lento, esperar más

        save_debug_info(driver, numero, "04_despues_consultar")

        # ========== PASO 8: BUSCAR TABLA DE RESULTADOS ==========
        try:
            # Esperar a que aparezca alguna tabla
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//table"))
            )

            tables = driver.find_elements(By.XPATH, "//table")
            logging.info(f"[{idx}/{total}] ✅ Encontradas {len(tables)} tablas")

            # Buscar tabla con resultados
            for table in tables:
                try:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if rows:
                        logging.info(f"[{idx}/{total}] 📋 Tabla con {len(rows)} filas encontrada")
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
                            logging.info(f"[{idx}/{total}] 📌 Proceso: {proceso_num}")

                            # Fecha de última actuación
                            try:
                                fecha_btn = cells[2].find_element(By.TAG_NAME, "button")
                                fecha_text = fecha_btn.text.strip()
                                logging.info(f"[{idx}/{total}] 📅 Fecha: {fecha_text}")

                                # Parsear fecha
                                fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()

                                if fecha_obj >= cutoff:
                                    logging.info(f"[{idx}/{total}] 🎯 Fecha DENTRO del período")

                                    # Hacer click en la fecha
                                    driver.execute_script("arguments[0].click();", fecha_btn)
                                    time.sleep(8)

                                    save_debug_info(driver, numero, "06_click_fecha")

                                    # ========== PASO 9: EXTRAER ACTUACIONES ==========
                                    # Buscar tabla de actuaciones
                                    try:
                                        act_tables = driver.find_elements(By.XPATH, "//table")
                                        for act_table in act_tables:
                                            act_rows = act_table.find_elements(By.XPATH, ".//tbody//tr")
                                            if len(act_rows) > 1:  # Más de 1 fila (header + datos)
                                                logging.info(
                                                    f"[{idx}/{total}] 📝 Encontradas {len(act_rows) - 1} actuaciones")

                                                for row in act_rows[1:]:  # Saltar header
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
                                                                logging.info(
                                                                    f"      ✅ Actuación {act_fecha}: {act_nombre[:50]}...")
                                                        except:
                                                            continue
                                                break
                                    except Exception as e:
                                        logging.error(f"Error extrayendo actuaciones: {e}")

                                    # Volver
                                    driver.back()
                                    time.sleep(5)
                                else:
                                    logging.info(f"[{idx}/{total}] ⏭️ Fecha FUERA del período")
                            except Exception as e:
                                logging.warning(f"[{idx}/{total}] ⚠️ No se pudo extraer fecha: {e}")
                        break
                except:
                    continue

        except TimeoutException:
            logging.warning(f"[{idx}/{total}] ⚠️ No se encontraron tablas de resultados")
            save_debug_info(driver, numero, "05_sin_resultados")

        # ========== PASO 10: FINALIZAR ==========
        with lock:
            results.append((numero, driver.current_url))

        logging.info(f"[{idx}/{total}] ✅ Proceso {numero} COMPLETADO")
        save_debug_info(driver, numero, "99_completado")

    except Exception as e:
        logging.error(f"❌ [{idx}/{total}] Error: {e}")
        save_debug_info(driver, numero, "99_error")
        with lock:
            errors.append((numero, str(e)))
        raise