# test_tor.py (crea este archivo para probar)
import requests
import time

print("Probando TOR...")

# Esperar a que TOR se inicie
time.sleep(15)

# Probar sin TOR
try:
    direct = requests.get('https://api.ipify.org', timeout=10)
    print(f"IP sin TOR: {direct.text}")
except Exception as e:
    print(f"Error sin TOR: {e}")

# Probar con TOR
try:
    session = requests.Session()
    session.proxies = {
        'http': 'socks5://127.0.0.1:9050',
        'https': 'socks5://127.0.0.1:9050'
    }

    tor_ip = session.get('https://api.ipify.org', timeout=30)
    print(f"IP con TOR: {tor_ip.text}")

    # Probar acceso al sitio
    test = session.get('https://consultaprocesos.ramajudicial.gov.co', timeout=30)
    print(f"Sitio - Status: {test.status_code}")
    print(f"Sitio - Tamaño: {len(test.text)} caracteres")

except Exception as e:
    print(f"Error con TOR: {e}")