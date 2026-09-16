import shutil
from datetime import date
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

import config
from extractor import obtener_datos_json
from componer_svg import insertar_datos_en_svg
from importar_pedidos import obtener_reporte_mas_reciente, procesar_reporte


# ============================================================
# MESES
# ============================================================

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre"
}


# ============================================================
# FORMATEAR NÚMEROS
# ============================================================

def formatear_numero(valor):
    return f"{valor:.4f}".rstrip("0").rstrip(".")


# ============================================================
# OBTENER ARCHIVOS JSON
# ============================================================

def obtener_archivos_json(customizaciones=None):
    """
    Obtiene los JSON que serán procesados.

    IMPORTANTE:
    Cuando customizaciones viene desde importar_pedidos.py,
    se respeta EXACTAMENTE el orden del Amazon Report.

    NO se utiliza sorted() para determinar el orden.

    Si el Motor se ejecuta de forma independiente y no recibe
    customizaciones, se utiliza el contenido de la carpeta Datos.
    """

    # --------------------------------------------------------
    # FLUJO PRINCIPAL:
    # usar exactamente el orden recibido desde Amazon
    # --------------------------------------------------------
    if customizaciones is not None:
        archivos_json = []

        for customizacion in customizaciones:
            ruta_json = customizacion.get("json_path")

            if not ruta_json:
                continue

            ruta_json = Path(ruta_json)

            if not ruta_json.exists():
                raise FileNotFoundError(
                    f"No se encontró el JSON de la customización:\n"
                    f"{ruta_json}"
                )

            archivos_json.append(ruta_json)

        return archivos_json

    # --------------------------------------------------------
    # FLUJO INDEPENDIENTE:
    # si no hay customizaciones, buscar los JSON existentes.
    #
    # Aquí el orden alfabético solamente aplica al modo
    # independiente, porque no existe un Amazon Report
    # suministrado que determine el orden.
    # --------------------------------------------------------
    return sorted(config.JSON_INPUT_DIR.glob("*.json"))


# ============================================================
# AGRUPAR ARCHIVOS JSON EN LOTES DE 9
# ============================================================

def dividir_en_lotes(archivos_json):
    """Divide los JSON en grupos del tamaño del jig."""

    capacidad_maxima = config.GRID_ROWS * config.GRID_COLUMNS

    return [
        archivos_json[i:i + capacidad_maxima]
        for i in range(0, len(archivos_json), capacidad_maxima)
    ]


# ============================================================
# OBTENER POSICIONES DE LOS SLOTS
# ============================================================

def obtener_posiciones_slots():
    posiciones = []
    tag_number = 1

    for row in range(config.GRID_ROWS):
        for column in range(config.GRID_COLUMNS):

            center_x = (
                config.FIRST_CENTER_X_MM
                + column * config.CENTER_SPACING_X_MM
            )

            center_y = (
                config.FIRST_CENTER_Y_MM
                + row * config.CENTER_SPACING_Y_MM
            )

            posiciones.append({
                "tag_number": tag_number,
                "center_x": center_x,
                "center_y": center_y
            })

            tag_number += 1

    return posiciones


# ============================================================
# PROCESAR UN LOTE DE JSON
# ============================================================

def procesar_json_lote(archivos_json, numero_lote, total_lotes):

    datos_lote = []

    print()
    print("=" * 70)
    print(
        f"        PROCESANDO LOTE {numero_lote}/{total_lotes} "
        f"({len(archivos_json)} archivo(s))"
    )
    print("=" * 70)

    for numero_slot, archivo_json in enumerate(archivos_json, start=1):

        print()
        print("-" * 70)
        print(f"SLOT {numero_slot} | ARCHIVO: {archivo_json.name}")
        print("-" * 70)

        try:

            datos = obtener_datos_json(archivo_json)

            datos_lote.append({
                "slot": numero_slot,
                "archivo": archivo_json.name,
                "datos": datos
            })

            for clave, valor in datos.items():
                print(f"{clave:<20} : {valor}")

            print(
                f"\n[OK] {archivo_json.name} "
                f"procesado correctamente."
            )

        except Exception as error:

            print(
                f"\n[ERROR] No se pudo procesar "
                f"{archivo_json.name}"
            )

            print(f"Detalle: {error}")

            raise

    print()
    print("=" * 70)
    print(
        f"[OK] Se procesaron {len(datos_lote)} archivo(s) "
        f"del lote {numero_lote}."
    )
    print("=" * 70)

    return datos_lote


# ============================================================
# CARPETA DE RESULTADOS DEL DÍA
# ============================================================

def obtener_fecha_texto():

    hoy = date.today()

    return (
        f"{MESES_ES[hoy.month]}."
        f"{hoy.day:02d}."
        f"{hoy.year}"
    )


def obtener_carpeta_run(fecha_texto):
    """Crea una carpeta limpia para la ejecución actual."""

    carpeta_run = (
        config.BASE_DIR
        / f"svg Tags {fecha_texto}"
    )

    if carpeta_run.exists():
        shutil.rmtree(carpeta_run)

    carpeta_run.mkdir(
        parents=True,
        exist_ok=True
    )

    return carpeta_run


# ============================================================
# CREAR SVG DEL JIG BASE
# ============================================================

def crear_svg_jig():

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{config.CANVAS_WIDTH_MM}mm",
            "height": f"{config.CANVAS_HEIGHT_MM}mm",
            "viewBox": (
                f"0 0 "
                f"{config.CANVAS_WIDTH_MM} "
                f"{config.CANVAS_HEIGHT_MM}"
            )
        }
    )

    slots_group = ET.SubElement(
        svg,
        "g",
        {"id": "jig_slots"}
    )

    for slot in obtener_posiciones_slots():

        numero_slot = slot["tag_number"]

        slot_group = ET.SubElement(
            slots_group,
            "g",
            {
                "id": f"slot_{numero_slot}",
                "transform": (
                    f"translate("
                    f"{formatear_numero(slot['center_x'])},"
                    f"{formatear_numero(slot['center_y'])}"
                    f")"
                )
            }
        )

        ET.SubElement(
            slot_group,
            "circle",
            {
                "id": f"slot_{numero_slot}_circle",
                "cx": "0",
                "cy": "0",
                "r": formatear_numero(
                    config.TAG_RADIUS_MM
                ),
                "fill": config.CIRCLE_FILL,
                "stroke": config.CIRCLE_STROKE,
                "stroke-width": formatear_numero(
                    config.CIRCLE_STROKE_WIDTH_MM
                )
            }
        )

    xml_pretty = minidom.parseString(
        ET.tostring(
            svg,
            encoding="utf-8"
        )
    ).toprettyxml(
        indent="    ",
        encoding="UTF-8"
    )

    config.OUTPUT_FILE.write_bytes(
        xml_pretty
        if isinstance(xml_pretty, bytes)
        else xml_pretty.encode("utf-8")
    )

    return config.OUTPUT_FILE


# ============================================================
# GENERAR UN LOTE COMPLETO (FRONT + BACK)
# ============================================================

def generar_lote_svg(
    ruta_base,
    datos_lote,
    numero_lote,
    carpeta_run,
    fecha_texto
):

    carpeta_lote = (
        carpeta_run
        / f"Lote {numero_lote}"
    )

    carpeta_lote.mkdir(
        parents=True,
        exist_ok=True
    )

    sufijo = (
        f"Lote {numero_lote} - "
        f"{fecha_texto}.svg"
    )

    ruta_front = (
        carpeta_lote
        / f"FRONT - {sufijo}"
    )

    ruta_back = (
        carpeta_lote
        / f"BACK - {sufijo}"
    )

    insertar_datos_en_svg(
        ruta_base,
        datos_lote,
        ruta_front,
        cara="front"
    )

    insertar_datos_en_svg(
        ruta_base,
        datos_lote,
        ruta_back,
        cara="back"
    )

    return (
        carpeta_lote,
        ruta_front,
        ruta_back
    )


# ============================================================
# MAIN DEL MOTOR
# ============================================================

def main(
    ruta_reporte=None,
    customizaciones=None
):
    """
    Ejecuta el Motor SVG.

    Cuando recibe customizaciones desde Produccion/main.py:

        customizaciones = procesar_reporte(...)

    se respeta exactamente el orden del Amazon Report.

    La carpeta Motor/Datos NO determina el orden.

    Si se ejecuta el Motor por separado y no se pasan argumentos,
    mantiene el comportamiento independiente.
    """

    print()
    print("=" * 70)
    print("                    MOTOR JIG SVG")
    print("=" * 70)

    # --------------------------------------------------------
    # PASO 0:
    # PREPARAR CUSTOMIZACIONES SOLO SI HACE FALTA
    # --------------------------------------------------------

    if customizaciones is None:

        if ruta_reporte is None:
            ruta_reporte = obtener_reporte_mas_reciente()

        if not ruta_reporte:

            print(
                "\n[ERROR] No se encontró un reporte "
                "de Amazon para procesar."
            )

            return False

        print(
            f"\n[INFO] Preparando customizaciones desde: "
            f"{ruta_reporte}"
        )

        customizaciones = procesar_reporte(
            ruta_reporte
        )

    else:

        print(
            "\n[INFO] Customizaciones recibidas "
            "desde el flujo principal."
        )

    if not customizaciones:

        print(
            "\n[ERROR] No hay customizaciones válidas "
            "para generar SVG."
        )

        return False

    # --------------------------------------------------------
    # PASO 1:
    # OBTENER JSON RESPETANDO EL ORDEN AMAZON
    # --------------------------------------------------------

    archivos_json = obtener_archivos_json(
        customizaciones
    )

    if not archivos_json:

        print()
        print("=" * 70)
        print("[ERROR] EL LOTE NO PUDO PROCESARSE")
        print("=" * 70)

        print(
            f"\nNo se encontraron archivos JSON válidos "
            f"para las customizaciones.\n"
        )

        return False

    # --------------------------------------------------------
    # MOSTRAR ORDEN REAL QUE SERÁ PROCESADO
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("              ORDEN DE PROCESAMIENTO")
    print("=" * 70)

    for posicion, archivo_json in enumerate(
        archivos_json,
        start=1
    ):

        print(
            f"  [{posicion:02}] "
            f"{archivo_json.name}"
        )

    print("=" * 70)

    # --------------------------------------------------------
    # AGRUPAR EN LOTES
    # --------------------------------------------------------

    lotes = dividir_en_lotes(
        archivos_json
    )

    capacidad_maxima = (
        config.GRID_ROWS
        * config.GRID_COLUMNS
    )

    print(
        f"\n[INFO] Se encontraron "
        f"{len(archivos_json)} archivo(s) JSON. "
        f"Se generarán {len(lotes)} lote(s) "
        f"de hasta {capacidad_maxima} c/u."
    )

    # --------------------------------------------------------
    # PASO 1B:
    # CREAR / REINICIAR CARPETA DE RESULTADOS
    # --------------------------------------------------------

    fecha_texto = obtener_fecha_texto()

    carpeta_run = obtener_carpeta_run(
        fecha_texto
    )

    print(
        f"[INFO] Carpeta de resultados: "
        f"{carpeta_run}"
    )

    # --------------------------------------------------------
    # PASO 2:
    # GENERAR SVG BASE
    # --------------------------------------------------------

    print(
        "\n[INFO] Generando SVG base del Jig..."
    )

    try:

        ruta_base = crear_svg_jig()

        print(
            f"[OK] SVG base generado: "
            f"{ruta_base}"
        )

        print(
            f"     Canvas   : "
            f"{config.CANVAS_WIDTH_MM} x "
            f"{config.CANVAS_HEIGHT_MM} mm"
        )

        print(
            f"     Tags     : "
            f"{capacidad_maxima}"
        )

        print(
            f"     Diámetro : "
            f"{config.TAG_DIAMETER_MM} mm"
        )

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "[ERROR] NO FUE POSIBLE "
            "GENERAR EL SVG BASE"
        )
        print("=" * 70)

        print(f"\n{error}\n")

        return False

    # --------------------------------------------------------
    # PASO 3:
    # PROCESAR LOTES
    # --------------------------------------------------------

    lotes_generados = []

    for numero_lote, archivos_del_lote in enumerate(
        lotes,
        start=1
    ):

        try:

            datos_lote = procesar_json_lote(
                archivos_del_lote,
                numero_lote,
                len(lotes)
            )

        except Exception as error:

            print()
            print("=" * 70)
            print(
                f"[ERROR] EL LOTE {numero_lote} "
                f"NO PUDO PROCESARSE"
            )
            print("=" * 70)

            print(f"\n{error}\n")

            return False

        try:

            (
                carpeta_lote,
                ruta_front,
                ruta_back
            ) = generar_lote_svg(
                ruta_base,
                datos_lote,
                numero_lote,
                carpeta_run,
                fecha_texto
            )

            lotes_generados.append(
                (
                    numero_lote,
                    carpeta_lote,
                    ruta_front,
                    ruta_back
                )
            )

        except Exception as error:

            print()
            print("=" * 70)
            print(
                "[ERROR] NO FUE POSIBLE COMPONER "
                f"EL SVG DEL LOTE {numero_lote}"
            )
            print("=" * 70)

            print(f"\n{error}\n")

            return False

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("                  MOTOR SVG COMPLETADO")
    print("=" * 70)

    print(
        f"\nCarpeta        : "
        f"{carpeta_run}"
    )

    print(
        f"JSON procesados: "
        f"{len(archivos_json)}"
    )

    print(
        f"Lotes generados: "
        f"{len(lotes_generados)}"
    )

    for (
        numero_lote,
        carpeta_lote,
        ruta_front,
        ruta_back
    ) in lotes_generados:

        print(
            f"\n  Lote {numero_lote} "
            f"({carpeta_lote})"
        )

        print(
            f"    FRONT : "
            f"{ruta_front.name}"
        )

        print(
            f"    BACK  : "
            f"{ruta_back.name}"
        )

    print()

    return {
        "carpeta_run": carpeta_run,
        "archivos_json": archivos_json,
        "lotes_generados": lotes_generados,
        "cantidad_json": len(archivos_json),
        "cantidad_lotes": len(lotes_generados)
    }


# ============================================================
# EJECUTAR MOTOR DE FORMA INDEPENDIENTE
# ============================================================

if __name__ == "__main__":
    main()