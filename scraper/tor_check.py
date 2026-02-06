# scraper/tor_check.py
import requests
import logging


def check_tor():
    """Verificar que TOR está funcionando."""
    try:
        # Sin TOR
        direct_response = requests.get('https://api.ipify.org', timeout=10)
        direct_ip = direct_response.text.strip()

        # Con TOR
        session = requests.Session()
        session.proxies = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }

        tor_response = session.get('https://api.ipify.org', timeout=10)
        tor_ip = tor_response.text.strip()

        if tor_ip != direct_ip:
            logging.info(f"✅ TOR funcionando: IP Directa={direct_ip}, IP TOR={tor_ip}")
            return True
        else:
            logging.warning(f"⚠️ TOR podría no estar funcionando: misma IP {tor_ip}")
            return False

    except Exception as e:
        logging.error(f"❌ Error verificando TOR: {e}")
        return False


def test_site_with_tor():
    """Probar acceso al sitio con TOR."""
    try:
        session = requests.Session()
        session.proxies = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }

        response = session.get('https://consultaprocesos.ramajudicial.gov.co', timeout=30)

        if response.status_code == 200:
            logging.info("✅ Sitio accesible a través de TOR")
            return True
        else:
            logging.warning(f"⚠️ Código {response.status_code} con TOR")
            return False

    except Exception as e:
        logging.error(f"❌ Error accediendo con TOR: {e}")
        return False