import base64
import glob
import os
import re
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

import config
from drive_service import sincronizar_disenos_drive, buscar_svg_local


# ============================================================
# CONFIGURACIÓN Y CONSTANTES
# ============================================================

SVG_NS = "http://www.w3.org/2000/svg"
FONTS_DIR = getattr(config, "FONTS_DIR", r"C:\p_wk1\Motor\Fuentes")
TAG_DIAMETER_MM = getattr(config, "TAG_DIAMETER_MM", 30.0)

ET.register_namespace("", SVG_NS)

# Caché de fuentes ya cargadas: ruta -> (glyph_set, cmap, units_per_em, metrics)
_FONT_CACHE = {}


# ============================================================
# LÓGICA DE BÚSQUEDA Y VECTORIZACIÓN DE FUENTES
# ============================================================

def extraer_ft_id(cadena_json):
    """
    Extrae la clave 'FTXX' del texto.
    Ejemplos:
      'Silent Arc (FT 12)' -> 'FT12'
      'Vestige Legacy(FT18)' -> 'FT18'
    """
    if not cadena_json:
        return None
    match = re.search(r"FT\s*(\d+)", cadena_json, re.IGNORECASE)
    return f"FT{match.group(1)}" if match else None


@lru_cache(maxsize=None)
def buscar_archivo_fuente(cadena_json):
    """
    Busca en FONTS_DIR la carpeta/archivo que empiece con el ID (ej: 'FT12*')
    y retorna la ruta completa al archivo .ttf u .otf.
    Cacheada: el mismo ID de fuente se repite entre distintos slots/pedidos.
    """
    ft_id = extraer_ft_id(cadena_json)
    if not ft_id:
        return None

    coincidencias = glob.glob(os.path.join(FONTS_DIR, f"{ft_id}*"))
    if not coincidencias:
        print(f"      [WARN] No se encontró carpeta para la fuente: '{ft_id}' ({cadena_json})")
        return None

    ruta_encontrada = coincidencias[0]

    if os.path.isdir(ruta_encontrada):
        fuentes = glob.glob(os.path.join(ruta_encontrada, "*.ttf")) + \
                  glob.glob(os.path.join(ruta_encontrada, "*.otf"))
        return fuentes[0] if fuentes else None

    if ruta_encontrada.lower().endswith(('.ttf', '.otf')):
        return ruta_encontrada

    return None


def _cargar_fuente(ruta_fuente):
    """
    Carga (o recupera de caché) el glyph set, cmap y métricas de una fuente.
    Evita reabrir y reparsear el mismo archivo TTF/OTF en cada texto/línea.
    """
    datos_fuente = _FONT_CACHE.get(ruta_fuente)
    if datos_fuente:
        return datos_fuente

    font = TTFont(ruta_fuente)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()

    head = font.get('head')
    units_per_em = float(getattr(head, 'unitsPerEm', 1000)) if head else 1000.0

    hmtx = font.get('hmtx')
    metrics = hmtx.metrics if hmtx else {}

    datos_fuente = (glyph_set, cmap, units_per_em, metrics)
    _FONT_CACHE[ruta_fuente] = datos_fuente
    return datos_fuente


def _obtener_nombre_familia_fuente(ruta_fuente):
    """
    Obtiene el nombre interno de familia de la fuente TTF/OTF.
    Este nombre es el que se entrega a SVG mediante font-family para que
    aplicaciones como xTool puedan tratar el contenido como texto real.
    """
    try:
        font = TTFont(ruta_fuente)

        # 1 = Family name
        # 16 = Typographic Family Name (si existe)
        nombres_preferidos = (16, 1)

        for name_id in nombres_preferidos:
            for record in font["name"].names:
                if record.nameID != name_id:
                    continue

                try:
                    nombre = record.toUnicode().strip()
                except Exception:
                    continue

                if nombre:
                    return nombre

    except Exception as e:
        print(f"      [WARN] No se pudo obtener el nombre interno de la fuente: {e}")

    return Path(ruta_fuente).stem


def crear_texto_vectorizado(slot_group, texto_str, ruta_fuente, font_size_mm=4.5, pos_y_mm=0.0):
    """
    Crea el texto como un único elemento SVG <text>, NO como paths.

    Esto permite que programas compatibles con texto SVG, como xTool,
    puedan identificar la cadena completa como texto en lugar de recibir
    cada letra como un vector independiente.

    La fuente sigue obteniéndose exactamente desde la carpeta de fuentes
    existente del proyecto. No se cambia el sistema actual de búsqueda FTXX.
    """
    if not ruta_fuente or not os.path.exists(ruta_fuente):
        print(f"      [WARN] No se pudo crear texto '{texto_str}': Ruta de fuente no encontrada.")
        return

    if not texto_str:
        return

    try:
        glyph_set, cmap, units_per_em, metrics = _cargar_fuente(ruta_fuente)

        # ------------------------------------------------------------
        # 1. Calcular el ancho real usando las métricas de la fuente.
        #    Esto conserva el centrado que ya funcionaba con los paths.
        # ------------------------------------------------------------
        total_units_x = 0

        for char in texto_str:
            glyph_name = cmap.get(ord(char))

            if not glyph_name or glyph_name not in glyph_set:
                # Mantener el comportamiento anterior: ignorar caracteres
                # que la fuente no pueda representar.
                continue

            if glyph_name in metrics:
                advance_width = metrics[glyph_name][0]
            else:
                advance_width = getattr(
                    glyph_set[glyph_name],
                    "width",
                    units_per_em * 0.5
                )

            total_units_x += advance_width

        if total_units_x <= 0:
            return

        # ------------------------------------------------------------
        # 2. Convertir el ancho calculado a milímetros para centrar.
        # ------------------------------------------------------------
        scale = font_size_mm / units_per_em
        total_width_mm = total_units_x * scale
        offset_x = -(total_width_mm / 2.0)

        # SVG usa el baseline para posicionar <text>.
        # Este ajuste conserva aproximadamente la posición vertical
        # utilizada anteriormente por los paths vectorizados.
        offset_y = pos_y_mm + (font_size_mm * 0.35)

        # ------------------------------------------------------------
        # 3. Crear UN SOLO <text>.
        #
        #    Antes:
        #       <g> -> <g> -> <path> por cada letra
        #
        #    Ahora:
        #       <text>Nombre completo</text>
        #
        #    Así xTool recibe la cadena como texto y no como letras
        #    vectoriales independientes.
        # ------------------------------------------------------------
        font_family = _obtener_nombre_familia_fuente(ruta_fuente)

        text_element = ET.SubElement(
            slot_group,
            f"{{{SVG_NS}}}text",
            {
                "id": f"txt_{texto_str.replace(' ', '_')}",
                "x": f"{offset_x:.4f}",
                "y": f"{offset_y:.4f}",
                "font-family": font_family,
                "font-size": f"{font_size_mm:.4f}",
                "fill": "#000000",
                "text-anchor": "start",
            }
        )

        text_element.text = texto_str

        print(
            f"      [TEXT] '{texto_str}' → fuente '{font_family}' "
            f"| tamaño {font_size_mm:.4f} mm"
        )

    except Exception as e:
        print(f"      [ERROR] No se pudo crear el texto '{texto_str}': {e}")


def crear_texto_multilinea_vectorizado(
    slot_group,
    lineas,
    ruta_fuente,
    font_size_mm,
    inicio_y_mm,
    salto_linea_mm
):
    """
    Crea TODAS las líneas del reverso (rescue_info) como UN SOLO <text>
    editable, SIN <tspan>: el salto de línea va embebido como "\\n" real
    dentro del propio contenido del <text>.

    Historial del problema:
      1) Antes: un <path> por LETRA -> xTool trataba cada letra como
         un objeto independiente.
      2) Se cambió a <text> real -> arregló el problema de las letras,
         pero cada línea del reverso seguía siendo su propio <text>.
      3) Un <text> con un <tspan> por línea (con "x" propio por línea,
         y luego con "x" constante + text-anchor middle) -> en ambos
         casos xTool seguía separando cada línea al hacer doble clic.
      4) Fusionar todo en un único <path> vectorial -> quedó como un
         solo objeto, pero dejó de ser texto editable (imagen).

    Pista clave: al escribir el texto multilínea A MANO dentro de xTool
    (con Enter), sí quedó como un solo objeto. Eso indica que xTool
    probablemente guarda su texto nativo como UNA sola cadena con
    saltos de línea reales, no como varios <tspan>. Este intento
    replica exactamente eso: un <text> con \\n embebido, sin tspans.

    Nota: el estándar SVG estricto no garantiza salto de línea visual
    con \\n plano (algunos visores lo colapsan en una sola línea). Se
    agrega xml:space="preserve" como ayuda adicional, pero el objetivo
    principal es que xTool, específicamente, lo reconozca como un solo
    objeto igual que su propio texto nativo.
    """
    if not ruta_fuente or not os.path.exists(ruta_fuente):
        print(
            "      [WARN] No se pudo crear el texto del reverso: "
            "Ruta de fuente no encontrada."
        )
        return

    lineas_validas = [linea for linea in lineas if linea]

    if not lineas_validas:
        return

    try:
        font_family = _obtener_nombre_familia_fuente(ruta_fuente)

        # Y del primer renglón (igual cálculo que antes para la línea 0)
        primer_y = inicio_y_mm + (font_size_mm * 0.35)

        text_element = ET.SubElement(
            slot_group,
            f"{{{SVG_NS}}}text",
            {
                "id": f"txt_reverso_{lineas_validas[0].replace(' ', '_')}",
                "x": "0",
                "y": f"{primer_y:.4f}",
                "font-family": font_family,
                "font-size": f"{font_size_mm:.4f}",
                "fill": "#000000",
                "text-anchor": "middle",
                "{http://www.w3.org/XML/1998/namespace}space": "preserve",
            }
        )

        text_element.text = "\n".join(lineas_validas)

        print(
            f"      [TEXT] Reverso ({len(lineas_validas)} línea(s)) → "
            f"fuente '{font_family}' | tamaño {font_size_mm:.4f} mm "
            f"(un solo <text>, sin tspans, \\n embebido)"
        )

    except Exception as e:
        print(f"      [ERROR] No se pudo crear el texto del reverso: {e}")


# ============================================================
# INSERTAR DISEÑO VECTORIAL EN EL SLOT
# ============================================================

def insertar_diseno_vectorial(slot_group, diseno_str):
    """
    Escala e inyecta el diseño (SVG o PNG/JPG vía Base64) para que ocupe el TAMAÑO COMPLETO
    del Tag definido en config.TAG_DIAMETER_MM.
    """
    filepath = buscar_svg_local(diseno_str)

    if not filepath or not filepath.exists():
        print(f"      [WARN] No se encontró el diseño para: '{diseno_str}'")
        return

    area_max_mm = TAG_DIAMETER_MM

    # ------------------------------------------------------------
    # CASO 1: IMÁGENES RASTERIZADAS (PNG / JPG / JPEG)
    # ------------------------------------------------------------
    if filepath.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        try:
            mime_type = "image/png" if filepath.suffix.lower() == ".png" else "image/jpeg"
            b64_data = base64.b64encode(filepath.read_bytes()).decode("utf-8")
            offset_xy = -(area_max_mm / 2.0)

            ET.SubElement(
                slot_group,
                f"{{{SVG_NS}}}image",
                {
                    "id": f"art_{filepath.stem.replace(' ', '_')}",
                    "x": f"{offset_xy:.4f}",
                    "y": f"{offset_xy:.4f}",
                    "width": f"{area_max_mm:.4f}",
                    "height": f"{area_max_mm:.4f}",
                    "preserveAspectRatio": "xMidYMid meet",
                    "href": f"data:{mime_type};base64,{b64_data}"
                }
            )
        except Exception as e:
            print(f"      [ERROR] Fallo al procesar la imagen {diseno_str}: {e}")
        return

    # ------------------------------------------------------------
    # CASO 2: VECTORES (SVG)
    # ------------------------------------------------------------
    try:
        root = ET.parse(filepath).getroot()

        viewbox = root.attrib.get("viewBox")
        if viewbox:
            parts = [float(p) for p in re.split(r'[\s,]+', viewbox.strip()) if p]
            vb_w, vb_h = parts[2], parts[3]
        else:
            vb_w = float(re.sub(r"[^\d.]", "", root.attrib.get("width", "100")))
            vb_h = float(re.sub(r"[^\d.]", "", root.attrib.get("height", "100")))

        if vb_w <= 0 or vb_h <= 0:
            return

        scale = min(area_max_mm / vb_w, area_max_mm / vb_h)
        offset_x = -(vb_w * scale) / 2.0
        offset_y = -(vb_h * scale) / 2.0

        art_group = ET.SubElement(
            slot_group,
            f"{{{SVG_NS}}}g",
            {
                "id": f"art_{filepath.stem.replace(' ', '_')}",
                "transform": f"translate({offset_x:.4f}, {offset_y:.4f}) scale({scale:.6f})"
            }
        )

        for child in list(root):
            tag_clean = child.tag.split("}")[-1].lower() if "}" in child.tag else child.tag.lower()
            if tag_clean not in ("defs", "style", "metadata"):
                art_group.append(child)

    except Exception as e:
        print(f"      [ERROR] Fallo al procesar el vector {diseno_str}: {e}")


# ============================================================
# CARA TRASERA: WRAP + ESCALADO DINÁMICO DE LÍNEAS
# ============================================================

MAX_CHARS_POR_LINEA = 22


def _envolver_lineas(rescue_info):
    """Divide rescue_info en líneas, partiendo las que excedan MAX_CHARS_POR_LINEA."""
    lineas = []

    for linea in (l.strip() for l in rescue_info.splitlines() if l.strip()):
        if len(linea) <= MAX_CHARS_POR_LINEA or " " not in linea:
            lineas.append(linea)
            continue

        linea_actual = ""
        for palabra in linea.split(" "):
            candidata = (linea_actual + " " + palabra).strip()
            if len(candidata) <= MAX_CHARS_POR_LINEA:
                linea_actual = candidata
            else:
                if linea_actual:
                    lineas.append(linea_actual)
                linea_actual = palabra
        if linea_actual:
            lineas.append(linea_actual)

    return lineas


def _calcular_tamano_letra(lineas):
    """Escala dinámicamente el tamaño de letra según ancho/alto del bloque de texto."""
    max_longitud = max(len(l) for l in lineas)
    total_lineas = len(lineas)

    tamano_letra = TAG_DIAMETER_MM * 0.085

    if max_longitud > 18:
        tamano_letra = min(tamano_letra, (TAG_DIAMETER_MM / max_longitud) * 1.1)

    if total_lineas >= 4:
        tamano_letra = min(tamano_letra, (TAG_DIAMETER_MM / (total_lineas * 2.2)))

    return tamano_letra


def _componer_cara_trasera(slot_group, datos):
    rescue_info = datos.get("rescue_info", "")
    fuente_rescue_raw = datos.get("fuente_rescue")
    ruta_fuente = buscar_archivo_fuente(fuente_rescue_raw)

    lineas = _envolver_lineas(rescue_info)

    if lineas:
        tamano_letra = _calcular_tamano_letra(lineas)
        salto_linea = tamano_letra * 1.30
        inicio_y = -((len(lineas) - 1) * salto_linea) / 2.0

        crear_texto_multilinea_vectorizado(
            slot_group=slot_group,
            lineas=lineas,
            ruta_fuente=ruta_fuente,
            font_size_mm=tamano_letra,
            inicio_y_mm=inicio_y,
            salto_linea_mm=salto_linea
        )

    return lineas, fuente_rescue_raw


# ============================================================
# CARA FRONTAL: DISEÑO + NOMBRE
# ============================================================

def _componer_cara_frontal(slot_group, datos):
    nombre = datos.get("nombre_mascota", "N/A")
    fuente_nombre_raw = datos.get("fuente_nombre")
    diseno = (
        datos.get("diseno_tag")
        or datos.get("diseno")
        or datos.get("design_file")
    )

    tiene_diseno = (
        bool(diseno)
        and str(diseno).strip().upper() != "N/A"
    )

    if tiene_diseno:
        insertar_diseno_vectorial(
            slot_group,
            diseno
        )

    ruta_fuente = buscar_archivo_fuente(
        fuente_nombre_raw
    )

    tamano_letra = TAG_DIAMETER_MM * 0.13

    crear_texto_vectorizado(
        slot_group=slot_group,
        texto_str=nombre,
        ruta_fuente=ruta_fuente,
        font_size_mm=tamano_letra,
        pos_y_mm=0.0
    )

    return (
        nombre,
        diseno if tiene_diseno else None,
        fuente_nombre_raw,
        tamano_letra
    )


# ============================================================
# INSERTAR DATOS EN EL SVG (FRONT Y BACK)
# ============================================================

def insertar_datos_en_svg(svg_path, datos_lote, output_path, cara="front"):

    print()
    print("=" * 70)

    if cara == "front":
        print("                    GENERANDO DISEÑO FRONT")
    elif cara == "back":
        print("                    GENERANDO DISEÑO BACK")
    else:
        print(f"                    GENERANDO DISEÑO {cara.upper()}")

    print("=" * 70)

    if cara == "front":
        print("\n[INFO] Sincronizando diseños desde Google Drive...")

        sincronizar_disenos_drive()

        print("[OK] Diseños sincronizados.")

    print(
        f"\n[INFO] Abriendo SVG base ({cara}):\n"
        f"       {svg_path}"
    )

    root = ET.parse(svg_path).getroot()

    for item in datos_lote:

        numero_slot = item["slot"]
        datos = item["datos"]

        slot_group = root.find(
            f".//*[@id='slot_{numero_slot}']"
        )

        if slot_group is None:

            print(
                f"[ERROR] No se encontró slot_{numero_slot}."
            )

            continue

        if cara == "front":

            (
                nombre,
                diseno,
                fuente_nombre,
                tamano_letra
            ) = _componer_cara_frontal(
                slot_group,
                datos
            )

            texto_diseno = (
                diseno
                if diseno
                else "Sin diseño"
            )

            nombre_log = str(
                nombre
            ).replace(
                "\n",
                " / "
            ).strip()

            fuente_log = (
                str(fuente_nombre).strip()
                if fuente_nombre
                else "Sin fuente"
            )

            print(
                f"[OK] Slot {numero_slot:<2} → "
                f"{texto_diseno:<25} | "
                f"{nombre_log} | "
                f"{fuente_log} | "
                f"{tamano_letra:.4f} mm"
            )

        elif cara == "back":

            (
                lineas,
                fuente_rescue_raw
            ) = _componer_cara_trasera(
                slot_group,
                datos
            )

            fuente_log = (
                str(fuente_rescue_raw).strip()
                if fuente_rescue_raw
                else "Sin fuente"
            )

            cantidad_lineas = len(lineas)

            texto_lineas = (
                "línea"
                if cantidad_lineas == 1
                else "líneas"
            )

            print(
                f"[OK] Slot {numero_slot:<2} → "
                f"{cantidad_lineas} {texto_lineas} | "
                f"{fuente_log}"
            )
        else:

            print(
                f"[WARN] Cara no reconocida: {cara}"
            )

    # ========================================================
    # GUARDAR SVG
    # ========================================================

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    ET.ElementTree(root).write(
        output_path,
        encoding="utf-8",
        xml_declaration=True
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    print()

    print(
        f"[OK] SVG compuesto ({cara}) generado correctamente."
    )

    print(
        f"     {output_path}"
    )

    print("=" * 70)

    return output_path