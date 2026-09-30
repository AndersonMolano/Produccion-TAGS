print("--- INICIANDO EL ROBOT DE MIAUCRAFT ---")

import pandas as pd
import requests
import io
import json
import os
import datetime
import re
from pypdf import PdfWriter
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

# Nuevas librerías para OAuth
from Dependencias.credenciales import obtener_credenciales

# ==========================================
# CONFIGURACIÓN (Tus IDs Reales)
# ==========================================
IMAGE_FOLDER_ID = '1XAEBj0xQ36C9mf9HeImVhs9yoZGa4Dno'
REPORT_FOLDER_ID = '1lQexshDTg9mHscvrzRBRpqk8HjWhQ_7o'
SPREADSHEET_ID = '1sv46K2O6dbEh6UtRrZv_9PpulzCaOxUJBcLkwKiSRlM'
ENVELOPES_FOLDER_ID = "1Gsz8bIH-KFXo5HpXyAR8s1cQN85ylhiB"
GID_TAB_1 = '1631646403'        
GID_TAB_2 = '774424954'

MESES = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 
         7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}

# ==========================================
# SISTEMA DE AUTENTICACIÓN (OAUTH)
# ==========================================

creds = None
drive_service = None
sheets_service = None


def inicializar_servicios_google():
    """Inicializa OAuth y los servicios de Drive/Sheets solo cuando se necesitan."""
    global creds, drive_service, sheets_service

    if drive_service is not None and sheets_service is not None:
        return

    print("🔐 Inicializando credenciales de Google...")

    creds = obtener_credenciales()

    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    print("✅ Servicios de Google inicializados.")

def parse_custom_json(json_data):
    """Extrae los campos clave del JSON de personalización de Amazon."""
    extracted = {
        "Protection_Plan": "",
        "Size": "",
        "Furry_Name": "",
        "Species": "",
        "Gift_Box": "",
        "BackUps": "" ,
        "Email": "",
        "Phone_1": "",
        "Phone_2": "",
        "Phone_3": ""
    }
    
    if 'version3.0' in json_data:
        areas = json_data['version3.0']['customizationInfo']['surfaces'][0]['areas']
        for area in areas:
            label = area.get('label', '')
            label_lower = label.lower() 
            
            if 'lifetime promise' in label_lower or 'protection' in label_lower:
                extracted["Protection_Plan"] = area.get('optionValue', area.get('text', ''))
                
            elif 'size' in label_lower and 'text' not in label_lower and 'authorization' not in label_lower:
                extracted["Size"] = area.get('optionValue', area.get('text', ''))
                
            elif 'species' in label_lower:
                extracted["Species"] = area.get('optionValue', area.get('text', ''))
                
            # Use lowercase keywords only to match label_lower
            elif 'jewerly' in label_lower or 'gift' in label_lower:
                extracted["Gift_Box"] = area.get('optionValue', area.get('text', ''))
                
            elif 'backup' in label_lower or 'back up' in label_lower:
                extracted["BackUps"] = area.get('optionValue', area.get('text', ''))

    def buscar_texto_profundo(data, variaciones):
        if isinstance(data, dict):
            label = str(data.get('label', '')).lower()
            name = str(data.get('name', '')).lower()
            
            if any(var.lower() in label or var.lower() in name for var in variaciones):
                if 'inputValue' in data:
                    return data['inputValue']
                if 'text' in data:
                    return data['text']
                    
            for key, value in data.items():
                res = buscar_texto_profundo(value, variaciones)
                if res: return res
                
        elif isinstance(data, list):
            for item in data:
                res = buscar_texto_profundo(item, variaciones)
                if res: return res
        return ""

    variaciones_nombre = ["furry name", "furry's name", "peludo name", "peludo"]
    extracted["Furry_Name"] = buscar_texto_profundo(json_data, variaciones_nombre)

    variaciones_email = ["email","email (faster communication)"]
    extracted["Email"] = buscar_texto_profundo(json_data,variaciones_email)

    # Buscar el texto de Rescue Info
    variaciones_rescue = ["rescue info"]
    rescue_info = buscar_texto_profundo(json_data, variaciones_rescue)

    telefonos = []

    if rescue_info:
        telefonos = re.findall(
            r'(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s*|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}',
        rescue_info
    )

    if len(telefonos) > 0:
        extracted["Phone_1"] = telefonos[0]

    if len(telefonos) > 1:
        extracted["Phone_2"] = telefonos[1]

    if len(telefonos) > 2:
        extracted["Phone_3"] = telefonos[2]

    return extracted

def upload_to_drive(content, filename, mimetype, folder_id):
    media = MediaInMemoryUpload(content, mimetype=mimetype)
    file_metadata = {'name': filename, 'parents': [folder_id]}
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    return file.get('id'), file.get('webViewLink')

def get_lote_number():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    query = f"'{REPORT_FOLDER_ID}' in parents and name contains '{today_str}' and mimeType = 'application/pdf'"
    results = drive_service.files().list(q=query).execute()
    return len(results.get('files', [])) + 1

def download_tab_pdf(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=pdf&gid={gid}"
    import google.auth.transport.requests
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    response = requests.get(url, headers={'Authorization': 'Bearer ' + creds.token})
    return io.BytesIO(response.content)

def export_multitab_pdf():
    print("📄 Generando reporte unificado de dos pestañas...")
    now = datetime.datetime.now()
    nombre_mes = MESES[now.month]
    lote = get_lote_number()
    pdf_name = f"{nombre_mes}.{now.day}.{now.year} - Lote {lote} - Alistamiento Report.pdf"

    merger = PdfWriter()
    try:
        pdf1 = download_tab_pdf(GID_TAB_1)
        merger.append(pdf1)
        pdf2 = download_tab_pdf(GID_TAB_2)
        merger.append(pdf2)
        
        merged_pdf_stream = io.BytesIO()
        merger.write(merged_pdf_stream)
        merged_pdf_stream.seek(0)
        
        upload_to_drive(merged_pdf_stream.read(), pdf_name, 'application/pdf', REPORT_FOLDER_ID)
        print(f"🏆 ¡ÉXITO! Reporte final guardado en Drive: {pdf_name}")
    except Exception as e:
        print(f"❌ Error al generar el PDF: {e}")
    finally:
        merger.close()


def generar_pdf_sobres(csv_file):

    fecha = datetime.datetime.now()
    mes = fecha.strftime("%b").title()

    FONDO = "Dependencias/Fondo/Envelope V.5_3.png"
    FUENTE = "Dependencias/Fuente/Caramel.ttf"
    SALIDA = f"Envelopes {mes}.{fecha.day:02d}.{fecha.year} - Lot 1.pdf"

    # ==============================
    # AJUSTES DEL DISEÑO
    # ==============================

    INTERLINEADO = 1.1

    # Nombre de 1 línea
    NOMBRE_SIZE = 1900
    NOMBRE_Y = 3500

    # Nombre de 2 líneas (Y = posición de la PRIMERA línea)
    NOMBRE_SIZE_DOS_LINEAS = 1650
    NOMBRE_Y_DOS_LINEAS = 4300

    CODIGO_SIZE = 350
    CODIGO_X = 450
    CODIGO_Y = 2050

    img = Image.open(FONDO)
    ancho, alto = img.size

    # Se crea una sola vez (con una imagen tan grande, hacerlo en cada página es lento)
    fondo_reader = ImageReader(img)

    pdf = canvas.Canvas(SALIDA, pagesize=(ancho, alto))

    # ==============================
    # CARGAR FUENTE
    # ==============================

    nombre_fuente = "Helvetica-Bold"

    if os.path.exists(FUENTE):
        pdfmetrics.registerFont(TTFont("FuentePrincipal", FUENTE))
        nombre_fuente = "FuentePrincipal"
        print(f"✅ Fuente cargada: {FUENTE}")
    else:
        print(f"⚠️ No se encontró la fuente: {FUENTE}. Se utilizará Helvetica-Bold.")

    # ==============================
    # LEER EL CSV
    # ==============================

    df = pd.read_csv(csv_file)

    for _, fila in df.iterrows():

        nombre = "" if pd.isna(fila["Nombre"]) else str(fila["Nombre"])
        codigo = str(fila["Codigo"])

        # Fondo
        pdf.drawImage(
            fondo_reader,
            0,
            0,
            width=ancho,
            height=alto
        )

        # Nombre (1 o 2 líneas)
        pdf.setFillColorRGB(0, 0, 0)

        partes = nombre.strip().split()

        if len(partes) >= 2:
            lineas = [partes[0], " ".join(partes[1:])]
            size = NOMBRE_SIZE_DOS_LINEAS
            y_inicial = NOMBRE_Y_DOS_LINEAS
        else:
            lineas = partes
            size = NOMBRE_SIZE
            y_inicial = NOMBRE_Y

        pdf.setFont(nombre_fuente, size)
        salto = size * INTERLINEADO

        for i, linea in enumerate(lineas):
            y = y_inicial - (i * salto)
            pdf.drawCentredString(ancho / 2, y, linea)

        # Código
        pdf.saveState()
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica", CODIGO_SIZE)
        pdf.translate(ancho - CODIGO_X, alto - CODIGO_Y)
        pdf.rotate(90)
        pdf.drawString(0, 0, codigo)
        pdf.restoreState()

        pdf.showPage()

    pdf.save()

    # ==============================
    # SUBIR EL PDF A GOOGLE DRIVE
    # ==============================

    with open(SALIDA, "rb") as archivo:
        contenido = archivo.read()

    upload_to_drive(
        contenido,
        os.path.basename(SALIDA),
        "application/pdf",
        ENVELOPES_FOLDER_ID
    )

    print("☁️ PDF subido a Google Drive.")

    # ==============================
    # ELIMINAR EL ARCHIVO TEMPORAL
    # ==============================

    if os.path.exists(SALIDA):
        os.remove(SALIDA)

    print("✅ Archivo temporal eliminado.")
    
def _normalizar_ruta_reporte(ruta_reporte):
    """Convierte la ruta recibida por el orquestador en una ruta absoluta válida."""
    ruta = os.path.abspath(os.fspath(ruta_reporte))

    if os.path.exists(ruta):
        return ruta

    # Compatibilidad si se pasa solamente "Amazon_report.txt".
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alternativa = os.path.normpath(
        os.path.join(script_dir, "..", "Extraer_Reporte", os.fspath(ruta_reporte))
    )

    if os.path.exists(alternativa):
        return alternativa

    return ruta


def _crear_indice_customizaciones(customizaciones):
    """Crea un índice O(1) por order-id + order-item-id."""
    indice = {}

    for item in customizaciones or []:
        order_id = str(item.get("order_id", "")).strip()
        order_item_id = str(item.get("order_item_id", "")).strip()

        if not order_id or not order_item_id:
            continue

        indice[(order_id, order_item_id)] = item

    return indice


def _leer_json_local(ruta_json):
    """Lee un JSON de customización previamente descargado."""
    with open(ruta_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _obtener_dato_fila(row, columna):
    """Devuelve un valor seguro desde una fila del reporte."""
    if columna in row and pd.notna(row[columna]):
        return str(row[columna])
    return ""


def _subir_archivo_local(ruta_archivo, nombre, mimetype, folder_id):
    """Sube un archivo local a Drive reutilizando upload_to_drive()."""
    with open(ruta_archivo, "rb") as archivo:
        contenido = archivo.read()

    return upload_to_drive(
        contenido,
        nombre,
        mimetype,
        folder_id
    )


def run_miaucraft_robot(ruta_reporte, customizaciones=None):
    """
    Ejecuta el robot productivo usando el mismo reporte y las mismas
    customizaciones preparadas previamente por el flujo principal.

    Ya no vuelve a descargar las customized-url de Amazon.
    """
    print("\n--- INICIANDO EL ROBOT PRODUCTIVO DE MIAUCRAFT ---")

    ruta_archivo = _normalizar_ruta_reporte(ruta_reporte)
    print(f"🔎 Leyendo órdenes desde: {ruta_archivo}")

    if not os.path.exists(ruta_archivo):
        print(f"❌ ERROR: No se encontró el reporte: {ruta_archivo}")
        return False

    try:
        df = pd.read_csv(ruta_archivo, sep="\t")
    except Exception as error:
        print(f"❌ ERROR leyendo el reporte: {error}")
        return False

    if customizaciones is None:
        print("❌ ERROR: No se recibieron las customizaciones preparadas.")
        print("❌ AMZCustomBot.py debe ejecutarse desde Produccion/main.py.")
        return False

    # Las customizaciones ya fueron descargadas por el orquestador.
    # Aquí solo se indexan para reutilizarlas sin nuevas llamadas a Amazon.
    indice_customizaciones = _crear_indice_customizaciones(customizaciones)

    # Google se inicializa únicamente cuando comienza el robot productivo.
    # Esto evita que importar AMZCustomBot.py fuerce un refresh OAuth prematuro.
    try:
        inicializar_servicios_google()
    except Exception as error:
        print(f"❌ No fue posible inicializar los servicios de Google: {error}")
        return False

    print(f"🚀 Iniciando procesamiento para {len(df)} órdenes...")
    print(
        f"📦 Customizaciones preparadas: {len(indice_customizaciones)} "
        f"(sin nuevas descargas)"
    )

    sobres = []
    procesadas = 0
    errores = 0
    omitidas = 0

    for index, row in df.iterrows():
        order_id = _obtener_dato_fila(row, "order-id")
        item_id = _obtener_dato_fila(row, "order-item-id")

        if not order_id or not item_id:
            print(f"⚠️ Fila {index + 1} sin order-id/order-item-id. Se omite.")
            omitidas += 1
            continue

        customized_url = _obtener_dato_fila(row, "customized-url")
        if not customized_url or customized_url.lower() == "nan":
            print(f"ℹ️ Orden {order_id}: sin customized-url. Se omite del robot personalizado.")
            omitidas += 1
            continue

        print()
        print("-" * 70)
        print(f"📦 ORDEN {index + 1}/{len(df)} | {order_id} | ITEM {item_id}")

        try:
            custom = indice_customizaciones.get((order_id, item_id))

            if not custom:
                raise FileNotFoundError(
                    f"No existe una customización preparada para "
                    f"{order_id} / {item_id}."
                )

            ruta_json = custom.get("json_path")
            ruta_imagen = custom.get("image_path")

            if not ruta_json or not os.path.exists(ruta_json):
                raise FileNotFoundError(
                    f"No se encontró el JSON preparado para {order_id} / {item_id}."
                )

            json_content = _leer_json_local(ruta_json)
            parsed_data = parse_custom_json(json_content)
            base_name = f"{order_id}_{item_id}"

            # ----------------------------------------------------
            # SUBIR JSON YA DESCARGADO
            # ----------------------------------------------------
            _subir_archivo_local(
                ruta_json,
                f"{base_name}.json",
                "application/json",
                IMAGE_FOLDER_ID
            )
            print(f"✅ JSON analizado y subido: {base_name}.json")

            # ----------------------------------------------------
            # SUBIR IMAGEN YA DESCARGADA
            # ----------------------------------------------------
            img_link = ""

            if ruta_imagen and os.path.exists(ruta_imagen):
                extension = os.path.splitext(ruta_imagen)[1].lower()
                if extension == ".png":
                    mimetype = "image/png"
                    nombre_drive = f"{base_name}.png"
                elif extension in (".jpg", ".jpeg"):
                    mimetype = "image/jpeg"
                    nombre_drive = f"{base_name}.jpg"
                else:
                    mimetype = "application/octet-stream"
                    nombre_drive = f"{base_name}{extension}"

                _, img_link = _subir_archivo_local(
                    ruta_imagen,
                    nombre_drive,
                    mimetype,
                    IMAGE_FOLDER_ID
                )
                print(f"✅ Imagen subida: {nombre_drive}")
            else:
                print("ℹ️ La customización no contiene imagen.")

            # ----------------------------------------------------
            # DATOS PARA GOOGLE SHEETS
            # ----------------------------------------------------
            consecutivo = index + 1

            valor_backup = parsed_data.get("BackUps", "").strip()
            if valor_backup.startswith("+") or valor_backup.startswith("="):
                valor_backup = "'" + valor_backup

            new_row = [
                consecutivo,
                _obtener_dato_fila(row, "order-id"),
                _obtener_dato_fila(row, "order-item-id"),
                _obtener_dato_fila(row, "buyer-name"),
                _obtener_dato_fila(row, "sku"),
                _obtener_dato_fila(row, "product-name"),
                _obtener_dato_fila(row, "quantity-purchased"),
                _obtener_dato_fila(row, "ship-service-level"),
                _obtener_dato_fila(row, "recipient-name"),
                _obtener_dato_fila(row, "ship-address-1"),
                _obtener_dato_fila(row, "ship-address-2"),
                _obtener_dato_fila(row, "ship-city"),
                _obtener_dato_fila(row, "ship-state"),
                _obtener_dato_fila(row, "ship-postal-code"),
                _obtener_dato_fila(row, "ship-country"),
                _obtener_dato_fila(row, "customized-page"),
                _obtener_dato_fila(row, "is-business-order"),
                _obtener_dato_fila(row, "purchase-order-number"),
                _obtener_dato_fila(row, "default-ship-from-address-name"),
                _obtener_dato_fila(row, "default-ship-from-address-field-1"),
                _obtener_dato_fila(row, "default-ship-from-address-field-2"),
                _obtener_dato_fila(row, "default-ship-from-city"),
                _obtener_dato_fila(row, "default-ship-from-state"),
                _obtener_dato_fila(row, "default-ship-from-country"),
                _obtener_dato_fila(row, "default-ship-from-postal-code"),
                _obtener_dato_fila(row, "delivery-Instructions"),
                parsed_data.get("Protection_Plan", ""),
                parsed_data.get("Size", ""),
                parsed_data.get("Furry_Name", ""),
                parsed_data.get("Species", ""),
                parsed_data.get("Gift_Box", ""),
                valor_backup,
                img_link,
                parsed_data.get("Email", ""),
                parsed_data.get("Phone_1", ""),
                parsed_data.get("Phone_2", ""),
                parsed_data.get("Phone_3", "")
            ]

            fecha = datetime.datetime.now()
            mes = MESES[fecha.month][:3]
            codigo = f"{mes}{fecha.day}-{consecutivo}"

            sobres.append({
                "Nombre": parsed_data.get("Furry_Name", ""),
                "Codigo": codigo
            })

            sheets_service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range="Amazon Extracted!A2",
                valueInputOption="USER_ENTERED",
                body={"values": [new_row]}
            ).execute()

            print(f"📝 Fila agregada ({consecutivo}): {order_id}")
            procesadas += 1

        except Exception as error:
            errores += 1
            print(f"❌ Error en la orden {order_id}: {error}")

    # ========================================================
    # GENERAR ARCHIVO PARA SOBRES
    # ========================================================

    if sobres:
        fecha = datetime.datetime.now()
        mes = MESES[fecha.month][:3]

        ruta = f"sobres_{fecha.year}-{mes}{fecha.day}.csv"

        df_sobres = pd.DataFrame(sobres)
        df_sobres.to_csv(
            ruta,
            index=False,
            encoding="utf-8-sig"
        )

        generar_pdf_sobres(ruta)

        if os.path.exists(ruta):
            os.remove(ruta)
            print("✅ CSV temporal de sobres eliminado.")
    else:
        print("ℹ️ No hubo órdenes procesadas; no se generará PDF de sobres.")

    # ========================================================
    # REPORTE FINAL UNIFICADO
    # ========================================================

    if procesadas > 0:
        export_multitab_pdf()
    else:
        print("ℹ️ No hubo órdenes exitosas; no se generará reporte final.")

    print()
    print("=" * 70)
    print("             ROBOT PRODUCTIVO COMPLETADO")
    print("=" * 70)
    print(f"Procesadas : {procesadas}")
    print(f"Errores    : {errores}")
    print(f"Omitidas   : {omitidas}")
    print("=" * 70)

    return errores == 0


if __name__ == "__main__":
    print("Este módulo debe ejecutarse desde Produccion/main.py.")
