# scraper/logger.py
import logging
import os
import sys
import csv
from datetime import datetime


# Colores ANSI para consola
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'
    MAGENTA = '\033[95m'


class ScraperLogger:
    def __init__(self):
        self.logger = logging.getLogger('scraper')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # ========== TIMESTAMP DE LA EJECUCIÓN ==========
        self.execution_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.execution_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # ========== DIRECTORIO DE LOGS ==========
        self.logs_dir = "/app/logs"  # Montado en /home/logs
        os.makedirs(self.logs_dir, exist_ok=True)

        # ========== ARCHIVO DE LOG COMPLETO ==========
        self.log_file = os.path.join(self.logs_dir, f'scraper_{self.execution_id}.log')

        # Handler para archivo (guarda TODO)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

        # Handler para consola (solo info importante)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(CustomFormatter())
        self.logger.addHandler(console)

        # ========== REGISTROS SEPARADOS ==========
        self.results_log_path = os.path.join(self.logs_dir, f'resultados_{self.execution_id}.txt')
        self.errors_log_path = os.path.join(self.logs_dir, f'errores_{self.execution_id}.txt')
        self.actuaciones_log_path = os.path.join(self.logs_dir, f'actuaciones_{self.execution_id}.csv')

        # Escribir encabezado
        self._write_header()

    def _write_header(self):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{'=' * 80}\n")
            f.write(f" SCRAPER RAMA JUDICIAL - EJECUCIÓN {self.execution_id}\n")
            f.write(f" Fecha: {self.execution_date}\n")
            f.write(f"{'=' * 80}\n\n")

    # ========== MÉTODOS PRINCIPALES ==========

    def titulo(self, mensaje):
        """📌 TÍTULO - Para secciones importantes"""
        self.logger.info(f"\n{Colors.BOLD}{Colors.WHITE}{mensaje}{Colors.END}")
        self.logger.info(f"{Colors.GRAY}{'=' * 50}{Colors.END}")

    def resultado(self, mensaje):
        """📊 RESULTADOS - Siempre se muestra."""
        self.logger.info(f"{Colors.GREEN}{Colors.BOLD}📊 {mensaje}{Colors.END}")

        with open(self.results_log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} - {mensaje}\n")

    def progreso(self, mensaje):
        """🔄 PROGRESO - Avance del scraper."""
        self.logger.info(f"{Colors.CYAN}🔄 {mensaje}{Colors.END}")

    def proceso(self, mensaje):
        """📋 PROCESO - Detalles del proceso actual."""
        self.logger.info(f"{Colors.WHITE}📋 {mensaje}{Colors.END}")

    def accion(self, mensaje):
        """🖱️ ACCIÓN - Clicks, navegación, etc."""
        self.logger.info(f"{Colors.BLUE}🖱️ {mensaje}{Colors.END}")

    def exito(self, mensaje):
        """✅ ÉXITO - Operaciones exitosas."""
        self.logger.info(f"{Colors.GREEN}✅ {mensaje}{Colors.END}")

    def advertencia(self, mensaje):
        """⚠️ ADVERTENCIA - Problemas no críticos."""
        self.logger.warning(f"{Colors.YELLOW}⚠️ {mensaje}{Colors.END}")

    def error(self, mensaje):
        """❌ ERROR - Problemas críticos (siempre se muestra)."""
        self.logger.error(f"{Colors.RED}❌ {mensaje}{Colors.END}")

        with open(self.errors_log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} - {mensaje}\n")

    def info(self, mensaje):
        """📌 Información general"""
        self.logger.info(f"{Colors.CYAN}📌 {mensaje}{Colors.END}")

    def separador(self):
        """Línea separadora."""
        self.logger.info(f"{Colors.GRAY}{'=' * 50}{Colors.END}")

    # ========== MÉTODOS PARA ARCHIVO (NO SALEN EN CONSOLA) ==========

    def tor(self, mensaje):
        """🌐 TOR - Solo al archivo"""
        self.logger.debug(f"🌐 {mensaje}")

    def debug(self, mensaje):
        """🔧 Debug - Solo al archivo"""
        self.logger.debug(f"🔧 {mensaje}")

    def detalle(self, mensaje):
        """📋 Detalles técnicos - Solo al archivo"""
        self.logger.debug(f"📋 {mensaje}")

    # ========== MÉTODOS PARA GUARDAR RESULTADOS ==========

    def guardar_actuacion(self, numero, fecha, actuacion, anotacion, url):
        """Guarda una actuación en el archivo CSV de la ejecución."""
        file_exists = os.path.isfile(self.actuaciones_log_path)

        with open(self.actuaciones_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    'ID_Ejecucion',
                    'Fecha_Ejecucion',
                    'Numero_Proceso',
                    'Fecha_Actuacion',
                    'Actuacion',
                    'Anotacion',
                    'URL'
                ])

            writer.writerow([
                self.execution_id,
                self.execution_date,
                numero,
                fecha,
                actuacion.replace('\n', ' ').replace('\r', ''),
                anotacion.replace('\n', ' ').replace('\r', ''),
                url
            ])

    def guardar_resumen(self, total_procesos, exitosos, errores, total_actuaciones):
        """Guarda un resumen de la ejecución."""
        resumen_path = os.path.join(self.logs_dir, f'resumen_{self.execution_id}.txt')

        with open(resumen_path, 'w', encoding='utf-8') as f:
            f.write(f"{'=' * 60}\n")
            f.write(f"RESUMEN DE EJECUCIÓN - {self.execution_id}\n")
            f.write(f"{'=' * 60}\n\n")
            f.write(f"Fecha: {self.execution_date}\n")
            f.write(f"Debug: {'ACTIVADO' if os.getenv('DEBUG_SCRAPER', '0') == '1' else 'DESACTIVADO'}\n\n")
            f.write(f"📊 ESTADÍSTICAS:\n")
            f.write(f"  • Total procesos: {total_procesos}\n")
            f.write(f"  • Exitosos: {exitosos}\n")
            f.write(f"  • Errores: {errores}\n")
            f.write(f"  • Actuaciones encontradas: {total_actuaciones}\n\n")
            f.write(f"📁 Archivos generados:\n")
            f.write(f"  • Log completo: scraper_{self.execution_id}.log\n")
            f.write(f"  • Resultados: resultados_{self.execution_id}.txt\n")
            f.write(f"  • Errores: errores_{self.execution_id}.txt\n")
            f.write(f"  • Actuaciones: actuaciones_{self.execution_id}.csv\n")
            f.write(f"{'=' * 60}\n")

        return resumen_path

    def get_logs_info(self):
        """Retorna información sobre los logs generados."""
        return {
            'execution_id': self.execution_id,
            'execution_date': self.execution_date,
            'full_log': self.log_file,
            'results_log': self.results_log_path,
            'errors_log': self.errors_log_path,
            'actuaciones_log': self.actuaciones_log_path,
            'logs_dir': self.logs_dir
        }


class CustomFormatter(logging.Formatter):
    """Formato sin timestamp para consola"""

    def format(self, record):
        return super().format(record).split('] ', 1)[-1]


# Instancia global
log = ScraperLogger()

# Silenciar logs externos
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('webdriver_manager').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('charset_normalizer').setLevel(logging.ERROR)