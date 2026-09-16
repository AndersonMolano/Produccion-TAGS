import os
import glob
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ============================================================
# CONFIGURACIÓN
# ============================================================

EMAIL = os.getenv(
    "AMAZON_EMAIL",
    "Miaucraft.team2@gmail.com"
)

PASSWORD = os.getenv(
    "AMAZON_PASSWORD",
    "Anderson27**"
)

URL_REPORTE = (
    "https://sellercentral.amazon.com/"
    "order-reports-and-feeds/reports/"
    "fbmUnshippedOrders"
)


# ============================================================
# RUTAS
# ============================================================

CARPETA_ACTUAL = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# INICIAR SELENIUM
# ============================================================

def iniciar_driver():

    opciones = Options()

    opciones.add_argument("--start-maximized")
    opciones.add_argument("--disable-gpu")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")

    # --------------------------------------------------------
    # Prevenir detección básica de automatización
    # --------------------------------------------------------

    opciones.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    opciones.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )

    opciones.add_experimental_option(
        "useAutomationExtension",
        False
    )

    # --------------------------------------------------------
    # Carpeta de descargas
    # --------------------------------------------------------

    prefs = {
        "download.default_directory": CARPETA_ACTUAL,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }

    opciones.add_experimental_option(
        "prefs",
        prefs
    )

    # --------------------------------------------------------
    # ChromeDriver
    # --------------------------------------------------------

    ruta_driver = os.path.join(
        CARPETA_ACTUAL,
        "chromedriver.exe"
    )

    servicio = Service(
        executable_path=ruta_driver
    )

    return webdriver.Chrome(
        service=servicio,
        options=opciones
    )


# ============================================================
# BOTÓN KAT / SHADOW DOM
# ============================================================

def pulsar_boton_kat(driver, wait):

    print(
        "  [INFO] Buscando botón de confirmación..."
    )

    try:

        kat_button = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "kat-button[data-test='confirm-selection']"
                )
            )
        )

        try:

            wait.until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "kat-button[data-test='confirm-selection']"
                    )
                )
            ).click()

            print(
                "  [OK] Botón de confirmación pulsado."
            )

            return True

        except Exception as error:

            print(
                "  [WARN] Clic normal falló."
            )

            print(
                f"         Detalle: {error}"
            )

            print(
                "  [INFO] Intentando clic mediante JavaScript..."
            )

            driver.execute_script(
                "arguments[0].click();",
                kat_button
            )

            print(
                "  [OK] Botón pulsado mediante JavaScript."
            )

            return True

    except Exception as error:

        print(
            "  [INFO] No apareció el botón de confirmación."
        )

        return False


# ============================================================
# GUARDAR REPORTE
# ============================================================

def guardar_como_amazon_report():

    destino_final = os.path.join(
        CARPETA_ACTUAL,
        "Amazon_report.txt"
    )

    # --------------------------------------------------------
    # Eliminar reporte anterior
    # --------------------------------------------------------

    if os.path.exists(destino_final):
        os.remove(destino_final)

        print(
            "  [INFO] Reporte anterior eliminado."
        )

    print(
        "  [INFO] Esperando que finalice la descarga..."
    )

    tiempo_limite = 30
    tiempo_transcurrido = 0
    archivo_descargado = None

    # --------------------------------------------------------
    # Esperar archivo
    # --------------------------------------------------------

    while tiempo_transcurrido < tiempo_limite:

        archivos = [
            f
            for f in glob.glob(
                os.path.join(CARPETA_ACTUAL, "*")
            )
            if (
                not f.endswith(".crdownload")
                and not f.endswith(".py")
                and f != destino_final
            )
        ]

        if archivos:

            archivo_descargado = max(
                archivos,
                key=os.path.getmtime
            )

            break

        time.sleep(1)
        tiempo_transcurrido += 1

    # --------------------------------------------------------
    # Renombrar
    # --------------------------------------------------------

    if archivo_descargado and os.path.exists(
        archivo_descargado
    ):

        os.rename(
            archivo_descargado,
            destino_final
        )

        print(
            "  [OK] Reporte descargado correctamente."
        )

        print(
            f"  [OK] Ubicación: {destino_final}"
        )

        return destino_final

    raise FileNotFoundError(
        "No se pudo detectar el reporte descargado "
        "dentro del tiempo esperado."
    )


# ============================================================
# DESCARGAR REPORTE AMAZON
# ============================================================

def descargar_reporte():

    print()
    print("=" * 70)
    print("              DESCARGANDO REPORTE DE AMAZON")
    print("=" * 70)

    driver = iniciar_driver()

    wait = WebDriverWait(
        driver,
        20
    )

    try:

        # ====================================================
        # 1. ABRIR AMAZON
        # ====================================================

        print(
            "\n[1/7] ABRIENDO AMAZON SELLER..."
        )

        driver.get(
            URL_REPORTE
        )

        print(
            "[OK] Amazon Seller abierto."
        )

        # ====================================================
        # 2. CORREO
        # ====================================================

        print(
            "\n[2/7] INTRODUCIENDO CREDENCIALES..."
        )

        print(
            "  [INFO] Introduciendo correo..."
        )

        campo_email = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "ap_email")
            )
        )

        campo_email.clear()
        campo_email.send_keys(
            EMAIL
        )

        wait.until(
            EC.element_to_be_clickable(
                (By.ID, "continue")
            )
        ).click()

        print(
            "  [OK] Correo introducido."
        )

        # ====================================================
        # 3. CONTRASEÑA
        # ====================================================

        print(
            "  [INFO] Introduciendo contraseña..."
        )

        campo_password = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "ap_password")
            )
        )

        campo_password.clear()

        campo_password.send_keys(
            PASSWORD
        )

        wait.until(
            EC.element_to_be_clickable(
                (By.ID, "signInSubmit")
            )
        ).click()

        print(
            "  [OK] Credenciales enviadas."
        )

        # ====================================================
        # 4. MFA
        # ====================================================

        print(
            "\n[3/7] VALIDANDO MFA..."
        )

        try:

            campo_codigo = WebDriverWait(
                driver,
                5
            ).until(
                EC.presence_of_element_located(
                    (
                        By.ID,
                        "auth-mfa-otpcode"
                    )
                )
            )

            codigo = input(
                "\n  [MFA] Código requerido: "
            )

            campo_codigo.clear()

            campo_codigo.send_keys(
                codigo
            )

            wait.until(
                EC.element_to_be_clickable(
                    (
                        By.ID,
                        "auth-signin-button"
                    )
                )
            ).click()

            print(
                "  [OK] MFA completado."
            )

        except Exception:

            print(
                "  [INFO] No se solicitó MFA."
            )

        # ====================================================
        # 5. SELECCIÓN DE CUENTA
        # ====================================================

        print(
            "\n[4/7] VALIDANDO CUENTA DE AMAZON..."
        )

        try:

            print(
                "  [INFO] Buscando Estados Unidos / United States..."
            )

            xpath_usa = (
                "//span[contains(text(),'Estados Unidos') "
                "or contains(text(),'United States')]"
            )

            cuenta_usa = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        xpath_usa
                    )
                )
            )

            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                cuenta_usa
            )

            driver.execute_script(
                "arguments[0].click();",
                cuenta_usa
            )

            print(
                "  [OK] Cuenta de Estados Unidos seleccionada."
            )

            pulsar_boton_kat(
                driver,
                wait
            )

        except Exception:

            print(
                "  [INFO] No apareció la pantalla de selección de país."
            )

        # ====================================================
        # 6. SOLICITAR Y ACTUALIZAR REPORTE
        # ====================================================

        print(
            "\n[5/7] SOLICITANDO REPORTE..."
        )

        btn_request = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "input[name='request']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            btn_request
        )

        try:

            btn_request.click()

        except Exception:

            driver.execute_script(
                "arguments[0].click();",
                btn_request
            )

        print(
            "  [OK] Solicitud enviada."
        )

        print(
            "  [INFO] Esperando 60 segundos "
            "para generar el reporte..."
        )

        time.sleep(60)

        print(
            "  [INFO] Actualizando tabla..."
        )

        btn_refresh = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "input[name='refresh']"
                )
            )
        )

        try:

            btn_refresh.click()

        except Exception:

            driver.execute_script(
                "arguments[0].click();",
                btn_refresh
            )

        print(
            "  [OK] Tabla actualizada."
        )

        # ====================================================
        # 7. DESCARGAR REPORTE
        # ====================================================

        print(
            "\n[6/7] DESCARGANDO REPORTE..."
        )

        print(
            "  [INFO] Buscando reporte más reciente..."
        )

        btn_descargar = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "(//a[contains(@href, 'documentMetadata')])[1]"
                )
            )
        )

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            btn_descargar
        )

        try:

            btn_descargar.click()

        except Exception:

            driver.execute_script(
                "arguments[0].click();",
                btn_descargar
            )

        print(
            "  [OK] Descarga iniciada."
        )

        # ====================================================
        # ESPERAR Y RENOMBRAR
        # ====================================================

        print(
            "\n[7/7] GUARDANDO REPORTE..."
        )

        ruta_final = guardar_como_amazon_report()

        print()
        print("=" * 70)
        print("              REPORTE AMAZON LISTO")
        print("=" * 70)

        print(
            f"\n[OK] Archivo: {ruta_final}"
        )

        return ruta_final

    except Exception as error:

        print()
        print("=" * 70)
        print("             ERROR DESCARGANDO REPORTE")
        print("=" * 70)

        print(
            f"\n[ERROR] {error}"
        )

        raise

    finally:

        driver.quit()

        print(
            "\n[INFO] Navegador cerrado."
        )


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":

    try:

        descargar_reporte()

    except Exception as error:

        print(
            "\n[ERROR] El proceso terminó con errores."
        )

        print(
            f"[ERROR] {error}"
        )