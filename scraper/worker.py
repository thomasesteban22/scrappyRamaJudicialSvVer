# scraper/worker.py

import time
import random
import logging
import itertools
from datetime import date, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .config import DIAS_BUSQUEDA, WAIT_TIME
from .browser import is_page_maintenance
from page_objects import ConsultaProcesosPage



# Contador para mostrar progreso
process_counter = itertools.count(1)
TOTAL_PROCESSES = 0  # ← se asigna en main.py: worker.TOTAL_PROCESSES = len(procesos)

def wait():
    """Pausa WAIT_TIME con hasta 50% de jitter."""
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

    logging.info("Página cargó correctamente")

def worker_task(numero, driver, results, actes, errors, lock):
    idx       = next(process_counter)
    total     = TOTAL_PROCESSES or idx
    remaining = total - idx
    print(f"[{idx}/{total}] Proceso {numero} → iniciando (quedan {remaining})")
    logging.info(f"[{idx}/{total}] Iniciando proceso {numero}; faltan {remaining}")

    page   = ConsultaProcesosPage(driver)
    cutoff = date.today() - timedelta(days=DIAS_BUSQUEDA)

    try:
        # 1) Cargo la página principal y espero DOM completo
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

        # 2) Selecciono “Todos los Procesos”
        page.select_por_numero()
        wait()

        # 3) Ingreso número de radicación
        page.enter_numero(numero)
        wait()

        # 4) Clic en “Consultar”
        page.click_consultar()
        wait()

        # 4.a) Cierre modal múltiple si aparece
        try:
            volver_modal = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//*[@id='app']/div[3]/div/div/div[2]/div/button/span"
                ))
            )
            driver.execute_script("arguments[0].style.backgroundColor='red'", volver_modal)
            volver_modal.click()
            wait()
            print(f"[{idx}/{total}] Proceso {numero}: modal múltiple detectado → cerrado y continúo")
            logging.info(f"{numero}: modal múltiple detectado, continuando flujo")
        except TimeoutException:
            pass

        # 5) Espero a que carguen los spans de fecha en el DOM
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
            logging.error("URL: %s", driver.current_url)
            logging.error("TITLE: %s", driver.title)

            html = driver.page_source.lower()

            if "captcha" in html:
                logging.error("Bloqueo captcha detectado")

            if "acceso restringido" in html:
                logging.error("Bloqueo por firewall")

            if "cloudflare" in html:
                logging.error("Bloqueo cloudflare")

            # guardar html para inspección manual
            with open(f"debug_{numero}.html", "w", encoding="utf8") as f:
                f.write(driver.page_source)

            raise
        wait()

        # 6) Comparo cada fecha vs cutoff y busco la primera aceptada
        match_span = None
        for s in spans:
            texto = s.text.strip()
            try:
                fecha_obj = date.fromisoformat(texto)
            except ValueError:
                print(f"[{idx}/{total}] Proceso {numero}: '{texto}' no es fecha → ignoro")
                continue

            driver.execute_script("arguments[0].style.backgroundColor='red'", s)
            decision = "ACEPTADA" if fecha_obj >= cutoff else "RECHAZADA"
            print(f"[{idx}/{total}] Fecha obtenida {fecha_obj} vs cutoff {cutoff} → {decision}")
            logging.info(f"{numero}: fecha {fecha_obj} vs {cutoff} → {decision}")

            if fecha_obj >= cutoff:
                match_span = s
                break

        if not match_span:
            print(f"[{idx}/{total}] Proceso {numero}: ninguna fecha en rango → salto")
            logging.info(f"{numero}: sin fechas ≥ {cutoff}")
            return

        # 7) Click en el botón padre del span aceptado
        btn = match_span.find_element(By.XPATH, "..")
        print(f"[{idx}/{total}] Proceso {numero}: clic en fecha {match_span.text.strip()}")
        logging.info(f"{numero}: clic en fecha {match_span.text.strip()}")
        driver.execute_script("arguments[0].scrollIntoView()", btn)
        btn.click()
        wait()

        # 8) Espero la tabla de actuaciones y al menos una fila de datos
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

        # 9) Recorro filas y guardo actuaciones en rango
        rows     = actuaciones_table.find_elements(By.TAG_NAME, "tr")[1:]
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
                driver.execute_script("arguments[0].style.backgroundColor='red'", fila)
                actuac = cds[1].text.strip()
                anota  = cds[2].text.strip()
                msg    = (
                    f"[{idx}/{total}] Proceso {numero}: actuación "
                    f"'{actuac}' ({fecha_act}) agregada"
                )
                print(msg)
                logging.info(msg)
                with lock:
                    actes.append((numero,
                                  fecha_act.isoformat(),
                                  actuac,
                                  anota,
                                  url_link))

        # 10) Registro URL
        with lock:
            results.append((numero, url_link))

        if any_saved:
            print(f"[{idx}/{total}] Proceso {numero}: registros guardados")
            logging.info(f"{numero}: proceso completado con guardado")
        else:
            print(f"[{idx}/{total}] Proceso {numero}: ninguna actuación guardada tras click → salto")
            logging.info(f"{numero}: proceso finalizado sin actuaciones guardadas")

        # 11) Volver al listado
        page.click_volver()
        wait()

    except TimeoutException as te:
        logging.error(f"{numero}: TIMEOUT → {te}")
        raise
    except Exception as e:
        logging.error(f"{numero}: ERROR general → {e}")
        raise
