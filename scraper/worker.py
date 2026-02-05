# scraper/worker.py

import time
import random
import logging
import itertools
import os
from datetime import date, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .config import DIAS_BUSQUEDA, WAIT_TIME
from .browser import is_page_maintenance
from page_objects import ConsultaProcesosPage


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
# UTILIDADES
# --------------------------------------------------

def wait():
    """Pausa WAIT_TIME con hasta 50% jitter."""
    extra = WAIT_TIME * 0.5 * random.random()
    time.sleep(WAIT_TIME + extra)


def wait_page_ready(driver, timeout=30):

    wait = WebDriverWait(driver, timeout)

    wait.until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    try:
        wait.until(
            EC.presence_of_element_located((By.ID, "mainContent"))
        )
    except TimeoutException:
        wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

    logging.info("Página cargó correctamente")


# --------------------------------------------------
# DEBUG
# --------------------------------------------------

def debug_page(driver, numero=None, xpath_fecha=None):
    logging.error("\n========== DEBUG PAGE ==========")

    try:
        logging.error("URL: %s", driver.current_url)
        logging.error("TITLE: %s", driver.title)

        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        logging.error("\n--- TEXTO DETECTADO ---\n")
        logging.error(body_text[:2000])

        # Revisar errores de JS
        for entry in driver.get_log('browser'):
            logging.error("LOG JS: %s", entry)

        path = os.path.join(SCREENSHOT_DIR, f"debug_{numero}.png")
        driver.save_screenshot(path)
        logging.error("Screenshot guardado en %s", path)

        html_path = os.path.join(HTML_DIR, f"debug_{numero}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.error("HTML guardado en %s", html_path)

    except Exception as e:
        logging.error("Error durante debug_page: %s", str(e))

    logging.error("\n===============================\n")


# --------------------------------------------------
# WORKER PRINCIPAL
# --------------------------------------------------

def worker_task(numero, driver, results, actes, errors, lock):

    idx       = next(process_counter)
    total     = TOTAL_PROCESSES or idx
    remaining = total - idx

    print(f"[{idx}/{total}] Proceso {numero} → iniciando (quedan {remaining})")
    logging.info(f"[{idx}/{total}] Iniciando proceso {numero}; faltan {remaining}")

    page   = ConsultaProcesosPage(driver)
    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:

        # 1) Cargar página principal
        page.load()
        wait_page_ready(driver)
        wait()

        # 1.a) Mantenimiento
        if is_page_maintenance(driver):
            logging.warning(f"{numero}: Mantenimiento detectado; durmiendo 30 min")
            time.sleep(1800)
            page.load()
            wait_page_ready(driver)
            wait()

        # 2) Seleccionar por número
        page.select_por_numero()
        wait()

        # 3) Ingresar radicación
        page.enter_numero(numero)
        wait()

        # 4) Consultar
        page.click_consultar()
        wait()

        # 4.a) Modal múltiple
        try:
            volver_modal = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//*[@id='app']/div[3]/div/div/div[2]/div/button/span"
                ))
            )

            driver.execute_script(
                "arguments[0].style.backgroundColor='red'", volver_modal
            )
            volver_modal.click()
            wait()

            print(f"[{idx}/{total}] Proceso {numero}: modal múltiple detectado → cerrado")
            logging.info(f"{numero}: modal múltiple detectado")

        except TimeoutException:
            pass

        # --------------------------------------------------
        # 5) Buscar spans fecha
        # --------------------------------------------------

        xpath_fecha = (
            "//*[@id='mainContent']/div/div/div/div[2]/div/"
            "div/div[2]/div/table/tbody/tr/td[3]/div/button/span"
        )

        try:
            spans = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.XPATH, xpath_fecha))
            )

        except TimeoutException:

            logging.error("Timeout buscando resultados")

            if DEBUG_SCRAPER:
                debug_page(driver, numero, xpath_fecha)

            raise

        wait()

        # --------------------------------------------------
        # 6) Evaluar fechas
        # --------------------------------------------------

        match_span = None

        for s in spans:

            texto = s.text.strip()

            try:
                fecha_obj = date.fromisoformat(texto)
            except ValueError:
                print(f"[{idx}/{total}] '{texto}' no es fecha → ignoro")
                continue

            driver.execute_script(
                "arguments[0].style.backgroundColor='red'", s
            )

            decision = "ACEPTADA" if fecha_obj >= cutoff else "RECHAZADA"

            print(
                f"[{idx}/{total}] Fecha {fecha_obj} vs cutoff {cutoff} → {decision}"
            )

            logging.info(f"{numero}: fecha {fecha_obj} vs {cutoff} → {decision}")

            if fecha_obj >= cutoff:
                match_span = s
                break

        if not match_span:
            logging.info(f"{numero}: sin fechas válidas")
            return

        # --------------------------------------------------
        # 7) Click fecha
        # --------------------------------------------------

        btn = match_span.find_element(By.XPATH, "..")

        driver.execute_script("arguments[0].scrollIntoView()", btn)
        btn.click()

        wait()

        # --------------------------------------------------
        # 8) Tabla actuaciones
        # --------------------------------------------------

        table_xpath = (
            "/html/body/div/div[1]/div[3]/main/div/div/div/div[2]/div/"
            "div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[2]/div/table"
        )

        actuaciones_table = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, table_xpath))
        )

        WebDriverWait(driver, 10).until(
            lambda d: len(actuaciones_table.find_elements(By.TAG_NAME, "tr")) > 1
        )

        wait()

        # --------------------------------------------------
        # 9) Recorrer actuaciones
        # --------------------------------------------------

        rows = actuaciones_table.find_elements(By.TAG_NAME, "tr")[1:]
        url_link = f"{ConsultaProcesosPage.URL}?numeroRadicacion={numero}"

        any_saved = False

        for fila in rows:

            cds = fila.find_elements(By.TAG_NAME, "td")

            if len(cds) < 3:
                continue

            try:
                fecha_act = date.fromisoformat(cds[0].text.strip())
            except ValueError:
                continue

            if fecha_act >= cutoff:

                any_saved = True

                driver.execute_script(
                    "arguments[0].style.backgroundColor='red'", fila
                )

                actuac = cds[1].text.strip()
                anota  = cds[2].text.strip()

                logging.info(
                    f"{numero}: actuación '{actuac}' ({fecha_act}) agregada"
                )

                with lock:
                    actes.append((
                        numero,
                        fecha_act.isoformat(),
                        actuac,
                        anota,
                        url_link
                    ))

        # --------------------------------------------------
        # 10) Registrar URL
        # --------------------------------------------------

        with lock:
            results.append((numero, url_link))

        if any_saved:
            logging.info(f"{numero}: proceso completado con guardado")
        else:
            logging.info(f"{numero}: sin actuaciones guardadas")

        # --------------------------------------------------
        # 11) Volver listado
        # --------------------------------------------------

        page.click_volver()
        wait_page_ready(driver)
        wait()

    except TimeoutException as te:

        logging.error(f"{numero}: TIMEOUT → {te}")

        if DEBUG_SCRAPER:
            debug_page(driver, numero)

        raise

    except Exception as e:

        logging.error(f"{numero}: ERROR general → {e}")

        if DEBUG_SCRAPER:
            debug_page(driver, numero)

        raise