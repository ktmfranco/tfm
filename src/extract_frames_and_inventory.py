#!/usr/bin/env python3
"""
extract_frames_and_inventory.py
- Instalar ffmpeg/ffprobe en python: pip install ffmpeg-python
- Ejecutar: python extract_frames_and_inventory.py --root data --csv inventory.csv --change_names True
- Lee estructura: <root>/<categoria>/* (acepta múltiples extensiones de vídeo e imagen)
- Si una categoría tiene vídeos, crea <root>/<categoria>/frames/ y extrae hasta 3 frames por vídeo:
    * si duration < 4.0s -> timestamps = [0, 2, 3]
    * else                  -> timestamps = [0, 2, 4]
  Cada frame se etiqueta en orden: train, val, test.
- Genera CSV con columnas:
    category, source_type (video|image), filename, timestamps_extracted, output_path, split
  Incluye en el CSV también las imágenes existentes en cada categoría (cualquier extensión),
  con source_type="image" y split="image".
- Requiere ffmpeg y ffprobe en PATH.
"""
from pathlib import Path
from shutil import rmtree
from pathlib import Path
from math import floor
from PIL import Image

import sys
sys.dont_write_bytecode = True

import generate_zip_data
import subprocess
import argparse
import shutil
import random
import time
import json
import csv
import os

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Extensiones reconocidas
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.mpeg', '.mpg', '.flv', '.ogg', '.3gp', '.ts'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

DST_DIR = Path("data_")       # copia destino solicitada
ZIP_NAME = "data_"            # nombre base del .zip resultante -> produces data_.zip

SPLITS = ['train', 'val', 'test']

TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1
SEED = 42

corrupted_images = []

def is_video_file(p: Path):
    return p.is_file() and p.suffix.lower() in VIDEO_EXTS

def is_image_file(p: Path):
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS

# Filtrar imágenes corruptas. 
# No almacenamos aquellas imagenes corruptas en la lista de imagenes para la categoría
# Aquellas imagenes corruptas se eliminan del disco y al final se muestran en pantalla
def is_valid_image(p: Path):
    is_jfif = False
    try:
        with Image.open(p) as img:
            img.verify()  # intenta decodificarla sin cargarla completa
        is_jfif = True
    except Exception:
        corrupted_images.append(p)
        is_jfif = False
        try:
            os.remove(p) # Delete corrupted image
        except Exception as del_err:
            print(f"❌ Error al eliminar {p}: {del_err}")

    return is_jfif

def gather_category_files(root: Path, change_names: bool):
    """
    Recorre root y devuelve dict:
      { category_path: {'videos':[Path,...], 'images':[Path,...]} , ... }
    Solo incluye directorios que contengan al menos videos or images (images are included
    even if there are no videos).
    """
    cats = {}
    if not root.exists():
        return cats
    for cat in sorted(root.iterdir()):
        if not cat.is_dir():
            continue
        videos = [p for p in sorted(cat.iterdir()) if is_video_file(p)]

        # Si queremos cambiar el nombre de las imagenes (change_names vendría a True) 
        # Recorremos todas las imagenes en la carpeta de la categoría y cambiamos el nombre de cada una para que se componga de
        # el nombre de la categoría seguido de un guion y un numero aleatorio
        if change_names:
            print(f"  Cambiando nombres de las imagenes de la categoria {cat.name}")
            images = [p for p in sorted(cat.iterdir()) if is_image_file(p) if is_valid_image(p)]
            change = random.randint(1, 50)
            contador = 1
            for img in images:
                name_image = img.name
                base_name, ext = os.path.splitext(img)
                name_image = f"{cat.name}{change}_{contador:04d}{ext}"
                new_path = img.parent / name_image
                img.rename(new_path)
                contador += 1

        images = [p for p in sorted(cat.iterdir()) if is_image_file(p) if is_valid_image(p)]
        # include categories that have either images or videos
        if videos or images:
            cats[cat] = {'videos': videos, 'images': images}
    return cats

def get_duration_seconds(video_path: Path):
    """Devuelve duración en segundos (float) usando ffprobe. 0.0 si error."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return float(out.decode().strip())
    except Exception:
        return 0.0

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def cap_timestamp(ts: float, duration: float):
    """Asegura ts <= duration - eps. Si duration==0 devuelve 0"""
    eps = 0.001
    if duration <= 0.0:
        return 0.0
    return min(ts, max(0.0, duration - eps))

def extract_frame_at_timestamp(video_path: Path, timestamp: float, out_path: Path):
    """
    Extrae un frame con ffmpeg en timestamp (segundos).
    Usa -ss antes de -i para posicionamiento rápido.
    """
    ensure_dir(out_path.parent)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",   # calidad jpeg razonable
        "-y",          # sobrescribir si existe
        str(out_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def timestamps_choice(duration: float):
    """
    Según la regla solicitada:
    - si duration < 4.0 -> [0, 2, 3]
    - else               -> [0, 2, 4]
    Luego capea cada timestamp a duration - eps si supera duración.
    """
    if duration < 2.0:
        base_ts = [0.3, 0.5, 1.0]
    elif duration >= 2.0 and duration < 3.0:
        base_ts = [0.3, 1.0, 1.8]
    elif duration >= 3.0 and duration < 4.0:
        base_ts = [0.5, 1.5, 2.8]
    elif duration >= 4.0 and duration < 5.0:
        base_ts = [1.0, 2.0, 3.8]
    elif duration >= 5.0 and duration < 6.0:
        base_ts = [1.0, 2.5, 4.8]    
    else:
        base_ts = [0.0, 2.5, 5.0]

    capped = [cap_timestamp(t, duration) for t in base_ts]
    # Opcional: si todos los timestamps quedan iguales (vídeo muy corto),
    # podemos deduplicar para evitar extraer mismo fotograma 3 veces.
    # Pero mantendremos 3 intentos (ffmpeg extraerá el mismo instante si es necesario).
    return capped

def split_elements_by_ratio(image_paths):
    """
    image_paths: list[Path]
    devuelve: dict split -> list[Path]
    """
    assert abs(TRAIN_RATIO + VAL_RATIO + TEST_RATIO - 1.0) < 1e-6
    n = len(image_paths)
    if n == 0:
        return {'train': [], 'val': [], 'test': []}

    random.seed(SEED)
    imgs = list(image_paths)
    random.shuffle(imgs)

    # conteos iniciales por redondeo
    n_train = int(round(n * TRAIN_RATIO))
    n_val = int(round(n * VAL_RATIO))
    # asegurar que n_train + n_val <= n
    if n_train + n_val > n:
        n_val = max(0, n - n_train)
    n_test = n - n_train - n_val

    # si hay muy pocos y un split queda 0, reequilibrar mínimamente:
    # reglas simples:
    if n >= 3:
        # asegurar que cada split tenga al menos 1 si es posible
        if n_train == 0:
            n_train = 1
        if n_val == 0:
            # darle 1 a val si hay suficiente
            if n - n_train >= 1:
                n_val = 1
        # recompute n_test
        n_test = n - n_train - n_val
        if n_test < 0:
            # ajustar reduciendo val primero, luego train
            if n_val > 0:
                diff = -n_test
                take = min(diff, n_val - 1) if n_val > 1 else min(diff, n_val)
                n_val -= take
            n_test = n - n_train - n_val
    else:
        # n = 1 o 2 -> fallback sencillo
        if n == 1:
            n_train, n_val, n_test = 1, 0, 0
        elif n == 2:
            n_train, n_val, n_test = 1, 1, 0

    # finalmente slice
    train_imgs = imgs[:n_train]
    val_imgs = imgs[n_train:n_train + n_val]
    test_imgs = imgs[n_train + n_val:]

    return {'train': train_imgs, 'val': val_imgs, 'test': test_imgs}

def process(root: Path, csv_out: Path, change_names: bool):
    if not root.exists():
        print("No existe el directorio", root)
        return

    if not root.is_dir():
        print("No es un directorio:", root)
        return

    #concatenar las rutas de root y csv
    csv_out_tmp = os.path.join(root, csv_out)
    # Si el fichero inventario.csv ya existe, lo borramos
    if os.path.exists(csv_out_tmp):
        os.remove(csv_out_tmp)

    cats = gather_category_files(root, change_names)
    if not cats:
        print("No se encontraron categorías con vídeos ni imágenes en", root)
        return

    # Prepara CSV
    csv_fieldnames = ['category', 'source_type', 'filename', 'timestamps_extracted', 'output_path', 'relative_path', 'split']
    csv_rows = []

    for cat_path, contents in cats.items():
        videos = contents['videos']
        images = contents['images']
        relative_path = cat_path
        # Solo crear frames dir si hay videos en la categoría (requisito)
        # Eliminar primero directorio frames si ya existe
        frames_dir = cat_path / "frames"
        if frames_dir.is_dir():
            rmtree(frames_dir)
        frames_root = frames_dir if videos else None

        if frames_root is not None:
            ensure_dir(frames_root)
            print(f"Categoria '{cat_path.name}': {len(videos)} videos, {len(images)} imágenes -> frames en {frames_root}")
        else:
            print(f"Categoria '{cat_path.name}': {len(videos)} videos, {len(images)} imágenes -> NO se crea 'frames' (no hay videos)")

        # Primero procesar VIDEOS (si los hay), extrayendo dataframes
        vid_splits = split_elements_by_ratio(videos)
        for split_name in SPLITS:
            for vid_path in vid_splits[split_name]:
            #for vid in videos:
                duration = get_duration_seconds(vid_path)
                ts_list = timestamps_choice(duration)
                video_base = vid_path.stem
                print(f"  Procesando video: {vid_path.name} (dur={duration:.2f}s) -> timestamps: {ts_list}")

                # Por cada timestamp, extraer y asignar split en orden
                for idx, ts in enumerate(ts_list):
                    out_dir = frames_root / split_name
                    ensure_dir(out_dir)
                    out_fname = out_dir / f"frame_{video_base}_{idx+1:06d}.jpg"
                    success = extract_frame_at_timestamp(vid_path, ts, out_fname)
                    out_path_str = str(out_fname.resolve()) if success else ""
                    # Guardar fila CSV por cada frame intentado (si falló se registra path vacío)
                    csv_rows.append({
                        'category': cat_path.name,
                        'source_type': 'video',
                        'filename': vid_path.name,
                        'timestamps_extracted': json.dumps([round(ts, 3)]),  # guardamos el timestamp de este frame como JSON list de 1
                        'output_path': out_path_str,
                        'relative_path': out_fname,
                        'split': split_name
                    })
                    if success:
                        print(f"    - {split_name}: {out_fname.name}  (t={ts:.3f}s)")
                    else:
                        print(f"    !! fallo extrayendo (t={ts:.3f}s) de {vid_path.name}")

        # Luego agregar imágenes existentes en la categoría al CSV (no crear frames por esto)
        # antes de iterar imágenes en una categoría:
        img_splits = split_elements_by_ratio(images)

        for split_name in SPLITS:
            for img_path in img_splits[split_name]:
                csv_rows.append({
                    'category': cat_path.name,
                    'source_type': 'image',
                    'filename': img_path.name,
                    'timestamps_extracted': '',
                    'output_path': str(img_path.resolve()),
                    'relative_path': img_path,
                    'split': split_name
                })
    
    # Escribir CSV
    ensure_dir(root)
    with open(f"{root}/{csv_out}", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)

    print(f"\nCSV generado en: {csv_out}  (filas: {len(csv_rows)})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrae frames (3 por vídeo) y genera CSV inventario (incluye imágenes).")
    parser.add_argument("--root", default="data", help="Directorio raíz con subcarpetas por categoría (default: data)")
    parser.add_argument("--csv", default="inventory.csv", help="Ruta CSV de salida (default: inventory.csv)")
    parser.add_argument("--change_names", default=False, help="Indica si quiere que se cambien los nombres de la s imagenes (default: true)")
    args = parser.parse_args()
    
    time_start = time.perf_counter()
    process(Path(args.root), Path(args.csv), args.change_names)

    # Generar ZIP de data
    generate_zip_data.main()

    time_end = time.perf_counter()
    time_total = time_end - time_start
    time_total = time_total / 60

    print(f"\n✅ Proceso completado {time_total:.2f} minutos")

    print(f"\n Imágenes corruptas: {len(corrupted_images)}: ", corrupted_images)

