# scraper/worker.py - CON MÁS SCREENSHOTS

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
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .config import DIAS_BUSQUEDA, WAIT_TIME
from .browser import is_page_maintenance
from page_objects import ConsultaProcesosPage

# Configuración de debug
DEBUG_SCRAPER = True  # Siempre activar debug
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# Contador progreso
process_counter = itertools.count(1)
TOTAL_PROCESSES = 0


def save_debug_info(driver, numero, step_name, extra_info=""):
    """Guarda screenshot y HTML para debugging."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Screenshot
    ss_filename = f"{numero}_{step_name}_{timestamp}.png"
    ss_path = os.path.join(SCREENSHOT_DIR, ss_filename)

    # HTML
    html_filename = f"{numero}_{step_name}_{timestamp}.html"
    html_path = os.path.join(HTML_DIR, html_filename)

    try:
        # Tomar screenshot
        driver.save_screenshot(ss_path)

        # Guardar HTML
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # Log
        logging.info(f"📸 DEBUG: {step_name} - Screenshot: {ss_filename}")
        logging.info(f"📄 DEBUG: {step_name} - HTML: {html_filename}")

        if extra_info:
            logging.info(f"ℹ️  DEBUG: {step_name} - {extra_info}")

        # También mostrar URL actual
        logging.info(f"🌐 DEBUG: {step_name} - URL: {driver.current_url}")

    except Exception as e:
        logging.error(f"❌ Error guardando debug {step_name}: {e}")

    return ss_path, html_path


def wait_page_ready(driver, timeout=60):
    """Espera a que la página esté completamente lista."""
    wait = WebDriverWait(driver, timeout)

    try:
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logging.info("✅ Página completamente cargada")
        return True
    except TimeoutException:
        logging.warning("⚠️ Timeout esperando página, continuando...")
        return False


def worker_task(numero, driver, results, actes, errors, lock):
    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx
    remaining = total - idx

    logging.info(f"🚀 [{idx}/{total}] Iniciando proceso {numero}")

    page = ConsultaProcesosPage(driver)
    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:
        # ========== PASO 1: CARGAR PÁGINA ==========
        logging.info(f"[{idx}/{total}] {numero}: Cargando página principal...")
        page.load()

        # Screenshot 1: Página cargada
        save_debug_info(driver, numero, "01_pagina_cargada",
                        f"URL: {driver.current_url}")

        if not wait_page_ready(driver):
            save_debug_info(driver, numero, "01_error_carga")
            raise Exception("Página no cargó correctamente")

        # Espera aleatoria
        time.sleep(random.uniform(2, 4))

        # ========== PASO 2: VERIFICAR MANTENIMIENTO ==========
        if is_page_maintenance(driver):
            logging.warning(f"[{idx}/{total}] {numero}: Mantenimiento detectado")
            save_debug_info(driver, numero, "02_mantenimiento")
            time.sleep(120)
            page.load()
            wait_page_ready(driver)

        # ========== PASO 3: BUSCAR Y HACER CLICK EN "NÚMERO DE RADICACIÓN" ==========
        logging.info(f"[{idx}/{total}] {numero}: Buscando opción 'Número de Radicación'...")

        try:
            # Intentar varios selectores posibles
            selectors = [
                "//button[contains(@title, 'Número de radicación')]",
                "//button[contains(@aria-label, 'Número de radicación')]",
                "//button[.//i[contains(@class, 'fa-list-ol')]]",
                "//button[contains(@class, 'v-btn') and .//span[contains(text(), 'Número')]]",
                "//div[contains(@class, 'processFilterBox')]//button"
            ]

            element = None
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        element = elements[0]
                        logging.info(f"✅ Encontrado con selector: {selector}")
                        break
                except:
                    continue

            if element:
                # Screenshot antes del click
                save_debug_info(driver, numero, "03_antes_click_numero",
                                f"Elemento encontrado: {element.text[:50]}")

                # Hacer click
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(1)
                element.click()

                # Screenshot después del click
                save_debug_info(driver, numero, "03_despues_click_numero")

            else:
                # Fallback al método de página
                logging.info("Usando método de página...")
                page.select_por_numero()

        except Exception as e:
            logging.error(f"Error seleccionando por número: {e}")
            save_debug_info(driver, numero, "03_error_seleccion_numero", str(e))

        time.sleep(random.uniform(2, 3))

        # ========== PASO 4: INGRESAR NÚMERO ==========
        logging.info(f"[{idx}/{total}] {numero}: Ingresando número...")

        try:
            # Buscar campo de entrada
            input_selectors = [
                "//input[@maxlength='23']",
                "//input[contains(@placeholder, '23 dígitos')]",
                "//input[contains(@id, 'input-')]",
                "//div[contains(@class, 'v-text-field')]//input"
            ]

            input_element = None
            for selector in input_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        input_element = elements[0]
                        logging.info(f"✅ Campo de entrada encontrado con: {selector}")
                        break
                except:
                    continue

            if input_element:
                # Limpiar campo primero
                input_element.clear()
                time.sleep(0.5)

                # Escribir número lentamente
                for char in str(numero):
                    input_element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))

                # Screenshot con número ingresado
                save_debug_info(driver, numero, "04_numero_ingresado",
                                f"Número: {numero}")

            else:
                # Fallback
                page.enter_numero(numero)

        except Exception as e:
            logging.error(f"Error ingresando número: {e}")
            save_debug_info(driver, numero, "04_error_ingreso_numero", str(e))

        time.sleep(random.uniform(1, 2))

        # ========== PASO 5: HACER CLICK EN CONSULTAR ==========
        logging.info(f"[{idx}/{total}] {numero}: Haciendo click en Consultar...")

        try:
            # Buscar botón Consultar
            consultar_selectors = [
                "//button[contains(@aria-label, 'Consultar')]",
                "//button[.//span[contains(text(), 'Consultar')]]",
                "//button[contains(@class, 'success')]",
                "//button[contains(@class, 'v-btn--has-bg') and .//span[contains(text(), 'Consultar')]]"
            ]

            consultar_btn = None
            for selector in consultar_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        consultar_btn = elements[0]
                        logging.info(f"✅ Botón Consultar encontrado con: {selector}")
                        break
                except:
                    continue

            if consultar_btn:
                # Screenshot antes de consultar
                save_debug_info(driver, numero, "05_antes_consultar")

                # Hacer click
                driver.execute_script("arguments[0].scrollIntoView(true);", consultar_btn)
                time.sleep(0.5)
                consultar_btn.click()

                # Screenshot después de consultar
                save_debug_info(driver, numero, "05_despues_consultar")

            else:
                # Fallback
                page.click_consultar()

        except Exception as e:
            logging.error(f"Error haciendo click en Consultar: {e}")
            save_debug_info(driver, numero, "05_error_consultar", str(e))

        # Esperar resultados
        logging.info(f"[{idx}/{total}] {numero}: Esperando resultados...")
        time.sleep(5)

        # ========== PASO 6: VERIFICAR RESULTADOS ==========
        save_debug_info(driver, numero, "06_resultados_consulta",
                        "Después de click en Consultar")

        # Buscar tabla de resultados
        logging.info(f"[{idx}/{total}] {numero}: Buscando tabla de resultados...")

        try:
            # Esperar a que aparezca alguna tabla
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//table"))
            )

            # Screenshot de tabla encontrada
            save_debug_info(driver, numero, "07_tabla_encontrada")

            # Buscar todas las tablas
            tables = driver.find_elements(By.XPATH, "//table")
            logging.info(f"✅ Encontradas {len(tables)} tablas")

            # Analizar cada tabla
            for i, table in enumerate(tables):
                try:
                    table_html = table.get_attribute('outerHTML')[:500]
                    table_text = table.text[:200]

                    logging.info(f"📊 Tabla {i + 1}: Texto inicial: {table_text}")

                    # Verificar si esta tabla tiene fechas
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    logging.info(f"   Filas en tabla {i + 1}: {len(rows)}")

                    if len(rows) > 1:
                        # Tomar screenshot de esta tabla específica
                        driver.execute_script("arguments[0].style.border='3px solid red'", table)
                        time.sleep(0.5)

                        ss_name = f"08_tabla_{i + 1}_con_{len(rows)}_filas"
                        save_debug_info(driver, numero, ss_name,
                                        f"Filas: {len(rows)}, Texto: {table_text[:100]}")

                        # Buscar fechas en esta tabla
                        fecha_xpaths = [
                            ".//td[3]//span",  # Columna 3
                            ".//td[contains(@class, 'fecha')]",
                            ".//span[contains(text(), '/')]",  # Fechas con /
                            ".//td[last()]//button//span"  # Última columna
                        ]

                        for xpath in fecha_xpaths:
                            try:
                                fecha_elements = table.find_elements(By.XPATH, xpath)
                                if fecha_elements:
                                    logging.info(f"   ✅ XPath '{xpath}' encontró {len(fecha_elements)} elementos")
                                    for j, elem in enumerate(fecha_elements[:3]):
                                        logging.info(f"     Elemento {j + 1}: '{elem.text}'")
                            except:
                                continue

                except Exception as e:
                    logging.error(f"Error analizando tabla {i + 1}: {e}")

        except TimeoutException:
            logging.warning(f"[{idx}/{total}] {numero}: No se encontraron tablas")
            save_debug_info(driver, numero, "07_sin_tablas", "Timeout buscando tablas")

        # ========== PASO 7: ANALIZAR PÁGINA COMPLETA ==========
        logging.info(f"[{idx}/{total}] {numero}: Analizando contenido completo...")

        try:
            # Obtener todo el texto de la página
            body = driver.find_element(By.TAG_NAME, "body")
            page_text = body.text

            # Buscar indicios de resultados
            keywords = ["proceso", "radicación", "fecha", "actuación", "resultado", "consulta"]
            found_keywords = []

            for keyword in keywords:
                if keyword.lower() in page_text.lower():
                    found_keywords.append(keyword)

            logging.info(f"📝 Palabras clave encontradas: {', '.join(found_keywords)}")

            # Guardar texto completo para análisis
            text_path = os.path.join(DEBUG_DIR, f"{numero}_texto_completo.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(page_text)

            logging.info(f"📄 Texto completo guardado en: {text_path}")

            # Verificar si hay mensaje de error o "no encontrado"
            error_phrases = [
                "no se encontraron", "sin resultados", "no existe",
                "no hay información", "no se encontró", "no hay datos"
            ]

            for phrase in error_phrases:
                if phrase in page_text.lower():
                    logging.warning(f"⚠️ Frase de error encontrada: '{phrase}'")
                    save_debug_info(driver, numero, "08_error_frase", f"Frase: {phrase}")
                    break

        except Exception as e:
            logging.error(f"Error analizando página: {e}")

        # ========== PASO 8: FINALIZAR ==========
        logging.info(f"[{idx}/{total}] {numero}: Proceso completado")
        save_debug_info(driver, numero, "09_final")

        # Registrar URL
        url_link = f"{ConsultaProcesosPage.URL}?numeroRadicacion={numero}"
        with lock:
            results.append((numero, url_link))

        logging.info(f"✅ {numero}: Finalizado - URL: {url_link}")

    except Exception as e:
        logging.error(f"❌ {numero}: Error en worker_task: {e}")
        save_debug_info(driver, numero, "error_fatal", str(e))

        with lock:
            errors.append((numero, f"Error: {str(e)}"))
        raise