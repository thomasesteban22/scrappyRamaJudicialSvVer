# scraper/verify_tor.py
import requests
import time
import logging


def verify_tor_setup():
    """Verificar que TOR está configurado correctamente."""

    logging.info("=" * 50)
    logging.info("VERIFICACIÓN DE CONFIGURACIÓN TOR")
    logging.info("=" * 50)

    # 1. Probar conexión directa
    try:
        direct_response = requests.get('https://api.ipify.org', timeout=10)
        direct_ip = direct_response.text.strip()
        logging.info(f"📡 IP Directa: {direct_ip}")
    except Exception as e:
        logging.error(f"❌ Error conexión directa: {e}")
        direct_ip = None

    # 2. Probar con TOR (esperar si es necesario)
    time.sleep(5)

    try:
        session = requests.Session()
        session.proxies = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }
        session.timeout = 30

        tor_response = session.get('https://api.ipify.org', timeout=30)
        tor_ip = tor_response.text.strip()
        logging.info(f"🌐 IP TOR: {tor_ip}")

        if direct_ip and tor_ip != direct_ip:
            logging.info("✅ TOR funcionando correctamente (IP diferente)")
        else:
            logging.warning("⚠️ TOR podría no estar funcionando (misma IP)")

    except Exception as e:
        logging.error(f"❌ Error conexión TOR: {e}")
        tor_ip = None

    # 3. Probar acceso al sitio objetivo
    if tor_ip:
        try:
            test_url = "https://consultaprocesos.ramajudicial.gov.co"
            session = requests.Session()
            session.proxies = {
                'http': 'socks5://127.0.0.1:9050',
                'https': 'socks5://127.0.0.1:9050'
            }

            response = session.get(test_url, timeout=45)

            if response.status_code == 200:
                logging.info(f"✅ Sitio accesible a través de TOR (código: {response.status_code})")
                return True
            else:
                logging.warning(f"⚠️ Sitio respondió con código: {response.status_code}")
                return False

        except Exception as e:
            logging.error(f"❌ Error accediendo al sitio: {e}")
            return False

    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    verify_tor_setup()