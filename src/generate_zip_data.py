#!/usr/bin/env python3
import shutil
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True

# ---------------- CONFIG ----------------
ROOT = Path(__file__).resolve().parent  # -> src/
data_path = ROOT.parent 
SRC_DIR = Path(data_path / "data")        # directorio fuente
DST_DIR = Path(data_path / "data_")       # copia destino solicitada
ZIP_NAME =  Path(data_path / "data_")            # nombre base del .zip resultante -> produces data_.zip
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.mpeg', '.mpg', '.flv', '.ogg', '.3gp', '.ts'}
# ----------------------------------------

def remove_if_exists(p: Path):
    if p.exists():
        print(f"Eliminando existente: {p} ...")
        shutil.rmtree(p)
        print("Eliminado.")

def copy_directory(src: Path, dst: Path):
    if not src.exists():
        raise FileNotFoundError(f"Directorio origen no existe: {src}")
    print(f"Copiando '{src}' -> '{dst}' ...")
    shutil.copytree(src, dst)
    print("Copia completada.")

def delete_video_files(root: Path, exts:set):
    removed_count = 0
    print(f"Borrando ficheros de vídeo (*.{', *.'.join(e.lstrip('.') for e in exts)}) dentro de '{root}' ...")
    for folder, dirs, files in os.walk(root):
        for fname in files:
            fpath = Path(folder) / fname
            if fpath.suffix.lower() in exts:
                try:
                    fpath.unlink()
                    removed_count += 1
                    # opcional: print cada archivo borrado (comenta si muchos)
                    print(f"  - Eliminado: {fpath}")
                except Exception as e:
                    print(f"  ! Error eliminando {fpath}: {e}")
    print(f"Borrados {removed_count} ficheros de vídeo.")
    return removed_count

def make_zip(root: Path, zip_base_name: str):
    # shutil.make_archive('data_', 'zip', root_dir='data_') -> crea data_.zip en CWD
    print(f"Comprimiendo '{root}' en '{zip_base_name}.zip' ...")
    archive_path = shutil.make_archive(zip_base_name, 'zip', root_dir=str(root))
    print(f"ZIP creado: {archive_path}")
    return Path(archive_path)

def main():
    try:
        # 1) eliminar data_ si existe (para reproducibilidad)
        if DST_DIR.exists():
            print(f"El directorio destino '{DST_DIR}' ya existe.")
            remove_if_exists(DST_DIR)

        # 2) copiar directorio
        copy_directory(SRC_DIR, DST_DIR)

        # 3) eliminar ficheros de video dentro de data_
        delete_video_files(DST_DIR, VIDEO_EXTS)

        # 4) crear zip de data_
        zip_path = make_zip(DST_DIR, ZIP_NAME)

        # 5️) Eliminar la carpeta data_ tras comprimir
        print(f"🧹 Eliminando carpeta temporal '{DST_DIR}' ...")
        shutil.rmtree(DST_DIR)
        print(f"✅ Carpeta '{DST_DIR}' eliminada correctamente.")

        print("Proceso finalizado correctamente.")
        print(f"Archivo final: {zip_path.resolve()}")

    except Exception as exc:
        print("Ha ocurrido un error:", exc)

if __name__ == "__main__":
    main()
