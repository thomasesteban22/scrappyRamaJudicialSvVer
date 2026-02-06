# scraper/diagnostic.py
from browser import new_chrome_driver


def run_diagnostic():
    driver = new_chrome_driver(0)

    try:
        # Test 1: Navegar a Google
        driver.get("https://www.google.com")
        print("✅ Google cargado")

        # Test 2: Verificar JavaScript
        js_result = driver.execute_script("return 1 + 1")
        print(f"✅ JavaScript funciona: 1+1={js_result}")

        # Test 3: Verificar User-Agent
        user_agent = driver.execute_script("return navigator.userAgent")
        print(f"✅ User-Agent: {user_agent}")

        # Test 4: Verificar webdriver
        webdriver_prop = driver.execute_script("return navigator.webdriver")
        print(f"✅ navigator.webdriver: {webdriver_prop}")

        # Test 5: Navegar al sitio objetivo
        driver.get("https://consultaprocesos.ramajudicial.gov.co")
        print("✅ Sitio objetivo cargado")

        # Verificar contenido
        body_text = driver.find_element(By.TAG_NAME, "body").text[:200]
        print(f"✅ Texto del body: {body_text}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    run_diagnostic()