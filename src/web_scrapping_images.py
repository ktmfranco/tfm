import os, time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from pathlib import Path

# ---------- CONFIGURACIÓN ----------
# URL de la página que quieres scrapear
# EJEMPLOS:
#   https://es.images.search.yahoo.com/search/images;_ylt=AwrihPQ1ExNphgIsoLKV.Qt.;_ylu=c2VjA3NlYXJjaARzbGsDYnV0dG9u;_ylc=X1MDMjExNDcxNDAwNQRfcgMyBGZyAwRmcjIDcDpzLHY6aSxtOnNiLXRvcARncHJpZANBX0VBZXZNYlFjYU9SWGhSVFdVNnBBBG5fcnNsdAMwBG5fc3VnZwM4BG9yaWdpbgNlcy5pbWFnZXMuc2VhcmNoLnlhaG9vLmNvbQRwb3MDMARwcXN0cgMEcHFzdHJsAzAEcXN0cmwDOQRxdWVyeQN2aW9sZW5jaWEEdF9zdG1wAzE3NjI4NTc4MjY-?p=violencia&fr=&fr2=p%3As%2Cv%3Ai%2Cm%3Asb-top&ei=UTF-8&x=wrt
#       class_="sres-cntr"
#       
TARGET_URL = "https://es.images.search.yahoo.com/search/images;_ylt=AwrihPTdzhlpVn0ZbS.V.Qt.;_ylu=c2VjA3NlYXJjaARzbGsDYnV0dG9u;_ylc=X1MDMjExNDcxNDAwNQRfcgMyBGZyAwRmcjIDcDpzLHY6aSxtOnNiLXRvcARncHJpZAN0eG1pQVNIc1RLZUxMYjZPMVhMMURBBG5fcnNsdAMwBG5fc3VnZwMxMARvcmlnaW4DZXMuaW1hZ2VzLnNlYXJjaC55YWhvby5jb20EcG9zAzAEcHFzdHIDBHBxc3RybAMwBHFzdHJsAzE5BHF1ZXJ5A3RhcmpldGFzJTIwZGUlMjBjcmVkaXRvBHRfc3RtcAMxNzYzMjk5MDQ1?p=familia&fr=&fr2=p%3As%2Cv%3Ai%2Cm%3Asb-top&ei=UTF-8&x=wrt"
OUT_DIR    = "images"
DELAY_BETWEEN = 2.0   # segundos de espera entre descargas
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
# -----------------------------------

# identificamos la ruta actual del directorio del script
path_script = Path(__file__).resolve()
path_parent = path_script.parent
OUT_DIR = os.path.join(path_parent, OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36"
}

cookies = {
    "YS": "v=1&safesearch=off"
}

# 1. Descargar el HTML de la página
resp = requests.get(TARGET_URL, headers=headers, timeout=20)
resp.raise_for_status()

# 2. Analizar el HTML
soup = BeautifulSoup(resp.text, "html.parser")

# 3. Encontrar todas las etiquetas <img>
container = soup.find("div", class_="sres-cntr")
img_tags = container.find_all("img") if container else []

# 4. Recorrer y descargar cada imagen
for img in tqdm(img_tags, desc="Descargando imágenes"):
    src = img.get("src")
    if not src or src.startswith("data:"):
        continue  # ignorar imágenes embebidas en base64 u otras sin src
    # convertir URL relativa a absoluta
    img_url = urljoin(TARGET_URL, src)
    # nombre de archivo a partir de la URL
    filename = os.path.basename(urlparse(img_url).path)
    if not filename:
        continue
   
    out_path = os.path.join(OUT_DIR, filename)
    # Verificar si el nombre viene sin extensión para agregarsela (pasa con google y yahoo)
    root, ext = os.path.splitext(out_path)
    if ext not in IMAGE_EXTS:  # si tiene extensión, no lo cambiamos
        out_path = out_path + ".jpeg"  # le añadimos .jpeg
   
    try:
        r = requests.get(img_url, stream=True, headers=headers, timeout=30)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024*32):
                if chunk:
                    f.write(chunk)
        print(f"✅ Guardada: {out_path}")
        time.sleep(DELAY_BETWEEN)  # respetar el servidor
    except Exception as e:
        print(f"Error al descargar {img_url}: {e}")

print(f"✅ Imágenes guardadas en la carpeta: {OUT_DIR}")