#!/usr/bin/env python3
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from tqdm import tqdm
from pathlib import Path

# ---------- CONFIGURACIÓN ----------
""" repositories: 
    https://es.xhamster.com/ container = soup.find("div", class_="subsection mono index-videos mixed-section")
    https://cumguru.com/es/videos/accidente container = soup.find("ul", id="content", class_="content")
"""
TARGET_URL = "https://cumguru.com/es/videos/anime"   # URL de la página que quieres scrapear (página 1)
OUT_DIR    = "images"
DELAY_BETWEEN = 2.0   # segundos de espera entre descargas
START_PAGE = 1
END_PAGE = 10
# -----------------------------------

# identificamos la ruta actual del directorio del script
path_script = Path(__file__).resolve()
path_parent = path_script.parent
OUT_DIR = os.path.join(path_parent, OUT_DIR)


os.makedirs(OUT_DIR, exist_ok=True)

headers = {"User-Agent": "Mozilla/5.0 (compatible; ImageScraper/1.0)"}

def normalize_url_no_query(full_url):
    """
    Normaliza la URL quitando query y fragment para evitar duplicados
    ejemplo: https://site/img.jpg?v=1  -> https://site/img.jpg
    """
    p = urlparse(full_url)
    p2 = p._replace(query="", fragment="")
    return urlunparse(p2)

def build_page_url(root_url, page_number):
    root = root_url.rstrip("/")
    if page_number == 1:
        return root + "/"
    else:
        return f"{root}/{page_number}"

seen_urls = set()  # URLs normalizadas ya descargadas

for page in range(START_PAGE, END_PAGE + 1):
    page_url = build_page_url(TARGET_URL, page)
    print(f"\n[+] Procesando página {page}: {page_url}")

    # 1. Descargar el HTML de la página
    try:
        resp = requests.get(page_url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[!] Error al obtener {page_url}: {e}")
        continue

    # 2. Analizar el HTML
    soup = BeautifulSoup(resp.text, "html.parser")

    # 3. Encontrar todas las etiquetas <img> dentro del contenedor que usabas
    container = soup.find("ul", id="content", class_="content")
    img_tags = container.find_all("img") if container else []

    if not img_tags:
        print(f"[i] No se encontraron imágenes en la página {page} (contenedor no encontrado o vacío).")
        continue

    # 4. Recorrer y descargar cada imagen (mismo comportamiento original)
    for img in tqdm(img_tags, desc=f"Descargando imágenes (pág {page})", leave=True):
        src = img.get("src")
        if not src or src.startswith("data:"):
            continue  # ignorar imágenes embebidas en base64 u otras sin src

        # convertir URL relativa a absoluta usando la URL de la página actual
        img_url = urljoin(page_url, src)

        # Normalizar para comparar duplicados (quita query y fragment)
        norm = normalize_url_no_query(img_url)
        if norm in seen_urls:
            # ya la hemos visto / descargado (o una versión con query diferente)
            continue

        # nombre de archivo a partir de la URL (misma lógica que tenías)
        filename = os.path.basename(urlparse(img_url).path)
        if not filename:
            continue

        out_path = os.path.join(OUT_DIR, filename)

        # Si ya existe el archivo, asumimos que ya está y no volvemos a descargarlo
        if os.path.exists(out_path):
            seen_urls.add(norm)  # marcar como vista para evitar reintentos
            continue

        try:
            r = requests.get(img_url, stream=True, headers=headers, timeout=30)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024*32):
                    if chunk:
                        f.write(chunk)
            # marcar como descargada usando la URL normalizada
            seen_urls.add(norm)
            time.sleep(DELAY_BETWEEN)  # respetar el servidor
        except Exception as e:
            print(f"Error al descargar {img_url}: {e}")

print(f"\n✅ Imágenes guardadas en la carpeta: {OUT_DIR}")
