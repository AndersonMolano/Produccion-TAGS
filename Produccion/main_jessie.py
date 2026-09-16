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


from Extraer_Reporte.descargar_reporte import descargar_reporte
from Motor.importar_pedidos import procesar_reporte
from Motor.main import main as ejecutar_motor_svg
from Motor.drive_service import subir_carpeta_svg_drive


# ============================================================
# FLUJO PRINCIPAL (SOLO REPORTE + SVG, SIN ROBOT PRODUCTIVO)
# ============================================================

def main():
    print()
    print("=" * 80)
    print("        ROBOT DE PRODUCCIÓN TAGS (SOLO REPORTE + SVG)")
    print("=" * 80)

    # --------------------------------------------------------
    # 1. DESCARGAR REPORTE AMAZON
    # --------------------------------------------------------
    print("\n[1/4] DESCARGANDO REPORTE DE AMAZON...")

    ruta_reporte = descargar_reporte()

    if not ruta_reporte:
        print("\n❌ El reporte de Amazon no pudo descargarse.")
        print("❌ El flujo se detiene para evitar trabajar con datos anteriores.")
        return False

    ruta_reporte = Path(ruta_reporte).resolve()
    print(f"✅ Reporte disponible: {ruta_reporte}")

    # --------------------------------------------------------
    # 2. DESCARGAR CUSTOMIZACIONES UNA SOLA VEZ
    # --------------------------------------------------------
    print("\n[2/4] PREPARANDO CUSTOMIZACIONES...")

    customizaciones = procesar_reporte(ruta_reporte)

    if not customizaciones:
        print("\n❌ No se encontraron customizaciones válidas.")
        print("❌ El flujo se detiene antes de continuar.")
        return False

    print(f"✅ Customizaciones preparadas: {len(customizaciones)}")

    # --------------------------------------------------------
    # 3. GENERAR SVG CON EL MISMO LOTE DE DATOS
    # --------------------------------------------------------
    print("\n[3/4] EJECUTANDO MOTOR DE SVG...")

    resultado_svg = ejecutar_motor_svg(
        ruta_reporte=ruta_reporte,
        customizaciones=customizaciones
    )

    if not resultado_svg:
        print("\n❌ El Motor SVG falló.")
        print("❌ El flujo se detiene para evitar dejar un lote inconsistente.")
        return False

    print(f"✅ SVG generados en: {resultado_svg['carpeta_run']}")

    # --------------------------------------------------------
    # 4. SUBIR SVG A GOOGLE DRIVE
    # --------------------------------------------------------
    print("\n[4/4] SUBIENDO RESULTADOS SVG A GOOGLE DRIVE...")

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
    # FIN: NO SE EJECUTA EL ROBOT PRODUCTIVO EN ESTA VERSIÓN
    # --------------------------------------------------------
    print()
    print("=" * 80)
    print("           ✅ REPORTE + SVG FINALIZADOS (sin robot productivo)")
    print("=" * 80)
    print(f"Reporte Amazon : {ruta_reporte}")
    print(f"Carpeta SVG    : {resultado_svg['carpeta_run']}")
    print(f"JSON           : {resultado_svg['cantidad_json']}")
    print(f"Lotes SVG      : {resultado_svg['cantidad_lotes']}")
    print(f"Drive SVG      : {resultado_drive_svg['cantidad_subidos']} archivo(s)")
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