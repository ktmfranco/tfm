import pandas as pd
import random

# Cargar inventario
#df = pd.read_csv("data/inventory.csv")

# Seleccionar 50 imágenes aleatorias
sample_df = df.sample(n=50, random_state=42).reset_index(drop=True)

results = []

for i, row in enumerate(sample_df.itertuples(), 1):
    img_path = row.relative_path  # asegúrate de que esta columna existe
    true_label = row.category  # asegúrate de que esta columna existe

    try:
        # Predicción
        pred_label, confidence = predict_image(img_path)

        # Guardar resultado
        results.append({
            "img": img_path,
            "true_label": true_label,
            "pred_label": pred_label,
            "confidence": float(confidence)
        })

        print(f"[{i}/30] {img_path}")
        print(f"  → True label: {true_label}")
        print(f"  → Pred label: {pred_label}  (conf: {confidence:.4f})\n")

    except Exception as e:
        print(f"Error procesando {img_path}: {e}")