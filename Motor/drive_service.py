import mimetypes
import sys
from pathlib import Path

import config
import gdown
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Permite importar las credenciales cuando se ejecuta desde Produccion/main.py
PRODUCCION_DIR = config.BASE_DIR.parent / "Produccion"
if str(PRODUCCION_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCCION_DIR))

from Dependencias.credenciales import obtener_credenciales


CACHE_DIR = config.BASE_DIR / "cache_assets"


def sincronizar_disenos_drive():
    """
    Descarga o actualiza la carpeta pública de diseños de Google Drive.
    Esta función mantiene el comportamiento original del Motor.
    """
    folder_id = getattr(config, "GOOGLE_DRIVE_DESIGNS_FOLDER_ID", None)
    if not folder_id:
        print(
            "      [WARN] GOOGLE_DRIVE_DESIGNS_FOLDER_ID "
            "no está definido en config.py."
        )
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{folder_id}"

    try:
        gdown.download_folder(
            url=url,
            output=str(CACHE_DIR),
            quiet=True,
            use_cookies=False,
        )
    except Exception as error:
        print(f"      [WARN] Error al sincronizar con Google Drive: {error}")


def buscar_svg_local(diseno_str):
    """
    Busca el archivo de diseño descargado (.svg, .png, .jpg, .jpeg)
    en la carpeta cache_assets.
    """
    if not diseno_str or diseno_str == "N/A":
        return None

    import re

    match_codigo = re.search(r"\((.*?)\)", diseno_str)
    codigo = (
        match_codigo.group(1).strip().lower()
        if match_codigo
        else diseno_str.strip().lower()
    )

    if not CACHE_DIR.exists():
        return None

    extensiones_validas = {".svg", ".png", ".jpg", ".jpeg"}

    for archivo in CACHE_DIR.rglob("*"):
        if archivo.suffix.lower() in extensiones_validas:
            nombre_limpio = archivo.stem.lower()
            if codigo in nombre_limpio or diseno_str.lower() in nombre_limpio:
                return archivo

    return None


# ============================================================
# SUBIDA DE RESULTADOS SVG A GOOGLE DRIVE
# ============================================================


def _obtener_servicio_drive():
    """Crea el servicio autenticado de Google Drive."""
    print("🔐 Autenticando Google Drive para subir los SVG...")
    creds = obtener_credenciales()
    return build("drive", "v3", credentials=creds)


def _buscar_carpeta_drive(service, nombre, parent_id):
    """Busca una carpeta existente dentro de parent_id por nombre."""
    query = (
        "trashed = false "
        "and mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{nombre.replace(chr(39), chr(92) + chr(39))}' "
        f"and '{parent_id}' in parents"
    )

    respuesta = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id,name)",
            pageSize=10,
        )
        .execute()
    )

    archivos = respuesta.get("files", [])
    return archivos[0]["id"] if archivos else None


def _crear_carpeta_drive(service, nombre, parent_id):
    """Crea una carpeta dentro de parent_id y devuelve su ID."""
    metadata = {
        "name": nombre,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }

    carpeta = (
        service.files()
        .create(
            body=metadata,
            fields="id,name",
        )
        .execute()
    )

    return carpeta["id"]


def _obtener_o_crear_carpeta(service, nombre, parent_id):
    """Devuelve el ID de una carpeta existente o crea una nueva."""
    carpeta_id = _buscar_carpeta_drive(service, nombre, parent_id)

    if carpeta_id:
        return carpeta_id

    return _crear_carpeta_drive(service, nombre, parent_id)


def _subir_archivo_drive(service, archivo_local, parent_id):
    """Sube un archivo a Drive y devuelve su ID."""
    archivo_local = Path(archivo_local)

    mime_type = mimetypes.guess_type(archivo_local.name)[0] or "application/octet-stream"

    metadata = {
        "name": archivo_local.name,
        "parents": [parent_id],
    }

    media = MediaFileUpload(
        str(archivo_local),
        mimetype=mime_type,
        resumable=True,
    )

    archivo_drive = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink",
        )
        .execute()
    )

    return archivo_drive


def subir_carpeta_svg_drive(carpeta_local, parent_id=None):
    """
    Replica la estructura de una carpeta local de resultados SVG en Google Drive.

    Ejemplo local:

        svg Tags Agosto.24.2026/
            Lote 1/
                FRONT - Lote 1 - Agosto.24.2026.svg
                BACK - Lote 1 - Agosto.24.2026.svg
            Lote 2/
                ...

    Resultado en Drive:

        <carpeta destino configurada>/
            svg Tags Agosto.24.2026/
                Lote 1/
                    FRONT...
                    BACK...
                Lote 2/
                    ...

    Si la carpeta de la ejecución ya existe, se reutiliza. Los archivos se
    suben con su mismo nombre. Si ya existe un archivo con ese nombre dentro
    de la carpeta, Drive conservará ambas versiones.

    Retorna un diccionario con información del resultado o False si falla.
    """
    carpeta_local = Path(carpeta_local).resolve()

    if not carpeta_local.exists() or not carpeta_local.is_dir():
        print(f"❌ No existe la carpeta local de SVG: {carpeta_local}")
        return False

    if parent_id is None:
        parent_id = getattr(config, "GOOGLE_DRIVE_SVG_FOLDER_ID", None)

    if not parent_id:
        print("❌ GOOGLE_DRIVE_SVG_FOLDER_ID no está configurado.")
        return False

    archivos_svg = sorted(
        archivo
        for archivo in carpeta_local.rglob("*")
        if archivo.is_file() and archivo.suffix.lower() == ".svg"
    )

    if not archivos_svg:
        print(f"❌ No se encontraron archivos SVG en: {carpeta_local}")
        return False

    print()
    print("=" * 70)
    print("              SUBIENDO RESULTADOS SVG A GOOGLE DRIVE")
    print("=" * 70)
    print(f"[INFO] Carpeta local : {carpeta_local}")
    print(f"[INFO] Archivos SVG : {len(archivos_svg)}")
    print(f"[INFO] Carpeta Drive: {parent_id}")

    try:
        service = _obtener_servicio_drive()

        carpeta_raiz_id = _obtener_o_crear_carpeta(
            service,
            carpeta_local.name,
            parent_id,
        )

        print(f"[OK] Carpeta de ejecución: {carpeta_local.name}")

        cantidad_subidos = 0
        enlaces = []

        # Mantener la estructura relativa debajo de la carpeta de ejecución.
        for archivo_local in archivos_svg:
            relativo = archivo_local.relative_to(carpeta_local)

            parent_actual = carpeta_raiz_id
            partes_directorio = relativo.parts[:-1]

            for nombre_directorio in partes_directorio:
                parent_actual = _obtener_o_crear_carpeta(
                    service,
                    nombre_directorio,
                    parent_actual,
                )

            print(f"  📤 Subiendo: {relativo}")

            archivo_drive = _subir_archivo_drive(
                service,
                archivo_local,
                parent_actual,
            )

            cantidad_subidos += 1
            enlaces.append(
                {
                    "nombre": archivo_drive.get("name"),
                    "id": archivo_drive.get("id"),
                    "webViewLink": archivo_drive.get("webViewLink"),
                }
            )

            print("     ✅ Subido correctamente.")

        print()
        print("=" * 70)
        print("             ✅ SVG SUBIDOS CORRECTAMENTE A DRIVE")
        print("=" * 70)
        print(f"Archivos subidos : {cantidad_subidos}")
        print(f"Carpeta          : {carpeta_local.name}")
        print("=" * 70)

        return {
            "carpeta_local": carpeta_local,
            "carpeta_drive_id": carpeta_raiz_id,
            "cantidad_subidos": cantidad_subidos,
            "archivos": enlaces,
        }

    except Exception as error:
        print()
        print("=" * 70)
        print("❌ ERROR SUBIENDO LOS SVG A GOOGLE DRIVE")
        print("=" * 70)
        print(error)
        print("=" * 70)
        return False
