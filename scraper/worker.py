# scraper/worker.py
import time
import random
import logging
import itertools
import os
import requests
from datetime import date, timedelta, datetime
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .config import DIAS_BUSQUEDA, WAIT_TIME
from .browser import is_page_maintenance, test_javascript, handle_modal_error, wait_for_tor_circuit
from page_objects import ConsultaProcesosPage

# Configuración
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# Contadores
process_counter = itertools.count(1)
TOTAL_PROCESSES = 0


def save_debug_info(driver, numero, step_name, extra_info=""):
    """Guarda screenshot y HTML con timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss_path = os.path.join(SCREENSHOT_DIR, f"{numero}_{step_name}_{timestamp}.png")
    html_path = os.path.join(HTML_DIR, f"{numero}_{step_name}_{timestamp}.html")

    try:
        driver.save_screenshot(ss_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"📸 {step_name}: Screenshot guardado")
        if extra_info:
            logging.info(f"   ℹ️ {extra_info}")
    except Exception as e:
        logging.error(f"Error guardando debug {step_name}: {e}")


def extract_process_data(driver, numero):
    """Extrae los datos del proceso de la tabla de resultados."""
    try:
        # Esperar a que cargue la tabla
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//table//tbody//tr"))
        )

        # Encontrar la fila del proceso
        row = driver.find_element(By.XPATH, "//table//tbody//tr")
        cells = row.find_elements(By.TAG_NAME, "td")

        if len(cells) >= 5:
            # Número de radicación (cell 1)
            try:
                numero_element = cells[1].find_element(By.TAG_NAME, "button")
                numero_proceso = numero_element.text.strip()
            except:
                numero_proceso = cells[1].text.strip()

            # Fecha de última actuación (cell 2) - ¡LO MÁS IMPORTANTE!
            fecha_text = None
            fecha_element = None
            try:
                fecha_element = cells[2].find_element(By.TAG_NAME, "button")
                fecha_text = fecha_element.text.strip()
            except:
                fecha_text = cells[2].text.strip()

            # Despacho (cell 3)
            despacho = cells[3].text.strip() if len(cells) > 3 else ""

            # Sujetos procesales (cell 4)
            sujetos = cells[4].text.strip() if len(cells) > 4 else ""

            # Parsear fecha
            fecha_obj = None
            if fecha_text:
                try:
                    fecha_obj = datetime.strptime(fecha_text, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        fecha_obj = datetime.strptime(fecha_text, "%d/%m/%Y").date()
                    except ValueError:
                        logging.warning(f"   ⚠️ No se pudo parsear fecha: {fecha_text}")

            return {
                'numero': numero_proceso,
                'fecha_text': fecha_text,
                'fecha_obj': fecha_obj,
                'fecha_element': fecha_element,
                'despacho': despacho,
                'sujetos': sujetos
            }

    except Exception as e:
        logging.error(f"   ❌ Error extrayendo datos: {e}")

    return None


def extract_actuaciones(driver, numero, cutoff):
    """Extrae las actuaciones de la tabla de actuaciones."""
    actuaciones_encontradas = 0

    try:
        # XPATHs posibles para la tabla de actuaciones
        xpaths_actuaciones = [
            "//table[contains(@class, 'v-data-table')]",
            "//div[contains(@class, 'v-data-table')]//table",
            "//table[.//th[contains(text(), 'Actuación')]]",
            "//table[.//th[contains(text(), 'Fecha')]]",
            "//main//table[.//td]"
        ]

        actuaciones_table = None
        for xpath in xpaths_actuaciones:
            try:
                tables = driver.find_elements(By.XPATH, xpath)
                for table in tables:
                    rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    if len(rows) > 0:
                        # Verificar que sea la tabla correcta (tiene fechas)
                        first_row_cells = rows[0].find_elements(By.TAG_NAME, "td")
                        if len(first_row_cells) >= 3:
                            fecha_test = first_row_cells[0].text.strip()
                            if '-' in fecha_test or '/' in fecha_test:
                                actuaciones_table = table
                                logging.info(f"   ✅ Tabla de actuaciones encontrada")
                                break
                if actuaciones_table:
                    break
            except:
                continue

        if actuaciones_table:
            rows = actuaciones_table.find_elements(By.XPATH, ".//tbody//tr")
            logging.info(f"   📊 Total actuaciones encontradas: {len(rows)}")

            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")

                    if len(cells) >= 3:
                        fecha_act_text = cells[0].text.strip()
                        actuacion_text = cells[1].text.strip()
                        anotacion_text = cells[2].text.strip() if len(cells) > 2 else ""

                        # Parsear fecha
                        try:
                            fecha_act = datetime.strptime(fecha_act_text, "%Y-%m-%d").date()
                        except ValueError:
                            try:
                                fecha_act = datetime.strptime(fecha_act_text, "%d/%m/%Y").date()
                            except ValueError:
                                continue

                        # Solo guardar si está dentro del período
                        if fecha_act >= cutoff:
                            logging.info(f"      ✅ {fecha_act}: {actuacion_text[:50]}...")
                            yield {
                                'fecha': fecha_act.isoformat(),
                                'actuacion': actuacion_text,
                                'anotacion': anotacion_text
                            }
                            actuaciones_encontradas += 1
                        else:
                            logging.info(f"      ⏭️ {fecha_act}: fuera de período")

                except Exception as e:
                    logging.debug(f"      ⚠️ Error procesando fila: {e}")
                    continue

            logging.info(f"   📝 Total actuaciones en período: {actuaciones_encontradas}")
        else:
            logging.warning("   ⚠️ No se encontró tabla de actuaciones")
            save_debug_info(driver, numero, "sin_tabla_actuaciones")

    except Exception as e:
        logging.error(f"   ❌ Error extrayendo actuaciones: {e}")

    return actuaciones_encontradas


def worker_task(numero, driver, results, actes, errors, lock):
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx
    remaining = total - idx

    logging.info(f"\n{'=' * 60}")
    logging.info(f"🚀 [{idx}/{total}] INICIANDO PROCESO {numero} (faltan {remaining})")
    logging.info(f"{'=' * 60}")

    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)
    logging.info(f"📅 Fecha corte: {cutoff} (últimos {DIAS_BUSQUEDA} días)")

    try:
        # ========== PASO 1: VERIFICAR TOR ==========
        logging.info(f"[{idx}/{total}] 🔍 Verificando TOR...")
        if not wait_for_tor_circuit(timeout=30):
            logging.error(f"[{idx}/{total}] ❌ TOR no listo, reintentando...")
            time.sleep(15)
            if not wait_for_tor_circuit(timeout=30):
                raise Exception("TOR no disponible después de reintento")

        # ========== PASO 2: CONSULTA DIRECTA ==========
        consulta_url = f"https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion?numeroRadicacion={numero}"
        logging.info(f"[{idx}/{total}] 🌐 Navegando a URL directa...")
        driver.get(consulta_url)
        time.sleep(8)

        save_debug_info(driver, numero, "01_consulta_directa")

        # ========== PASO 3: VERIFICAR Y MANEJAR MODAL DE ERROR ==========
        if handle_modal_error(driver, numero):
            logging.info(f"[{idx}/{total}] ✅ Modal manejado, reintentando...")
            driver.get(consulta_url)
            time.sleep(8)
            save_debug_info(driver, numero, "02_reintento_consulta")

        # ========== PASO 4: VERIFICAR JAVASCRIPT ==========
        logging.info(f"[{idx}/{total}] 🔧 Verificando JavaScript...")
        test_javascript(driver)

        # ========== PASO 5: EXTRACCIÓN DE DATOS DEL PROCESO ==========
        logging.info(f"[{idx}/{total}] 📋 Extrayendo datos del proceso...")
        process_data = extract_process_data(driver, numero)

        if not process_data:
            logging.warning(f"[{idx}/{total}] ⚠️ No se encontraron datos del proceso")
            save_debug_info(driver, numero, "sin_datos_proceso")
            return

        # Mostrar información del proceso
        logging.info(f"   📋 Número: {process_data['numero']}")
        logging.info(f"   📅 Fecha: {process_data['fecha_text']}")
        logging.info(f"   🏛️ Despacho: {process_data['despacho'][:50]}...")

        # ========== PASO 6: VERIFICAR SI LA FECHA ESTÁ DENTRO DEL PERÍODO ==========
        if process_data['fecha_obj'] and process_data['fecha_obj'] >= cutoff:
            logging.info(f"[{idx}/{total}] 🎯 Fecha {process_data['fecha_obj']} DENTRO del período")

            # ========== PASO 7: HACER CLICK EN LA FECHA ==========
            if process_data['fecha_element']:
                logging.info(f"[{idx}/{total}] 👆 Haciendo click en la fecha...")

                try:
                    # Scroll hasta el elemento
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                          process_data['fecha_element'])
                    time.sleep(2)

                    # Click con JavaScript
                    driver.execute_script("arguments[0].click();", process_data['fecha_element'])
                    logging.info(f"   ✅ Click en fecha ejecutado")

                    # Esperar a que cargue la página de actuaciones
                    time.sleep(8)

                    save_debug_info(driver, numero, "03_click_fecha")

                    # ========== PASO 8: EXTRAER ACTUACIONES ==========
                    logging.info(f"[{idx}/{total}] 📝 Extrayendo actuaciones...")
                    actuaciones_guardadas = 0

                    for actuacion in extract_actuaciones(driver, numero, cutoff):
                        with lock:
                            actes.append((
                                numero,
                                actuacion['fecha'],
                                actuacion['actuacion'],
                                actuacion['anotacion'],
                                driver.current_url
                            ))
                        actuaciones_guardadas += 1

                    logging.info(f"[{idx}/{total}] ✅ {actuaciones_guardadas} actuaciones guardadas")

                    # ========== PASO 9: VOLVER A RESULTADOS ==========
                    try:
                        # Buscar botón Volver
                        volver_btn = driver.find_element(By.XPATH,
                                                         "//button[contains(text(), 'Volver') or contains(@title, 'Volver')]"
                                                         )
                        driver.execute_script("arguments[0].click();", volver_btn)
                        logging.info(f"   ↩️ Volviendo a resultados...")
                        time.sleep(5)
                    except:
                        # Si no encuentra botón, navegar directamente
                        logging.info(f"   ↩️ Navegando directamente a URL de consulta...")
                        driver.get(consulta_url)
                        time.sleep(5)

                except Exception as e:
                    logging.error(f"   ❌ Error haciendo click en fecha: {e}")
                    save_debug_info(driver, numero, "error_click_fecha", str(e))
            else:
                logging.warning(f"   ⚠️ No se encontró elemento de fecha para hacer click")
        else:
            if process_data['fecha_obj']:
                logging.info(f"[{idx}/{total}] ⏭️ Fecha {process_data['fecha_obj']} FUERA del período")
            else:
                logging.info(f"[{idx}/{total}] ⏭️ No se pudo determinar fecha")

        # ========== PASO 10: REGISTRAR RESULTADO ==========
        with lock:
            results.append((numero, consulta_url))

        logging.info(f"[{idx}/{total}] ✅ Proceso {numero} COMPLETADO")
        save_debug_info(driver, numero, "99_completado")

    except Exception as e:
        logging.error(f"❌ [{idx}/{total}] Error en proceso {numero}: {str(e)[:200]}")
        save_debug_info(driver, numero, "99_error", str(e)[:200])

        with lock:
            errors.append((numero, str(e)[:200]))
        raise