"""Carga la lista de procesos: primero intenta la API de Magna, si falla usa el Excel."""
import pandas as pd
from .config import EXCEL_PATH
from .logger import log
from . import magna_client


def _cargar_desde_excel() -> list[str]:
    xl = pd.ExcelFile(EXCEL_PATH)
    sheet_name = xl.sheet_names[0]
    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name=sheet_name,
        usecols="B",
        header=None,
    )
    return [
        str(x).zfill(23)
        for x in df.iloc[:, 0]
        if pd.notna(x) and str(x).strip().isdigit()
    ]


def cargar_procesos() -> list[str]:
    procesos = magna_client.get_procesos()
    if procesos:
        log.exito(f"Cargados {len(procesos)} procesos desde Magna")
        # Asegurar formato: 23 dígitos con padding
        return [p.strip().zfill(23) for p in procesos if p and p.strip().isdigit()]

    log.advertencia("Magna no disponible, fallback al Excel")
    return _cargar_desde_excel()
