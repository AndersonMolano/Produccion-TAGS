import ctypes
import os
import shutil
import sys
import winreg
from pathlib import Path

# ============================================================
# INSTALADOR DE FUENTES - MIAUCRAFT / MOTOR TAGS
# ============================================================

MOTOR_DIR = Path(__file__).resolve().parent
FUENTES_DIR = MOTOR_DIR / "Fuentes"

# Carpeta de fuentes de Windows.
WINDOWS_FONTS_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

# Registro de fuentes instaladas para Windows.
REGISTRY_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"

# Mensaje de Windows para avisar a las aplicaciones que cambiaron las fuentes.
WM_FONTCHANGE = 0x001D
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002


def es_administrador():
    """Comprueba si el script tiene permisos de administrador."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ejecutar_como_administrador():
    """
    Reinicia este mismo script solicitando permisos de administrador.
    Así puedes ejecutarlo normalmente con:
        py instalar_fuentes.py
    """
    if es_administrador():
        return True

    print("[INFO] Se requieren permisos de administrador.")
    print("[INFO] Windows mostrará una ventana de confirmación UAC...")

    parametros = " ".join(f'"{arg}"' for arg in sys.argv)

    resultado = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        parametros,
        None,
        1
    )

    if resultado <= 32:
        print("[ERROR] No fue posible solicitar permisos de administrador.")
        input("\nPresiona ENTER para cerrar...")
        return False

    # El proceso elevado continuará por separado.
    return False


def obtener_nombre_registro(font_path):
    """
    Genera un nombre estable para la entrada del registro.
    El nombre visible de la fuente lo determina el propio archivo.
    """
    return font_path.stem


def instalar_fuente(font_path):
    """
    Copia la fuente a C:\\Windows\\Fonts, la registra en Windows
    y notifica el cambio al sistema.
    """
    nombre_archivo = font_path.name
    destino = WINDOWS_FONTS_DIR / nombre_archivo

    try:
        # --------------------------------------------------------
        # 1. Copiar fuente a la carpeta oficial de Windows
        # --------------------------------------------------------
        if not destino.exists():
            shutil.copy2(font_path, destino)
            accion = "INSTALADA"
        else:
            # Si ya existe, no la copiamos nuevamente.
            accion = "YA EXISTÍA"

        # --------------------------------------------------------
        # 2. Registrar la fuente en Windows
        # --------------------------------------------------------
        nombre_registro = obtener_nombre_registro(font_path)

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            REGISTRY_PATH,
            0,
            winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(
                key,
                nombre_registro,
                0,
                winreg.REG_SZ,
                nombre_archivo
            )

        # --------------------------------------------------------
        # 3. Avisar a Windows que se agregó/cambió una fuente
        # --------------------------------------------------------
        ctypes.windll.gdi32.AddFontResourceW(str(destino))

        return True, accion

    except PermissionError:
        return False, "SIN PERMISOS"
    except Exception as e:
        return False, f"ERROR: {e}"


def notificar_cambio_fuentes():
    """Notifica a las aplicaciones abiertas que cambió la lista de fuentes."""
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_FONTCHANGE,
            0,
            0,
            SMTO_ABORTIFHUNG,
            5000,
            None
        )
    except Exception:
        pass


def main():
    print("=" * 70)
    print("        INSTALADOR DE FUENTES - MIAUCRAFT / MOTOR TAGS")
    print("=" * 70)
    print()

    if not es_administrador():
        if ejecutar_como_administrador():
            pass
        else:
            # El proceso original termina. El proceso elevado continúa.
            return

    if not FUENTES_DIR.exists():
        print("[ERROR] No se encontró la carpeta de fuentes:")
        print(f"        {FUENTES_DIR}")
        print()
        input("Presiona ENTER para cerrar...")
        return

    # Buscar todas las fuentes dentro de FTXX y subcarpetas.
    fuentes = sorted(
        [
            p for p in FUENTES_DIR.rglob("*")
            if p.is_file()
            and p.suffix.lower() in (".ttf", ".otf")
        ],
        key=lambda p: str(p).lower()
    )

    if not fuentes:
        print("[ERROR] No se encontraron archivos .ttf o .otf.")
        print(f"        Carpeta revisada: {FUENTES_DIR}")
        print()
        input("Presiona ENTER para cerrar...")
        return

    print(f"[OK] Carpeta de fuentes encontrada:")
    print(f"     {FUENTES_DIR}")
    print()
    print(f"[OK] Fuentes encontradas: {len(fuentes)}")
    print()

    instaladas = 0
    existentes = 0
    errores = []

    for indice, fuente in enumerate(fuentes, start=1):
        relativa = fuente.relative_to(FUENTES_DIR)

        print(f"[{indice:02}/{len(fuentes):02}] {relativa}")

        ok, resultado = instalar_fuente(fuente)

        if ok:
            if resultado == "INSTALADA":
                instaladas += 1
                print("       [+] INSTALADA")
            else:
                existentes += 1
                print("       [=] YA EXISTÍA")
        else:
            errores.append((fuente, resultado))
            print(f"       [X] {resultado}")

        print()

    notificar_cambio_fuentes()

    print("=" * 70)
    print("                    RESULTADO")
    print("=" * 70)
    print()
    print(f"Fuentes encontradas : {len(fuentes)}")
    print(f"Nuevas instaladas   : {instaladas}")
    print(f"Ya existentes       : {existentes}")
    print(f"Con errores         : {len(errores)}")
    print()

    if errores:
        print("FUENTES CON ERROR:")
        for fuente, error in errores:
            print(f"  - {fuente}")
            print(f"    {error}")
        print()

    print("IMPORTANTE:")
    print(f"Las fuentes fueron buscadas automáticamente dentro de:")
    print(f"  {FUENTES_DIR}")
    print()
    print("1. Cierra completamente xTool Studio / XCS si está abierto.")
    print("2. Vuelve a abrir xTool.")
    print("3. Abre nuevamente el SVG generado.")
    print("4. Comprueba si las fuentes ya no aparecen como 'no disponibles'.")
    print()

    if instaladas > 0:
        print("[OK] Las fuentes nuevas fueron registradas en Windows.")
    else:
        print("[INFO] No fue necesario instalar fuentes nuevas.")

    print()
    input("Presiona ENTER para cerrar...")


if __name__ == "__main__":
    main()
