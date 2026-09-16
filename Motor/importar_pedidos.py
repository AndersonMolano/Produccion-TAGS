import csv
import io
import re
import shutil
import zipfile
from pathlib import Path

import requests

import config


# ============================================================
# UTILIDADES
# ============================================================

def limpiar_nombre(texto):
    """Deja solo caracteres seguros para nombre de archivo."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(texto).strip())


def leer_reporte(ruta_txt):
    """Lee el reporte de Amazon (TSV) y devuelve la lista de filas como dicts."""
    ruta_txt = Path(ruta_txt)

    with ruta_txt.open("r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f, delimiter="\t")
        return list(lector)


def limpiar_carpetas_customizacion():
    """
    Vacía las carpetas de JSON e imágenes para que cada ejecución
    represente exactamente el reporte actual.
    """
    for carpeta in (config.JSON_INPUT_DIR, config.CUSTOM_FILES_DIR):
        if carpeta.exists():
            shutil.rmtree(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)


def obtener_reporte_mas_reciente(carpeta=None):
    """Busca el .txt más reciente en la carpeta indicada."""
    carpeta = Path(carpeta or config.REPORTES_DIR)
    carpeta.mkdir(parents=True, exist_ok=True)

    archivos_txt = list(carpeta.glob("*.txt"))
    if not archivos_txt:
        return None

    return max(archivos_txt, key=lambda p: p.stat().st_mtime)


# ============================================================
# DESCARGA DE CUSTOMIZACIÓN
# ============================================================

def descargar_customizacion_zip(customized_url):
    """
    Descarga la customized-url de Amazon.

    La URL devuelve un ZIP que puede contener JSON, imágenes u otros
    recursos de la personalización.
    """
    respuesta = requests.get(customized_url, timeout=45)
    respuesta.raise_for_status()

    if not zipfile.is_zipfile(io.BytesIO(respuesta.content)):
        raise ValueError(
            f"La customized-url no devolvió un ZIP válido "
            f"(HTTP {respuesta.status_code})."
        )

    return zipfile.ZipFile(io.BytesIO(respuesta.content))


def descargar_y_guardar_customizacion(order_id, order_item_id, customized_url):
    """
    Descarga una customización una sola vez y guarda localmente:
      - JSON en Motor/Datos
      - Primera imagen encontrada en Motor/Customizaciones

    Devuelve un diccionario con las rutas generadas.
    """
    nombre_base = f"{limpiar_nombre(order_id)}_{limpiar_nombre(order_item_id)}"

    ruta_json = None
    ruta_imagen = None

    with descargar_customizacion_zip(customized_url) as zf:
        nombres_archivos = [
            nombre for nombre in zf.namelist()
            if not nombre.endswith("/")
        ]

        # --------------------------------------------------------
        # JSON
        # --------------------------------------------------------
        nombres_json = [
            nombre for nombre in nombres_archivos
            if nombre.lower().endswith(".json")
        ]

        if nombres_json:
            json_data = zf.read(nombres_json[0])
            ruta_json = config.JSON_INPUT_DIR / f"{nombre_base}.json"
            ruta_json.write_bytes(json_data)

        # --------------------------------------------------------
        # IMAGEN
        # --------------------------------------------------------
        extensiones_imagen = {".jpg", ".jpeg", ".png"}
        nombres_imagen = [
            nombre for nombre in nombres_archivos
            if Path(nombre).suffix.lower() in extensiones_imagen
        ]

        if nombres_imagen:
            nombre_original = Path(nombres_imagen[0]).name
            extension = Path(nombre_original).suffix.lower() or ".jpg"
            ruta_imagen = config.CUSTOM_FILES_DIR / f"{nombre_base}{extension}"
            ruta_imagen.write_bytes(zf.read(nombres_imagen[0]))

    return {
        "order_id": order_id,
        "order_item_id": order_item_id,
        "customized_url": customized_url,
        "json_path": ruta_json,
        "image_path": ruta_imagen,
    }


def descargar_json_desde_url(customized_url):
    """
    Compatibilidad con el motor anterior.

    Devuelve los bytes del primer JSON encontrado dentro del ZIP.
    """
    with descargar_customizacion_zip(customized_url) as zf:
        nombres_json = [
            nombre for nombre in zf.namelist()
            if nombre.lower().endswith(".json")
        ]

        if not nombres_json:
            return None

        return zf.read(nombres_json[0])


# ============================================================
# PROCESAR EL REPORTE COMPLETO
# ============================================================

def procesar_reporte(ruta_txt):
    """
    Descarga todas las customizaciones del reporte una sola vez.

    Retorna una lista de diccionarios que luego consumen tanto el
    Motor SVG como AMZCustomBot.py.
    """
    ruta_txt = Path(ruta_txt)
    filas = leer_reporte(ruta_txt)

    print()
    print("=" * 70)
    print("        DESCARGANDO CUSTOMIZACIONES DESDE REPORTE DE AMAZON")
    print("=" * 70)
    print(f"\n[INFO] Archivo del reporte : {ruta_txt}")
    print(f"[INFO] Filas encontradas   : {len(filas)}")

    print("\n[INFO] Limpiando archivos de la ejecución anterior...")
    limpiar_carpetas_customizacion()

    resultados = []
    omitidos = 0
    errores = 0

    for idx, fila in enumerate(filas, start=1):
        order_id = str(fila.get("order-id", "")).strip()
        order_item_id = str(fila.get("order-item-id", "")).strip()
        customized_url = str(fila.get("customized-url", "")).strip()

        print()
        print("-" * 70)
        print(f"[{idx}/{len(filas)}] Pedido: {order_id} | Item: {order_item_id}")

        if not customized_url or customized_url.lower() == "nan":
            print("  [OMITIDO] No tiene customized-url (no es un producto personalizado).")
            omitidos += 1
            continue

        try:
            resultado = descargar_y_guardar_customizacion(
                order_id,
                order_item_id,
                customized_url
            )

            if resultado["json_path"] is None:
                print("  [WARN] La customización no contiene JSON.")
                errores += 1
                continue

            resultados.append(resultado)

            print(f"  [OK] JSON   : {resultado['json_path']}")
            if resultado["image_path"]:
                print(f"  [OK] Imagen : {resultado['image_path']}")
            else:
                print("  [INFO] No se encontró imagen en la customización.")

        except requests.exceptions.RequestException as error:
            print(f"  [ERROR] Fallo de red al descargar: {error}")
            errores += 1

        except zipfile.BadZipFile:
            print("  [ERROR] La respuesta recibida no es un ZIP válido.")
            errores += 1

        except Exception as error:
            print(f"  [ERROR] No se pudo procesar: {error}")
            errores += 1

    print()
    print("=" * 70)
    print("                 DESCARGA COMPLETADA")
    print("=" * 70)
    print(f"\nCustomizaciones listas : {len(resultados)}")
    print(f"Omitidos               : {omitidos}")
    print(f"Errores                : {errores}")
    print()

    return resultados


# ============================================================
# MAIN STANDALONE
# ============================================================

def main():
    ruta_txt = obtener_reporte_mas_reciente()

    if not ruta_txt:
        print(f"\n[ERROR] No se encontró ningún .txt en: {config.REPORTES_DIR}\n")
        return False

    resultados = procesar_reporte(ruta_txt)

    if not resultados:
        print("[INFO] No se preparó ninguna customización. El motor no se ejecutará.")
        return False

    # Import tardío para evitar dependencias circulares.
    import main as motor

    return motor.main(
        ruta_reporte=ruta_txt,
        customizaciones=resultados
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\n[ERROR INESPERADO] {error}\n")

    input("\nPresiona ENTER para salir...")
