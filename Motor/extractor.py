import json
import os


# ============================================================
# BUSCADOR RECURSIVO DE NODOS
# ============================================================

def buscar_nodos_por_tipo(objeto, tipo_buscado, resultado=None):

    if resultado is None:
        resultado = []

    if isinstance(objeto, dict):

        if objeto.get("type") == tipo_buscado:
            resultado.append(objeto)

        for valor in objeto.values():
            buscar_nodos_por_tipo(
                valor,
                tipo_buscado,
                resultado
            )

    elif isinstance(objeto, list):

        for item in objeto:
            buscar_nodos_por_tipo(
                item,
                tipo_buscado,
                resultado
            )

    return resultado


# ============================================================
# EXTRAER DATOS
# ============================================================

def extraer_detalles_completos(datos):

    info = {
        "nombre_mascota": "N/A",
        "fuente_nombre": "N/A",
        "tamano_nombre": "N/A",
        "color_nombre": "N/A",
        "color_tag": "N/A",
        "diseno_tag": "N/A",
        "rescue_info": "N/A",
        "fuente_rescue": "N/A",
    }

    # ========================================================
    # COLOR DEL TAG
    # ========================================================

    titulo = datos.get("title", "")

    titulo_lower = titulo.lower()

    if "golden" in titulo_lower:
        info["color_tag"] = "Golden / Dorado"

    elif "silver" in titulo_lower:
        info["color_tag"] = "Silver / Plateado"

    elif "black" in titulo_lower:
        info["color_tag"] = "Black / Negro"


    # ========================================================
    # DATOS DE CUSTOMIZACIÓN (se extrae aquí porque el bloque de
    # DISEÑO, más abajo, también necesita buscar dentro de esto)
    # ========================================================

    custom_data = datos.get(
        "customizationData",
        {}
    )


    # ========================================================
    # DISEÑO DEL TAG
    # ========================================================
    # El diseño puede venir en distintos formatos según el pedido:
    #   1) area "Stylish Designs" dentro de version3.0.surfaces[].areas[]
    #      (formato más común)
    #   2) nodo "OptionCustomization" con name="Stylish Designs" dentro
    #      de customizationData (formato alterno de Amazon)
    #   3) si no hay diseño de colección, puede venir un MOTIF/SÍMBOLO/
    #      ÍCONO en su lugar. El nombre del campo varía según el pedido:
    #      "Motif", "Motifs BOTTOM", "Symbol", "Icon TOP", etc.
    #   4) igual que el 3, pero en formato OptionCustomization
    # Se prueba en ese orden y se usa el primero que aparezca.

    surfaces = (
        datos
        .get("version3.0", {})
        .get("customizationInfo", {})
        .get("surfaces", [])
    )

    areas = surfaces[0].get("areas", []) if surfaces else []

    def _valor_desde_areas(coincide_nombre):
        for area in areas:
            if coincide_nombre(area.get("name", "").lower()):
                valor = area.get("optionValue")
                if valor:
                    return valor
        return None

    def _valor_desde_option_customization(coincide_nombre):
        nodos = buscar_nodos_por_tipo(custom_data, "OptionCustomization")
        for nodo in nodos:
            if coincide_nombre(nodo.get("name", "").lower()):
                valor = (
                    nodo.get("optionSelection", {}).get("name")
                    or nodo.get("displayValue")
                )
                if valor:
                    return valor
        return None

    es_stylish_design = lambda nombre: nombre == "stylish designs"

    # El campo del motif/símbolo/ícono varía de un pedido a otro: a veces
    # es "Motif", a veces "Motifs BOTTOM", a veces "Symbol" o "Icon TOP",
    # etc. Por eso se acepta CUALQUIER nombre que contenga alguna de estas
    # palabras clave, siempre que NO sea el selector de posición (ese no
    # trae el nombre del diseño, solo dice "Top"/"Bottom"/"Left"/"Right").
    PALABRAS_CLAVE_MOTIF = ("motif", "symbol", "icon")

    def es_motif(nombre):
        return (
            any(palabra in nombre for palabra in PALABRAS_CLAVE_MOTIF)
            and "position" not in nombre
        )

    diseno = (
        _valor_desde_areas(es_stylish_design)
        or _valor_desde_option_customization(es_stylish_design)
        or _valor_desde_areas(es_motif)
        or _valor_desde_option_customization(es_motif)
    )

    if diseno:
        info["diseno_tag"] = diseno


    # ========================================================
    # PROCESAR CONTENEDORES (nombre, fuente, color, texto)
    # ========================================================

    contenedores = buscar_nodos_por_tipo(
        custom_data,
        "ContainerCustomization"
    )


    # ========================================================
    # PROCESAR CONTENEDORES
    # ========================================================

    for contenedor in contenedores:

        nombre_padre = contenedor.get(
            "name",
            ""
        )

        if not nombre_padre:
            continue


        nombre_lower = nombre_padre.lower()


        # ----------------------------------------------------
        # IDENTIFICAR TIPO DE CONTENEDOR
        # ----------------------------------------------------

        es_nombre = (
            "name" in nombre_lower
            or "peludo" in nombre_lower
            or "furry" in nombre_lower
        )

        es_reverso = (
            "back" in nombre_lower
            or "rescue" in nombre_lower
            or "info" in nombre_lower
        )

        if not es_nombre and not es_reverso:
            continue


        # ====================================================
        # FUENTE
        # ====================================================

        nodos_fuente = buscar_nodos_por_tipo(
            contenedor,
            "FontCustomization"
        )

        if nodos_fuente:

            family = (
                nodos_fuente[0]
                .get("fontSelection", {})
                .get("family", "N/A")
            )

            if es_nombre:
                info["fuente_nombre"] = family

            elif es_reverso:
                info["fuente_rescue"] = family


        # ====================================================
        # COLOR DEL TEXTO
        # ====================================================

        nodos_color = buscar_nodos_por_tipo(
            contenedor,
            "ColorCustomization"
        )

        if nodos_color:

            color_selection = (
                nodos_color[0]
                .get("colorSelection", {})
            )

            nombre_color = color_selection.get(
                "name",
                "N/A"
            )

            valor_color = color_selection.get(
                "value",
                "N/A"
            )

            color = (
                f"{nombre_color} "
                f"({valor_color})"
            )

            info["color_nombre"] = color


        # ====================================================
        # PLACEMENT / TEXTO
        # ====================================================

        nodos_placement = buscar_nodos_por_tipo(
            contenedor,
            "PlacementContainerCustomization"
        )

        if not nodos_placement:
            continue

        placement = nodos_placement[0]


        # ----------------------------------------------------
        # DIMENSIONES
        # ----------------------------------------------------

        dimension = placement.get(
            "dimension",
            {}
        )

        width = dimension.get(
            "width",
            "N/A"
        )

        height = dimension.get(
            "height",
            "N/A"
        )

        tamano = f"{width}x{height}"


        # ----------------------------------------------------
        # TEXTO
        # ----------------------------------------------------

        nodos_texto = buscar_nodos_por_tipo(
            placement,
            "TextCustomization"
        )

        texto = "N/A"

        if nodos_texto:

            texto = nodos_texto[0].get(
                "inputValue",
                "N/A"
            )

            if isinstance(texto, str):
                texto = texto.strip()


        # ----------------------------------------------------
        # GUARDAR DATOS
        # ----------------------------------------------------

        if es_nombre:

            info["nombre_mascota"] = texto
            info["tamano_nombre"] = tamano

        elif es_reverso:

            info["rescue_info"] = texto


    return info


# ============================================================
# LEER JSON
# ============================================================

def obtener_datos_json(ruta_json):

    if not os.path.exists(ruta_json):

        raise FileNotFoundError(
            f"No se encontró el archivo JSON: {ruta_json}"
        )

    with open(
        ruta_json,
        "r",
        encoding="utf-8"
    ) as archivo:

        datos = json.load(archivo)

    return extraer_detalles_completos(datos)