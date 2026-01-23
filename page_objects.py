# page_objects/ConsultaProcesosPage.py

import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ConsultaProcesosPage:
    URL = "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion"

    def __init__(self, driver, selectors_path="selectors.json"):
        self.driver = driver
        with open(selectors_path, 'r', encoding='utf-8') as f:
            self.sel = json.load(f)

    def load(self):
        """Carga la URL y espera a que el DOM esté completamente listo."""
        self.driver.get(self.URL)
        WebDriverWait(self.driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def _find(self, key, timeout=15):
        """
        Busca de forma resiliente un selector definido en selectors.json.
        Prueba cada alternativa hasta que coincida un elemento clickable.
        """
        errores = []
        for alt in self.sel.get(key, []):
            by_str, expr = alt.split(":", 1)
            by = {
                "xpath": By.XPATH,
                "css":   By.CSS_SELECTOR,
                "tag":   By.TAG_NAME
            }[by_str]
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((by, expr))
                )
                # resalta en rojo para debug
                self.driver.execute_script("arguments[0].style.backgroundColor='red'", el)
                return el
            except Exception as e:
                errores.append(f"{alt} → {e}")
                continue
        raise RuntimeError(f"Selector '{key}' no encontró elemento. Detalles: {errores}")

    def select_por_numero(self):
        self._find("radio_busqueda_numero").click()

    def enter_numero(self, numero):
        inp = self._find("input_numero")
        inp.clear()
        inp.send_keys(numero)

    def click_consultar(self):
        self._find("btn_consultar").click()

    def click_volver(self):
        try:
            self._find("btn_volver", timeout=5).click()
        except RuntimeError:
            # si no aparece el botón volver, lo ignoramos
            pass

    def get_tablas(self):
        """Devuelve todas las tablas presentes en la página."""
        return WebDriverWait(self.driver, 15).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
        )
