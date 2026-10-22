from pathlib import Path
import sys


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

PRODUCCION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PRODUCCION_DIR.parent
MOTOR_DIR = PROJECT_ROOT / "Motor"

# Los módulos actuales del Motor importan config/componer_svg/etc.
# directamente, por eso agregamos Motor al PATH antes de importarlos.
for ruta in (PRODUCCION_DIR, MOTOR_DIR, PROJECT_ROOT):
    ruta_str = str(ruta)
    if ruta_str not in sys.path:
        sys.path.insert(0, ruta_str)


import config as motor_config
from Motor.importar_pedidos import obtener_reporte_mas_reciente, procesar_reporte
from Motor.main import main as ejecutar_motor_svg
from Motor.drive_service import subir_carpeta_svg_drive
from Insertar_Data.AMZCustomBot import run_miaucraft_robot


# ============================================================
# FLUJO KARL (REPORTE MANUAL + SVG + DRIVE + ROBOT PRODUCTIVO)
# ============================================================
# Este script NO descarga el reporte automáticamente (sin Selenium).
# Toma el .txt más reciente que esté en Motor/Reportes, igual que
# main_manual.py, pero a diferencia de este SÍ ejecuta la parte
# productiva (run_miaucraft_robot) como lo hace main.py.

def main():
    print()
    print("=" * 80)
    print("   FLUJO KARL: REPORTE MANUAL -> SVG -> DRIVE -> ROBOT PRODUCTIVO")
    print("=" * 80)

    # --------------------------------------------------------
    # 1. BUSCAR EL REPORTE YA DEJADO A MANO EN Motor/Reportes
    # --------------------------------------------------------
    print(f"\n[1/5] Buscando reporte en: {motor_config.REPORTES_DIR}")

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
    # 2. PREPARAR CUSTOMIZACIONES UNA SOLA VEZ
    # --------------------------------------------------------
    print("\n[2/5] PREPARANDO CUSTOMIZACIONES...")

    customizaciones = procesar_reporte(ruta_reporte)

    if not customizaciones:
        print("\n❌ No se encontraron customizaciones válidas.")
        print("❌ El flujo se detiene antes de modificar Sheets/Drive.")
        return False

    print(f"✅ Customizaciones preparadas: {len(customizaciones)}")

    # --------------------------------------------------------
    # 3. GENERAR SVG CON EL MISMO LOTE DE DATOS
    # --------------------------------------------------------
    print("\n[3/5] EJECUTANDO MOTOR DE SVG...")

    resultado_svg = ejecutar_motor_svg(
        ruta_reporte=ruta_reporte,
        customizaciones=customizaciones
    )

    if not resultado_svg:
        print("\n❌ El Motor SVG falló.")
        print("❌ El robot productivo no se ejecutará para evitar dejar un lote inconsistente.")
        return False

    print(f"✅ SVG generados en: {resultado_svg['carpeta_run']}")

    # --------------------------------------------------------
    # 4. SUBIR SVG A GOOGLE DRIVE
    # --------------------------------------------------------
    print("\n[4/5] SUBIENDO RESULTADOS SVG A GOOGLE DRIVE...")

    resultado_drive_svg = subir_carpeta_svg_drive(
        resultado_svg["carpeta_run"]
    )

    if not resultado_drive_svg:
        print("\n❌ No fue posible subir los SVG a Google Drive.")
        print("❌ El robot productivo no se ejecutará para evitar dejar un lote inconsistente.")
        return False

    print(
        f"✅ SVG publicados en Drive: "
        f"{resultado_drive_svg['cantidad_subidos']} archivo(s)."
    )

    # --------------------------------------------------------
    # 5. CONTINUAR CON ROBOT PRODUCTIVO
    # --------------------------------------------------------
    print("\n[5/5] EJECUTANDO ROBOT PRODUCTIVO...")

    resultado_productivo = run_miaucraft_robot(
        ruta_reporte=ruta_reporte,
        customizaciones=customizaciones
    )

    if not resultado_productivo:
        print("\n❌ El robot productivo terminó con errores.")
        return False

    print()
    print("=" * 80)
    print("                    ✅ FLUJO KARL FINALIZADO")
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
