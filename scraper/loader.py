import pandas as pd
from .config import EXCEL_PATH

def cargar_procesos():
    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name="CONSULTA UNIFICADA DE PROCESOS",
        usecols="B"
    )
    procesos = [str(x).zfill(23) for x in df.iloc[:, 0] if pd.notna(x)]
    return procesos
