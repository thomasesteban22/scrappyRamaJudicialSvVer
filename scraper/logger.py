# scraper/logger.py
import logging
import os
import sys
from datetime import datetime


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    GRAY = '\033[90m'


class ScraperLogger:
    def __init__(self):
        self.logger = logging.getLogger('scraper')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # ========== USAR /app/logs (montado en /home/logs) ==========
        self.logs_dir = "/app/logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # ========== ARCHIVO DE LOG POR EJECUCIÓN ==========
        self.execution_id = datetime.now().strftime('%Y%m%d_%H%M%S')
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

        # Escribir encabezado
        self._write_header()

    def _write_header(self):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{'=' * 80}\n")
            f.write(f" SCRAPER RAMA JUDICIAL - EJECUCIÓN {self.execution_id}\n")
            f.write(f" Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'=' * 80}\n\n")

    # ========== MÉTODOS PARA CONSOLA ==========

    def info(self, mensaje):
        """📌 Información general"""
        self.logger.info(f"{Colors.CYAN}📌 {mensaje}{Colors.END}")

    def progreso(self, mensaje):
        """🔄 Progreso del scraper"""
        self.logger.info(f"{Colors.GREEN}🔄 {mensaje}{Colors.END}")

    def accion(self, mensaje):
        """🖱️ Acciones (clicks, navegación)"""
        self.logger.info(f"{Colors.BLUE}🖱️ {mensaje}{Colors.END}")

    def exito(self, mensaje):
        """✅ Éxito"""
        self.logger.info(f"{Colors.GREEN}✅ {mensaje}{Colors.END}")

    def advertencia(self, mensaje):
        """⚠️ Advertencias"""
        self.logger.warning(f"{Colors.YELLOW}⚠️ {mensaje}{Colors.END}")

    def error(self, mensaje):
        """❌ Errores"""
        self.logger.error(f"{Colors.RED}❌ {mensaje}{Colors.END}")

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