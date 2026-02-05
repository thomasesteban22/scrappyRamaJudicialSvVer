# scraper/worker.py

import time
import random
import logging
import itertools
import os
import sys
from datetime import date, timedelta
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .config import DIAS_BUSQUEDA, WAIT_TIME
from .browser import is_page_maintenance
from page_objects import ConsultaProcesosPage

# Configuración de debug
DEBUG_SCRAPER = os.getenv("DEBUG_SCRAPER", "0") == "1"
DEBUG_DIR = os.path.join(os.getcwd(), "debug")
SCREENSHOT_DIR = os.path.join(DEBUG_DIR, "screenshots")
HTML_DIR = os.path.join(DEBUG_DIR, "html")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# Contador progreso
process_counter = itertools.count(1)
TOTAL_PROCESSES = 0


# --------------------------------------------------
# UTILIDADES MEJORADAS - COMPORTAMIENTO HUMANO
# --------------------------------------------------

def random_sleep(min_seconds=1, max_seconds=3):
    """Espera aleatoria entre acciones humanas."""
    sleep_time = random.uniform(min_seconds, max_seconds)
    logging.debug(f"Esperando {sleep_time:.2f} segundos")
    time.sleep(sleep_time)


def human_like_delay(base=2, variation=1.5):
    """Delay más humano con variación."""
    delay = base + random.uniform(-variation, variation)
    delay = max(0.5, delay)  # Mínimo 0.5 segundos
    time.sleep(delay)


def simulate_mouse_movement(driver):
    """Simula movimientos aleatorios del mouse."""
    try:
        for i in range(random.randint(2, 4)):
            # Posición aleatoria en pantalla
            x = random.randint(100, driver.execute_script("return window.innerWidth - 100"))
            y = random.randint(100, driver.execute_script("return window.innerHeight - 100"))

            driver.execute_script(f"""
                var ev = new MouseEvent('mousemove', {{
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: {x},
                    clientY: {y},
                    movementX: {random.randint(-10, 10)},
                    movementY: {random.randint(-10, 10)}
                }});
                document.dispatchEvent(ev);
            """)
            time.sleep(random.uniform(0.05, 0.2))
    except Exception as e:
        logging.debug(f"Error simulando movimiento mouse: {e}")


def human_like_click(driver, element):
    """Realiza click de forma más humana."""
    try:
        # Simular hover antes de click
        ActionChains(driver).move_to_element(element).pause(random.uniform(0.1, 0.3)).perform()

        # Pequeño movimiento adicional
        offset_x = random.randint(-5, 5)
        offset_y = random.randint(-5, 5)

        driver.execute_script(f"""
            arguments[0].scrollIntoView({{behavior: 'smooth', block: 'center'}});
        """, element)

        time.sleep(random.uniform(0.1, 0.3))

        # Click con ActionChains para más realismo
        actions = ActionChains(driver)
        actions.move_to_element_with_offset(element, offset_x, offset_y)
        actions.pause(random.uniform(0.05, 0.15))
        actions.click()
        actions.perform()

    except Exception as e:
        logging.warning(f"Error en click humano, usando click normal: {e}")
        element.click()


def simulate_scroll(driver):
    """Simula scroll humano."""
    try:
        scroll_amounts = [random.randint(100, 400) for _ in range(random.randint(1, 3))]

        for amount in scroll_amounts:
            direction = random.choice([-1, 1])  # Arriba o abajo
            driver.execute_script(f"window.scrollBy(0, {amount * direction});")
            time.sleep(random.uniform(0.2, 0.8))

            # Ocasionalmente pequeño scroll de regreso
            if random.random() > 0.7:
                driver.execute_script(f"window.scrollBy(0, {int(amount * 0.3 * -direction)});")
                time.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logging.debug(f"Error simulando scroll: {e}")


def wait_page_ready(driver, timeout=60):
    """Espera a que la página esté completamente lista."""
    wait = WebDriverWait(driver, timeout)

    try:
        # Esperar a que document.readyState sea 'complete'
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Esperar a que algún elemento clave esté presente
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Verificar que no esté vacío
        body = driver.find_element(By.TAG_NAME, "body")
        if len(body.text.strip()) < 10:
            logging.warning("Página parece vacía, esperando adicional...")
            time.sleep(2)

        logging.info("✅ Página completamente cargada")

    except TimeoutException:
        logging.warning("Timeout esperando página, continuando igual...")
        # Intentar capturar el estado actual
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text[:200]
            logging.info(f"Texto de página (primeros 200 chars): {body_text}")
        except:
            pass


def check_for_errors(driver):
    """Verifica errores comunes en la página."""
    try:
        # Verificar si hay mensaje de JavaScript deshabilitado
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()

        error_keywords = [
            "javascript", "no funciona", "habilitado", "lo sentimos",
            "mantenimiento", "temporalmente", "no disponible",
            "access denied", "blocked", "robot", "automation"
        ]

        for keyword in error_keywords:
            if keyword in page_text:
                logging.error(f"⚠️ Posible error detectado: '{keyword}' en página")
                return True

        return False
    except Exception as e:
        logging.debug(f"Error verificando página: {e}")
        return False


# --------------------------------------------------
# FUNCIONES DEBUG MEJORADAS
# --------------------------------------------------

def debug_page(driver, numero=None, step_name="debug"):
    """Captura estado completo de la página para debugging."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    try:
        # Screenshot
        ss_filename = f"{numero or 'unknown'}_{step_name}_{timestamp}.png"
        ss_path = os.path.join(SCREENSHOT_DIR, ss_filename)
        driver.save_screenshot(ss_path)
        logging.info(f"📸 Screenshot guardado: {ss_path}")

        # HTML
        html_filename = f"{numero or 'unknown'}_{step_name}_{timestamp}.html"
        html_path = os.path.join(HTML_DIR, html_filename)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"📄 HTML guardado: {html_path}")

        # Información adicional
        logging.info(f"🔗 URL actual: {driver.current_url}")
        logging.info(f"📝 Título: {driver.title}")

        # Primeras líneas del body
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            lines = body_text.strip().split('\n')[:10]
            logging.info("📋 Primeras 10 líneas del body:")
            for i, line in enumerate(lines, 1):
                if line.strip():
                    logging.info(f"  {i:2d}. {line[:100]}{'...' if len(line) > 100 else ''}")
        except:
            pass

        # Logs de consola
        try:
            logs = driver.get_log('browser')
            if logs:
                logging.info("⚠️ Logs de consola del navegador:")
                for log in logs[-5:]:  # Últimos 5 logs
                    logging.info(f"  {log.get('level', 'INFO')}: {log.get('message', '')[:100]}")
        except:
            pass

    except Exception as e:
        logging.error(f"❌ Error en debug_page: {e}")


# --------------------------------------------------
# WORKER TASK PRINCIPAL - COMPLETAMENTE REVISADO
# --------------------------------------------------

def worker_task(numero, driver, results, actes, errors, lock):
    """Tarea principal del worker con comportamiento humano mejorado."""

    idx = next(process_counter)
    total = TOTAL_PROCESSES or idx
    remaining = total - idx

    logging.info(f"🚀 [{idx}/{total}] Iniciando proceso {numero} (faltan {remaining})")

    page = ConsultaProcesosPage(driver)
    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:
        # ========== PASO 1: CARGAR PÁGINA ==========
        logging.info(f"[{idx}/{total}] {numero}: Cargando página principal...")

        # Comportamiento humano antes de empezar
        simulate_mouse_movement(driver)
        random_sleep(1, 2)

        # Cargar página
        page.load()

        # Scroll aleatorio
        if random.random() > 0.3:
            simulate_scroll(driver)

        # Esperar carga completa
        wait_page_ready(driver)

        # Verificar errores
        if check_for_errors(driver):
            logging.error(f"[{idx}/{total}] {numero}: Error detectado en página")
            if DEBUG_SCRAPER:
                debug_page(driver, numero, "error_inicial")
            raise Exception("Página con error detectado")

        random_sleep(2, 4)

        # ========== PASO 2: VERIFICAR MANTENIMIENTO ==========
        if is_page_maintenance(driver):
            logging.warning(f"[{idx}/{total}] {numero}: Mantenimiento detectado, esperando 2 minutos...")
            if DEBUG_SCRAPER:
                debug_page(driver, numero, "mantenimiento")
            time.sleep(120)

            # Reintentar carga
            page.load()
            wait_page_ready(driver)
            random_sleep(2, 3)

        # ========== PASO 3: SELECCIONAR CONSULTA POR NÚMERO ==========
        logging.info(f"[{idx}/{total}] {numero}: Seleccionando consulta por número...")

        simulate_mouse_movement(driver)

        try:
            # Buscar elemento de selección
            select_element = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "tu_xpath_para_seleccionar_numero"))
            )
            human_like_click(driver, select_element)
        except TimeoutException:
            # Fallback: usar método de página
            page.select_por_numero()

        random_sleep(1, 2)

        # ========== PASO 4: INGRESAR NÚMERO DE RADICACIÓN ==========
        logging.info(f"[{idx}/{total}] {numero}: Ingresando número...")

        try:
            # Buscar campo de entrada
            input_element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "tu_xpath_para_input_numero"))
            )

            # Escribir de forma humana
            for char in str(numero):
                input_element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

        except TimeoutException:
            # Fallback: usar método de página
            page.enter_numero(numero)

        random_sleep(1, 2)

        # ========== PASO 5: CLICK EN CONSULTAR ==========
        logging.info(f"[{idx}/{total}] {numero}: Ejecutando consulta...")

        simulate_mouse_movement(driver)

        try:
            # Buscar botón consultar
            consultar_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Consultar') or contains(@aria-label, 'Consultar')]"))
            )
            human_like_click(driver, consultar_btn)
        except TimeoutException:
            # Fallback
            page.click_consultar()

        # Esperar resultados con timeout ajustado
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH,
                                                "//*[contains(text(), 'Radicación') or contains(text(), 'Resultados') or contains(text(), 'Proceso')]"))
            )
        except TimeoutException:
            logging.warning(f"[{idx}/{total}] {numero}: Timeout esperando resultados")
            if DEBUG_SCRAPER:
                debug_page(driver, numero, "timeout_resultados")

        random_sleep(3, 5)

        # ========== PASO 6: MANEJAR MODAL (SI EXISTE) ==========
        try:
            modal_buttons = driver.find_elements(By.XPATH,
                                                 "//button[contains(text(), 'Volver') or contains(text(), 'Cerrar') or contains(text(), 'Aceptar')]")
            if modal_buttons:
                for btn in modal_buttons[:1]:  # Solo el primero
                    if btn.is_displayed():
                        logging.info(f"[{idx}/{total}] {numero}: Cerrando modal...")
                        human_like_click(driver, btn)
                        random_sleep(1, 2)
                        break
        except:
            pass

        # ========== PASO 7: BUSCAR FECHAS DE PROCESOS ==========
        logging.info(f"[{idx}/{total}] {numero}: Buscando fechas...")

        xpath_fechas = [
            "//span[contains(@class, 'fecha') or contains(text(), '/')]",
            "//td[contains(@class, 'fecha')]",
            "//div[contains(@class, 'fecha')]",
            "//button[contains(@class, 'fecha')]/span"
        ]

        spans = []
        for xpath in xpath_fechas:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                if elements:
                    spans.extend(elements)
                    break
            except:
                continue

        if not spans:
            # Intentar xpath específico de tu error
            try:
                spans = driver.find_elements(By.XPATH,
                                             "//*[@id='mainContent']/div/div/div/div[2]/div/div/div[2]/div/table/tbody/tr/td[3]/div/button/span"
                                             )
            except:
                pass

        if not spans:
            logging.warning(f"[{idx}/{total}] {numero}: No se encontraron fechas")
            if DEBUG_SCRAPER:
                debug_page(driver, numero, "sin_fechas")
            return

        # ========== PASO 8: EVALUAR FECHAS ==========
        match_span = None
        fecha_encontrada = None

        for s in spans[:10]:  # Limitar búsqueda
            texto = s.text.strip()

            # Intentar parsear fecha
            fecha_obj = None
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                try:
                    fecha_obj = datetime.strptime(texto, fmt).date()
                    break
                except ValueError:
                    continue

            if fecha_obj:
                # Resaltar para debug
                try:
                    driver.execute_script("arguments[0].style.border='2px solid red'", s)
                except:
                    pass

                decision = "✅ ACEPTADA" if fecha_obj >= cutoff else "❌ RECHAZADA"
                logging.info(f"[{idx}/{total}] {numero}: Fecha {fecha_obj} vs cutoff {cutoff} → {decision}")

                if fecha_obj >= cutoff:
                    match_span = s
                    fecha_encontrada = fecha_obj
                    break

        if not match_span:
            logging.info(f"[{idx}/{total}] {numero}: Sin fechas válidas dentro del período")
            return

        # ========== PASO 9: CLICK EN FECHA SELECCIONADA ==========
        logging.info(f"[{idx}/{total}] {numero}: Click en fecha {fecha_encontrada}...")

        try:
            # Buscar botón padre
            btn = match_span.find_element(By.XPATH, "..")
            human_like_click(driver, btn)

            # Esperar carga de detalles
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(), 'Actuaciones') or contains(text(), 'Detalles')]"))
            )
            random_sleep(2, 4)

        except Exception as e:
            logging.error(f"[{idx}/{total}] {numero}: Error haciendo click en fecha: {e}")
            if DEBUG_SCRAPER:
                debug_page(driver, numero, "error_click_fecha")
            return

        # ========== PASO 10: EXTRAER ACTUACIONES ==========
        logging.info(f"[{idx}/{total}] {numero}: Extrayendo actuaciones...")

        # XPaths alternativos para tabla de actuaciones
        table_xpaths = [
            "//table[contains(@class, 'actuaciones') or contains(@class, 'tabla')]",
            "//div[contains(@class, 'tabla')]//table",
            "//table[.//th[contains(text(), 'Actuación') or contains(text(), 'Fecha')]]"
        ]

        actuaciones_table = None
        for xpath in table_xpaths:
            try:
                actuaciones_table = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                break
            except:
                continue

        if not actuaciones_table:
            # Intentar xpath específico del error
            try:
                actuaciones_table = driver.find_element(By.XPATH,
                                                        "/html/body/div/div[1]/div[3]/main/div/div/div/div[2]/div/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[2]/div/table"
                                                        )
            except:
                logging.warning(f"[{idx}/{total}] {numero}: No se encontró tabla de actuaciones")
                if DEBUG_SCRAPER:
                    debug_page(driver, numero, "sin_tabla_actuaciones")
                return

        # Extraer filas
        try:
            rows = actuaciones_table.find_elements(By.TAG_NAME, "tr")[1:]  # Saltar header
        except:
            rows = []

        if not rows:
            logging.info(f"[{idx}/{total}] {numero}: Tabla de actuaciones vacía")
            return

        url_link = f"{ConsultaProcesosPage.URL}?numeroRadicacion={numero}"
        actuaciones_guardadas = 0

        for i, fila in enumerate(rows[:20]):  # Limitar a 20 filas
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) < 3:
                    continue

                # Extraer datos
                fecha_text = celdas[0].text.strip()
                actuacion_text = celdas[1].text.strip() if len(celdas) > 1 else ""
                anotacion_text = celdas[2].text.strip() if len(celdas) > 2 else ""

                # Parsear fecha
                fecha_act = None
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                    try:
                        fecha_act = datetime.strptime(fecha_text, fmt).date()
                        break
                    except:
                        continue

                if fecha_act and fecha_act >= cutoff:
                    # Resaltar fila guardada
                    try:
                        driver.execute_script("arguments[0].style.backgroundColor='#d4edda'", fila)
                    except:
                        pass

                    with lock:
                        actes.append((
                            numero,
                            fecha_act.isoformat(),
                            actuacion_text,
                            anotacion_text,
                            url_link
                        ))

                    actuaciones_guardadas += 1
                    logging.info(
                        f"[{idx}/{total}] {numero}: Actuación guardada ({fecha_act}): {actuacion_text[:50]}...")

            except Exception as e:
                logging.debug(f"[{idx}/{total}] {numero}: Error procesando fila {i}: {e}")
                continue

        # ========== PASO 11: REGISTRAR RESULTADOS ==========
        with lock:
            results.append((numero, url_link))

        logging.info(f"[{idx}/{total}] {numero}: Proceso completado - {actuaciones_guardadas} actuaciones guardadas")

        # ========== PASO 12: VOLVER AL LISTADO ==========
        if actuaciones_guardadas > 0:
            logging.info(f"[{idx}/{total}] {numero}: Volviendo al listado...")

            try:
                # Buscar botón volver
                volver_buttons = driver.find_elements(By.XPATH,
                                                      "//button[contains(text(), 'Volver') or contains(text(), 'Regresar') or contains(@title, 'Volver')]"
                                                      )

                if volver_buttons:
                    for btn in volver_buttons:
                        if btn.is_displayed():
                            human_like_click(driver, btn)
                            break
                else:
                    page.click_volver()

                # Esperar a que cargue el listado
                wait_page_ready(driver)
                random_sleep(2, 3)

            except Exception as e:
                logging.warning(f"[{idx}/{total}] {numero}: Error volviendo: {e}")

        # ========== PASO 13: COMPORTAMIENTO FINAL ==========
        simulate_mouse_movement(driver)
        if random.random() > 0.5:
            simulate_scroll(driver)

        random_sleep(1, 2)

    except TimeoutException as te:
        error_msg = f"[{idx}/{total}] {numero}: TIMEOUT - {str(te)}"
        logging.error(error_msg)
        if DEBUG_SCRAPER:
            debug_page(driver, numero, "timeout")
        with lock:
            errors.append((numero, f"Timeout: {str(te)}"))
        raise

    except Exception as e:
        error_msg = f"[{idx}/{total}] {numero}: ERROR - {str(e)}"
        logging.error(error_msg)
        if DEBUG_SCRAPER:
            debug_page(driver, numero, "error_general")
        with lock:
            errors.append((numero, f"Error: {str(e)}"))
        raise


# --------------------------------------------------
# FUNCIÓN DE TEST RÁPIDO
# --------------------------------------------------

def quick_test(driver, numero_test):
    """Función para test rápido sin threads."""
    logging.info(f"🧪 TEST RÁPIDO para proceso: {numero_test}")

    results, actes, errors = [], [], []
    lock = threading.Lock()

    # Reiniciar contadores
    global process_counter, TOTAL_PROCESSES
    process_counter = itertools.count(1)
    TOTAL_PROCESSES = 1

    try:
        worker_task(numero_test, driver, results, actes, errors, lock)

        if errors:
            logging.error(f"❌ TEST FALLIDO: {errors[0][1]}")
        elif actes:
            logging.info(f"✅ TEST EXITOSO: {len(actes)} actuaciones encontradas")
            for act in actes[:3]:  # Mostrar primeras 3
                logging.info(f"   • {act[1]}: {act[2][:50]}...")
        else:
            logging.info("ℹ️ TEST SIN ERRORES pero sin actuaciones")

    except Exception as e:
        logging.error(f"💥 TEST CON EXCEPCIÓN: {e}")

    return len(actes) > 0