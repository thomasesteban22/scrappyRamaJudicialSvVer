# scraper/diagnostic.py
import requests
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def full_diagnostic():
    """Diagnóstico completo del sistema."""

    logging.info("=" * 60)
    logging.info("DIAGNÓSTICO COMPLETO DEL SISTEMA")
    logging.info("=" * 60)

    # 1. Test conexión directa
    logging.info("\n1. 📡 Test conexión directa:")
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        logging.info(f"   ✅ IP Directa: {response.text}")
    except Exception as e:
        logging.error(f"   ❌ Error: {e}")

    # 2. Test TOR (con más tiempo)
    logging.info("\n2. 🌐 Test TOR (puede tardar 2-3 minutos):")
    for i in range(12):  # Intentar por 2 minutos
        try:
            session = requests.Session()
            session.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
            session.timeout = 30

            response = session.get('https://api.ipify.org', timeout=30)
            tor_ip = response.text

            # Verificar que es diferente
            direct_ip = requests.get('https://api.ipify.org', timeout=10).text

            if tor_ip != direct_ip:
                logging.info(f"   ✅ TOR FUNCIONANDO: IP TOR={tor_ip}, IP Directa={direct_ip}")
                break
            else:
                logging.warning(f"   ⚠️ Misma IP ({tor_ip}), TOR podría no estar funcionando")

        except Exception as e:
            if i < 11:
                logging.info(f"   ⏳ Intento {i + 1}/12: TOR no listo, esperando 10s...")
                time.sleep(10)
            else:
                logging.error(f"   ❌ TOR no responde después de 2 minutos: {e}")

    # 3. Test sitio objetivo
    logging.info("\n3. 🎯 Test sitio objetivo (Rama Judicial):")
    try:
        session = requests.Session()
        session.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
        session.timeout = 60

        response = session.get('https://consultaprocesos.ramajudicial.gov.co', timeout=60)

        if response.status_code == 200:
            logging.info(f"   ✅ Sitio accesible: código {response.status_code}")
            logging.info(f"   📄 Tamaño respuesta: {len(response.text)} caracteres")

            # Verificar que no hay mensaje de bloqueo
            if "JavaScript" in response.text and "habilitado" in response.text:
                logging.warning("   ⚠️ Posible mensaje de JavaScript deshabilitado")
            else:
                logging.info("   ✅ Sin mensajes de bloqueo detectados")
        else:
            logging.warning(f"   ⚠️ Código {response.status_code}")

    except Exception as e:
        logging.error(f"   ❌ Error accediendo al sitio: {e}")

    # 4. Test Selenium básico
    logging.info("\n4. 🤖 Test Selenium básico:")
    try:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless=new")
        options.add_argument("--proxy-server=socks5://127.0.0.1:9050")
        options.add_argument("--ignore-certificate-errors")

        driver = webdriver.Chrome(options=options)

        # Test simple
        driver.get("https://api.ipify.org")
        selenium_ip = driver.find_element("tag name", "body").text
        logging.info(f"   ✅ Selenium con TOR: IP={selenium_ip}")

        driver.quit()

    except Exception as e:
        logging.error(f"   ❌ Error Selenium: {e}")

    logging.info("\n" + "=" * 60)
    logging.info("DIAGNÓSTICO COMPLETADO")
    logging.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    full_diagnostic()