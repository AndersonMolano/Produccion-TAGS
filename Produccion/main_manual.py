from pathlib import Path
import sys


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

PRODUCCION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PRODUCCION_DIR.parent
MOTOR_DIR = PROJECT_ROOT / "Motor"

for ruta in (PRODUCCION_DIR, MOTOR_DIR, PROJECT_ROOT):
    ruta_str = str(ruta)
    if ruta_str not in sys.path:
        sys.path.insert(0, ruta_str)


import config as motor_config
from Motor.importar_pedidos import obtener_reporte_mas_reciente, procesar_reporte
from Motor.main import main as ejecutar_motor_svg
from Motor.drive_service import subir_carpeta_svg_drive


# ============================================================
# FLUJO MANUAL (SIN SELENIUM, SIN ROBOT PRODUCTIVO)
# ============================================================
# Este script NO descarga el reporte automáticamente. Se usa cuando
# quieres dejar tú mismo el .txt del reporte de Amazon dentro de
# Motor/Reportes (el más reciente que encuentre ahí es el que se usa)
# y correr solo: customizaciones -> SVG -> subida a Drive.

def main():
    print()
    print("=" * 80)
    print("     FLUJO MANUAL: REPORTE (YA UBICADO) -> SVG -> DRIVE")
    print("=" * 80)

    # --------------------------------------------------------
    # 1. BUSCAR EL REPORTE YA DEJADO A MANO EN Motor/Reportes
    # --------------------------------------------------------
    print(f"\n[1/3] Buscando reporte en: {motor_config.REPORTES_DIR}")

    ruta_reporte = obtener_reporte_mas_reciente()

    if not ruta_reporte:
        print(
            f"\n❌ No se encontró ningún .txt en {motor_config.REPORTES_DIR}."
        )
        print(
            "❌ Copia ahí el reporte de Amazon (Amazon_report.txt o el "
            "nombre que tenga) y vuelve a correr este script."
        )
        return False

    ruta_reporte = Path(ruta_reporte).resolve()
    print(f"✅ Reporte encontrado: {ruta_reporte.name}")

    # --------------------------------------------------------
    # 2. PREPARAR CUSTOMIZACIONES Y GENERAR LOS SVG
    # --------------------------------------------------------
    print("\n[2/3] Preparando customizaciones y generando SVG...")

    customizaciones = procesar_reporte(ruta_reporte)

    if not customizaciones:
        print("\n❌ No se encontraron customizaciones válidas en el reporte.")
        return False

    print(f"✅ Customizaciones preparadas: {len(customizaciones)}")

    resultado_svg = ejecutar_motor_svg(
        ruta_reporte=ruta_reporte,
        customizaciones=customizaciones
    )

    if not resultado_svg:
        print("\n❌ El Motor SVG falló.")
        return False

    print(f"✅ SVG generados en: {resultado_svg['carpeta_run']}")

    # --------------------------------------------------------
    # 3. SUBIR LOS SVG A GOOGLE DRIVE
    # --------------------------------------------------------
    print("\n[3/3] Subiendo los SVG a Google Drive...")

    resultado_drive_svg = subir_carpeta_svg_drive(
        resultado_svg["carpeta_run"]
    )

    if not resultado_drive_svg:
        print("\n❌ No fue posible subir los SVG a Google Drive.")
        return False

    print(
        f"✅ SVG publicados en Drive: "
        f"{resultado_drive_svg['cantidad_subidos']} archivo(s)."
    )

    # --------------------------------------------------------
    # FIN: SIN ROBOT PRODUCTIVO
    # --------------------------------------------------------
    print()
    print("=" * 80)
    print("           ✅ SVG GENERADOS Y SUBIDOS (sin robot productivo)")
    print("=" * 80)
    print(f"Reporte usado : {ruta_reporte}")
    print(f"Carpeta SVG   : {resultado_svg['carpeta_run']}")
    print(f"JSON          : {resultado_svg['cantidad_json']}")
    print(f"Lotes SVG     : {resultado_svg['cantidad_lotes']}")
    print(f"Drive SVG     : {resultado_drive_svg['cantidad_subidos']} archivo(s)")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        exito = main()
        if not exito:
            print("\n❌ PROCESO FINALIZADO CON ERRORES.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Proceso cancelado por el usuario.")
        sys.exit(1)
    except Exception as error:
        print("\n" + "=" * 80)
        print("❌ ERROR NO CONTROLADO EN EL FLUJO PRINCIPAL")
        print("=" * 80)
        print(error)
        sys.exit(1)