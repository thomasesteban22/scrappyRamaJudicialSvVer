# scraper/free_proxy_manager.py
import requests
import random
import logging
import time


class FreeProxyManager:
    """Gestor simple de proxies gratuitos como backup."""

    def __init__(self):
        self.proxy_list = []

    def fetch_proxies(self):
        """Obtener proxies gratuitos."""
        try:
            # Fuente 1: proxyscrape
            url1 = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
            response1 = requests.get(url1, timeout=10)
            proxies1 = response1.text.strip().split('\r\n')

            # Fuente 2: proxy-list
            url2 = "https://www.proxy-list.download/api/v1/get?type=http"
            response2 = requests.get(url2, timeout=10)
            proxies2 = response2.text.strip().split('\r\n')

            # Combinar y limpiar
            all_proxies = proxies1 + proxies2
            self.proxy_list = [p.strip() for p in all_proxies if p.strip()]

            logging.info(f"Proxies obtenidos: {len(self.proxy_list)}")
            return self.proxy_list

        except Exception as e:
            logging.error(f"Error obteniendo proxies: {e}")
            return []

    def get_random_proxy(self):
        """Obtener proxy aleatorio."""
        if not self.proxy_list:
            self.fetch_proxies()

        if self.proxy_list:
            proxy = random.choice(self.proxy_list)
            logging.info(f"Proxy seleccionado: {proxy}")
            return proxy

        return None

    def test_proxy(self, proxy):
        """Probar si un proxy funciona."""
        try:
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            session.timeout = 10

            response = session.get('https://api.ipify.org', timeout=10)
            return response.status_code == 200

        except:
            return False