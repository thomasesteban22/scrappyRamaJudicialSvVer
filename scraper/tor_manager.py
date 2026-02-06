# scraper/tor_manager.py
import time
import logging
import requests
from stem import Signal
from stem.control import Controller
from stem.util import term


class TorController:
    """Controlador inteligente de TOR con fallback a proxies gratuitos."""

    def __init__(self):
        self.socks_proxy = "socks5://127.0.0.1:9050"
        self.http_proxy = "http://127.0.0.1:8118"
        self.control_port = 9051
        self.controller = None
        self.proxy_failures = 0
        self.max_failures = 3

    def start(self):
        """Iniciar conexión con TOR."""
        try:
            # Verificar que TOR está funcionando
            self.test_tor_connection()

            # Conectar al controlador
            self.controller = Controller.from_port(port=self.control_port)
            self.controller.authenticate()  # Sin contraseña si usamos CookieAuthentication

            logging.info(term.format("✅ TOR conectado y autenticado", term.Color.GREEN))
            self.print_tor_info()
            return True

        except Exception as e:
            logging.error(f"❌ Error conectando a TOR: {e}")
            logging.warning("Intentando modo TOR simple (sin control)...")
            return False

    def test_tor_connection(self):
        """Probar que TOR está funcionando."""
        try:
            session = requests.Session()
            session.proxies = {
                'http': self.socks_proxy,
                'https': self.socks_proxy
            }

            # Test 1: Conectar a check.torproject.org
            response = session.get('https://check.torproject.org/', timeout=30)
            if 'Congratulations' in response.text:
                logging.info("🎉 TOR funcionando correctamente")
            else:
                logging.warning("TOR conectado pero no detectado como red TOR")

            # Test 2: Obtener IP actual
            ip_response = session.get('https://api.ipify.org', timeout=10)
            current_ip = ip_response.text.strip()
            logging.info(f"🌐 IP actual a través de TOR: {current_ip}")

            return True

        except Exception as e:
            logging.error(f"Error probando TOR: {e}")
            return False

    def renew_identity(self):
        """Cambiar a un nuevo circuito TOR (nueva IP)."""
        try:
            if self.controller:
                self.controller.signal(Signal.NEWNYM)

                # Esperar a que se establezca el nuevo circuito
                time.sleep(5)

                # Verificar nueva IP
                new_ip = self.get_current_ip()
                if new_ip:
                    logging.info(f"🔄 IP renovada: {new_ip}")
                    self.proxy_failures = 0  # Resetear contador de fallos
                    return True

        except Exception as e:
            logging.error(f"Error renovando identidad TOR: {e}")
            self.proxy_failures += 1

        return False

    def get_current_ip(self):
        """Obtener IP actual a través de TOR."""
        try:
            session = self.create_tor_session()
            response = session.get('https://api.ipify.org', timeout=10)
            return response.text.strip()
        except:
            return None

    def create_tor_session(self):
        """Crear sesión requests que use TOR."""
        session = requests.Session()
        session.proxies = {
            'http': self.socks_proxy,
            'https': self.socks_proxy
        }
        session.timeout = 30
        return session

    def create_selenium_options(self, base_options):
        """Añadir configuración de proxy a Selenium options."""
        from selenium.webdriver.chrome.options import Options

        # Método 1: HTTP proxy (vía Privoxy)
        base_options.add_argument(f'--proxy-server={self.http_proxy}')

        # Método 2: SOCKS5 directo (alternativo)
        # base_options.add_argument(f'--proxy-server=socks5://127.0.0.1:9050')

        # Ignorar errores de certificado
        base_options.add_argument('--ignore-certificate-errors')
        base_options.add_argument('--ignore-ssl-errors')

        return base_options

    def handle_request_failure(self):
        """Manejar fallo de request - rotar IP si hay muchos fallos."""
        self.proxy_failures += 1
        logging.warning(f"Fallo #{self.proxy_failures} con IP actual")

        if self.proxy_failures >= self.max_failures:
            logging.info("Demasiados fallos, renovando IP TOR...")
            if self.renew_identity():
                return True

        return False

    def print_tor_info(self):
        """Mostrar información sobre el circuito TOR actual."""
        try:
            if self.controller:
                circuit = self.controller.get_circuit(0)  # Primer circuito
                if circuit:
                    nodes = []
                    for hop in circuit.path:
                        desc = self.controller.get_network_status(hop[0])
                        if desc:
                            nodes.append(desc.address)

                    logging.info(f"🔗 Circuito TOR: {' → '.join(nodes[:3])}...")
        except:
            pass

    def emergency_fallback(self):
        """Fallback de emergencia a proxies gratuitos si TOR falla."""
        logging.warning("⚠️ TOR falló, usando proxies gratuitos de emergencia...")

        from .free_proxy_manager import FreeProxyManager
        proxy_manager = FreeProxyManager()

        for _ in range(5):  # Intentar 5 proxies diferentes
            proxy = proxy_manager.get_random_proxy()
            if proxy:
                logging.info(f"Probando proxy gratuito: {proxy}")
                try:
                    session = requests.Session()
                    session.proxies = {'http': proxy, 'https': proxy}
                    response = session.get('https://api.ipify.org', timeout=10)

                    if response.status_code == 200:
                        logging.info(f"✅ Proxy gratuito funciona: IP {response.text}")
                        return {
                            'http': proxy,
                            'https': proxy,
                            'type': 'free_proxy'
                        }
                except:
                    continue

        logging.error("❌ Todos los proxies gratuitos fallaron")
        return None