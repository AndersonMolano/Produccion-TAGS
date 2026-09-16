from pathlib import Path


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# JSON de las customizaciones descargadas desde Amazon
JSON_INPUT_DIR = BASE_DIR / "Datos"

# Imágenes extraídas de las customized-url para reutilizarlas
# en el robot productivo sin volver a descargar la misma customización.
CUSTOM_FILES_DIR = BASE_DIR / "Customizaciones"

# Carpeta donde se genera el SVG base intermedio
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "jig_base.svg"

# Reporte local para ejecutar el Motor de forma independiente.
# El flujo integrado NO depende de esta carpeta: Produccion/main.py
# pasa directamente la ruta real del reporte descargado.
REPORTES_DIR = BASE_DIR / "Reportes"

# Fuentes locales
FONTS_DIR = BASE_DIR / "Fuentes"


# ============================================================
# GOOGLE DRIVE - DISEÑOS
# ============================================================

GOOGLE_DRIVE_DESIGNS_FOLDER_ID = "1MyOGzrzEPq7DDa3H1_7GjtRy2lugAk2s"

GOOGLE_DRIVE_SVG_FOLDER_ID = "19UzWwuVsPaaQAZtiCb9TVese-t81OW9U"


# ============================================================
# CANVAS FÍSICO
# ============================================================

CANVAS_WIDTH_MM = 94.8
CANVAS_HEIGHT_MM = 94.8


# ============================================================
# TAG / CÍRCULO
# ============================================================

TAG_DIAMETER_MM = 30.0
TAG_RADIUS_MM = TAG_DIAMETER_MM / 2


# ============================================================
# MATRIZ 3 x 3
# ============================================================

GRID_ROWS = 3
GRID_COLUMNS = 3

FIRST_CENTER_X_MM = 15.0
FIRST_CENTER_Y_MM = 15.0

CENTER_SPACING_X_MM = 32.4
CENTER_SPACING_Y_MM = 32.4


# ============================================================
# SVG DE PRUEBA
# ============================================================

CIRCLE_STROKE = "#000000"
CIRCLE_STROKE_WIDTH_MM = 0.1
CIRCLE_FILL = "none"
