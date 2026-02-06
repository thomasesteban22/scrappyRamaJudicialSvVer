# scraper/worker.py
import time
import random
import logging
import itertools
import os
from datetime import date, timedelta, datetime
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


from .config import DIAS_BUSQUEDA, WAIT_TIME
# CORREGIR: Importar desde browser
from .browser import is_page_maintenance
# Si no existe test_javascript, comenta esta línea o créala
# from .browser import test_javascript
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

# Si test_javascript no existe, crea una función dummy
def test_javascript(driver):
    """Función dummy si no existe en browser.py."""
    try:
        result = driver.execute_script("return true")
        return True
    except:
        return False


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


def wait_for_ajax(driver, timeout=30):
    """Espera a que todas las peticiones AJAX terminen."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return jQuery.active == 0")
        )
    except:
        # Si no hay jQuery, esperar un tiempo fijo
        time.sleep(3)


def simulate_human_interaction(driver):
    """Simula interacción humana realista."""
    try:
        # Scroll aleatorio
        scroll_amount = random.randint(200, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))

        # Mover mouse aleatoriamente
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            driver.execute_script(f"""
                var ev = new MouseEvent('mousemove', {{
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: {x},
                    clientY: {y}
                }});
                document.dispatchEvent(ev);
            """)
            time.sleep(random.uniform(0.1, 0.3))

    except Exception as e:
        logging.debug(f"Error en interacción humana: {e}")


def worker_task(numero, driver, results, actes, errors, lock):
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx

    logging.info(f"🚀 [{idx}/{total}] Iniciando {numero}")

    page = ConsultaProcesosPage(driver)
    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:
        # ========== PASO 1: VERIFICAR JAVASCRIPT ==========
        logging.info(f"[{idx}/{total}] Verificando JavaScript...")
        if not test_javascript(driver):
            logging.error("❌ JavaScript no está funcionando")
            raise Exception("JavaScript deshabilitado o no funcionando")

        # ========== PASO 2: CARGAR PÁGINA ==========
        logging.info(f"[{idx}/{total}] Cargando página...")
        driver.get("https://consultaprocesos.ramajudicial.gov.co")
        time.sleep(random.uniform(3, 5))

        save_debug_info(driver, numero, "01_pagina_cargada")

        # Interacción humana
        simulate_human_interaction(driver)

        # ========== PASO 3: NAVEGAR A CONSULTA POR RADICACIÓN ==========
        logging.info(f"[{idx}/{total}] Navegando a consulta por radicación...")

        # Método directo: Ir directamente a la URL de consulta
        consulta_url = f"https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion?numeroRadicacion={numero}"
        driver.get(consulta_url)

        time.sleep(random.uniform(4, 6))
        save_debug_info(driver, numero, "02_pagina_consulta")

        # ========== PASO 4: VERIFICAR QUE CARGÓ CORRECTAMENTE ==========
        try:
            # Verificar que no hay mensaje de JavaScript deshabilitado
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "JavaScript" in body_text and "habilitado" in body_text:
                logging.error("❌ JavaScript está deshabilitado en la página")
                raise Exception("JavaScript deshabilitado en página")

            # Verificar que hay elementos de la consulta
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@maxlength='23']"))
            )
            logging.info("✅ Página de consulta cargada correctamente")

        except TimeoutException:
            logging.error("❌ No se cargó la página de consulta")
            save_debug_info(driver, numero, "03_error_carga_consulta")
            raise

        # ========== PASO 5: INGRESAR NÚMERO (si no se ingresó por URL) ==========
        try:
            input_element = driver.find_element(By.XPATH, "//input[@maxlength='23']")
            current_value = input_element.get_attribute("value")

            if not current_value or current_value != numero:
                logging.info(f"[{idx}/{total}] Ingresando número...")
                input_element.clear()
                time.sleep(0.5)

                # Escribir lentamente como humano
                for char in str(numero):
                    input_element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))

                time.sleep(1)
                save_debug_info(driver, numero, "04_numero_ingresado")

        except Exception as e:
            logging.warning(f"No se pudo ingresar número: {e}")

        # ========== PASO 6: SELECCIONAR TIPO DE CONSULTA ==========
        try:
            # Seleccionar "Todos los Procesos" (opción completa)
            radio_selector = "//div[contains(@class, 'v-radio')]//label[contains(text(), 'Todos los Procesos')]"
            radio_element = driver.find_element(By.XPATH, radio_selector)
            radio_element.click()
            time.sleep(1)
            logging.info("✅ Seleccionada opción 'Todos los Procesos'")

        except Exception as e:
            logging.debug(f"No se pudo seleccionar tipo de consulta: {e}")

        # Interacción humana antes de consultar
        simulate_human_interaction(driver)
        time.sleep(random.uniform(1, 2))

        # ========== PASO 7: HACER CLICK EN CONSULTAR ==========
        logging.info(f"[{idx}/{total}] Ejecutando consulta...")

        try:
            # Tomar screenshot antes
            save_debug_info(driver, numero, "05_antes_consultar")

            # Método 1: Click normal
            consultar_btn = driver.find_element(By.XPATH,
                                                "//button[.//span[contains(text(), 'Consultar')] and contains(@class, 'success')]"
                                                )

            # Hacer click con JavaScript (más confiable)
            driver.execute_script("arguments[0].click();", consultar_btn)
            logging.info("✅ Click en Consultar realizado con JavaScript")

            # ESPERAR MÁS TIEMPO para respuesta (TOR es lento)
            time.sleep(15)  # Aumentar de 8 a 15 segundos

            # Verificar si hay respuesta (buscar algún cambio en la página)
            try:
                # Buscar mensaje de "cargando" o "procesando"
                loading_elements = driver.find_elements(By.XPATH,
                                                        "//*[contains(text(), 'Cargando') or contains(text(), 'Procesando') or contains(text(), 'Buscando')]"
                                                        )

                if loading_elements:
                    logging.info("⏳ Página mostrando indicador de carga, esperando más...")
                    time.sleep(10)

            except:
                pass

            # Tomar screenshot después de esperar
            save_debug_info(driver, numero, "08_despues_consultar")

            # Verificar si la página cambió (buscando resultados)
            current_url = driver.current_url
            logging.info(f"📄 URL después de consultar: {current_url}")

            # Si la URL cambió, podría haber resultados
            if "resultado" in current_url.lower() or "consulta" in current_url.lower():
                logging.info("✅ URL sugiere que hay resultados")

        except Exception as e:
            logging.error(f"❌ Error haciendo click en Consultar: {e}")

            # Intentar método alternativo: enviar formulario directamente
            try:
                logging.info("Intentando método alternativo: submit del formulario...")
                form = driver.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                time.sleep(10)
            except Exception as e2:
                logging.error(f"❌ Error método alternativo: {e2}")
                raise
            # ========== PASO 7: HACER CLICK EN CONSULTAR ==========
        logging.info(f"[{idx}/{total}] Ejecutando consulta...")

        try:
            # Tomar screenshot antes
            save_debug_info(driver, numero, "05_antes_consultar")

            # Método 1: Click normal
            consultar_btn = driver.find_element(By.XPATH,
                                                "//button[.//span[contains(text(), 'Consultar')] and contains(@class, 'success')]"
                                                )

            # Hacer click con JavaScript (más confiable)
            driver.execute_script("arguments[0].click();", consultar_btn)
            logging.info("✅ Click en Consultar realizado con JavaScript")

            # ESPERAR MÁS TIEMPO para respuesta (TOR es lento)
            time.sleep(15)  # Aumentar de 8 a 15 segundos

            # Verificar si hay respuesta (buscar algún cambio en la página)
            try:
                # Buscar mensaje de "cargando" o "procesando"
                loading_elements = driver.find_elements(By.XPATH,
                                                        "//*[contains(text(), 'Cargando') or contains(text(), 'Procesando') or contains(text(), 'Buscando')]"
                                                        )

                if loading_elements:
                    logging.info("⏳ Página mostrando indicador de carga, esperando más...")
                    time.sleep(10)

            except:
                pass

            # Tomar screenshot después de esperar
            save_debug_info(driver, numero, "08_despues_consultar")

            # Verificar si la página cambió (buscando resultados)
            current_url = driver.current_url
            logging.info(f"📄 URL después de consultar: {current_url}")

            # Si la URL cambió, podría haber resultados
            if "resultado" in current_url.lower() or "consulta" in current_url.lower():
                logging.info("✅ URL sugiere que hay resultados")

        except Exception as e:
            logging.error(f"❌ Error haciendo click en Consultar: {e}")

            # Intentar método alternativo: enviar formulario directamente
            try:
                logging.info("Intentando método alternativo: submit del formulario...")
                form = driver.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                time.sleep(10)
            except Exception as e2:
                logging.error(f"❌ Error método alternativo: {e2}")
                raise

        # ========== PASO 8: ESPERAR RESULTADOS Y VERIFICAR ==========
        logging.info(f"[{idx}/{total}] Esperando resultados...")

        # Esperar suficiente tiempo para que cargue
        time.sleep(8)

        # Verificar si hay modal de error
        try:
            modal_error = driver.find_elements(By.XPATH,
                                               "//div[contains(@class, 'v-dialog--active')]//*[contains(text(), 'Error')]"
                                               )

            if modal_error:
                error_text = modal_error[0].text
                logging.error(f"❌ Modal de error detectado: {error_text}")
                save_debug_info(driver, numero, "07_modal_error")
                raise Exception(f"Modal de error: {error_text}")

        except:
            pass  # No hay modal, continuar

        # Tomar screenshot después de consultar
        save_debug_info(driver, numero, "08_despues_consultar")

        # ========== PASO 9: ANALIZAR RESULTADOS ==========
        logging.info(f"[{idx}/{total}] Analizando resultados...")

        # Buscar tablas de resultados
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//table"))
            )

            tables = driver.find_elements(By.XPATH, "//table")
            logging.info(f"✅ Encontradas {len(tables)} tablas")

            if tables:
                # Resaltar primera tabla
                driver.execute_script("arguments[0].style.border='3px solid green'", tables[0])
                time.sleep(1)

                # Analizar tabla
                rows = tables[0].find_elements(By.TAG_NAME, "tr")
                logging.info(f"📊 Tabla principal tiene {len(rows)} filas")

                # Buscar fechas
                for i, row in enumerate(rows[:5]):  # Primeras 5 filas
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 3:
                            fecha_text = cells[2].text.strip()
                            logging.info(f"  Fila {i}: {fecha_text}")
                    except:
                        continue

        except TimeoutException:
            logging.warning("⚠️ No se encontraron tablas de resultados")
            save_debug_info(driver, numero, "09_sin_tablas")

        # ========== PASO 10: FINALIZAR ==========
        logging.info(f"[{idx}/{total}] {numero}: Proceso completado")
        save_debug_info(driver, numero, "10_final")

        # Registrar resultado
        url = f"https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion?numeroRadicacion={numero}"
        with lock:
            results.append((numero, url))

        logging.info(f"✅ {numero}: Finalizado exitosamente")

    except Exception as e:
        logging.error(f"❌ {numero}: Error - {str(e)}")
        save_debug_info(driver, numero, "error_final", str(e))

        with lock:
            errors.append((numero, str(e)))
        raise