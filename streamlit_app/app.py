import streamlit as st
from pathlib import Path
import numpy as np
import os
import json
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.efficientnet import preprocess_input as eff_preprocess
from PIL import Image
import tempfile
import matplotlib.pyplot as plt
import time
import cv2


# =====================================================
# CONFIG STREAMLIT
# PRO: https://explicit-content-classifier.streamlit.app/
# =====================================================
st.set_page_config(
    page_title="Explicit or illegal content classifier",
    page_icon="🎥",
    layout="centered"
)

# CSS personalizado
st.markdown("""
<style>
body {
    background-color: #0e1117;
}
div.stButton > button {
    background-color: #ff4b4b;
    color: white;
    border-radius: 10px;
    height: 3em;
    width: 100%;
    border: none;
    font-weight: bold;
}
.results-box {
    padding: 20px;
    background: #1e222b;
    border-radius: 15px;
    border: 1px solid #30343a;
    margin-top: 20px;
}
.pred-label {
    font-size: 20px;
    font-weight: bold;
    color: #4CAF50;
}
.pred-confidence {
    font-size: 22px;
    color: #f9c74f;
}
.st-emotion-cache-3uj0rx h1 {
    font-size: 2rem!important;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# CARGAR MODELO Y MAPEOS
# =====================================================
ROOT = Path(__file__).resolve().parent  # -> streamlit_app/
model_path = ROOT.parent / "models" / "final_effnetB3_classifier_6classes_14K.keras"
model = load_model(model_path)

indices_path = ROOT.parent / "notebooks" / "class_indices.json"

with open(indices_path, "r") as f:
    class_indices = json.load(f)
inv_class_indices = {v: k for k, v in class_indices.items()}

# =====================================================
# FUNCIONES DE PREDICCIÓN
# =====================================================
def predict_image(img_path):
    """Predice una imagen individual"""
    img = image.load_img(img_path, target_size=(300, 300))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = eff_preprocess(img_array)

    preds = model.predict(img_array)
    idx = np.argmax(preds[0])
    return inv_class_indices[idx], preds[0][idx], preds[0]

# saca una muestra de 10 frames por video
def predict_video(video_path, num_samples=10, target_size=(300, 300)):
    """Predice un video seleccionando solo N frames equidistantes."""

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, None, None

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        return None, None, None

    # Elegir 5 frames equidistantes
    frame_indices = np.linspace(0, total_frames - 1, num_samples, dtype=int)

    frames = []

    for frame_id in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = cap.read()
        if not ret:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, target_size)
        frame_preprocessed = eff_preprocess(np.expand_dims(frame_resized, axis=0))
        frames.append(frame_preprocessed)

    cap.release()

    if not frames:
        return None, None, None

    frames_array = np.vstack(frames)
    preds = model.predict(frames_array, batch_size=5, verbose=0)

    mean_preds = np.mean(preds, axis=0)
    idx = np.argmax(mean_preds)

    return inv_class_indices[idx], mean_preds[idx], preds


# =====================================================
# INTERFAZ STREAMLIT
# =====================================================

st.title("🎥 Explicit or illegal content classifier")
st.subheader("EfficientNetB3 Model — 6 Classes")

uploaded_file = st.file_uploader(
    "Upload an image or video",
    type=["jpg", "jpeg", "png", "mp4", "mov", "avi"]
)

st.markdown(
    """
    <style>
    .signature {
        position: fixed;
        bottom: 10px;
        right: 20px;
        font-size: 12px;
        color: #aaaaaa;
        text-align: right;
        opacity: 0.7;
        transition: opacity 0.3s ease;
    }
    .signature:hover {
        opacity: 1;
    }
    </style>

    <div class="signature">
        Developed by <b>afrancco@gmail.com</b>
    </div>
    """,
    unsafe_allow_html=True
)

if uploaded_file:

    # ============================
    # IMÁGENES
    # ============================
    if uploaded_file.type.startswith("image"):
        # Abrir imagen
        img = Image.open(uploaded_file)

        # Convertir a RGB si tiene canal alfa (RGBA, LA, P)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        # Mostrar imagen centrada
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(img, width=350)

        # Obtener la extensión original del archivo
        suffix = os.path.splitext(uploaded_file.name)[1].lower()

        # Guardar temporal respetando la extensión original
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            img.save(temp_path)

        # Placeholder de estado
        status = st.empty()
        status.info("⏳ Analyzing image...")

        # Predicción
        label, conf, preds = predict_image(temp_path)

        # Limpiar mensaje
        status.empty()

        # Mostrar resultados
        st.markdown(
            f"""
            <div class="results-box">
                <div class="pred-label">Prediction: <span style="color: #ffffff;">{label.upper()}</span></div>
                <div class="pred-confidence">Confidence: {conf*100:.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Probabilidades por clase
        st.subheader("Probabilities by class:")
        prob_df = {inv_class_indices[i]: float(preds[i]) for i in range(len(preds))}
        st.json(prob_df)


    # ============================
    # VIDEOS
    # ============================
    else:
        st.video(uploaded_file)

        # Guardar temporalmente
        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        with open(temp_path.name, "wb") as f:
            f.write(uploaded_file.getbuffer())

        status = st.empty()
        status.info("⏳ Analizing video...")

        label, conf, preds = predict_video(temp_path.name)

        # Simular procesamiento
        status.empty()
        if label is None:
            st.error("The video could not be processed.")
        else:
            st.markdown(
                f"""
                <div class="results-box">
                    <div class="pred-label">Prediction: <span style="color: #ffffff;">{label.upper()}</span></div>
                    <div class="pred-confidence">Average confidence: {conf*100:.2f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.subheader("📉 Probability per frame (plot)")
            fig, ax = plt.subplots(figsize=(10, 4))
            for i, cls in inv_class_indices.items():
                ax.plot([p[i] for p in preds], label=cls)
            ax.set_title("Evolution of frame-by-frame prediction")
            ax.legend()
            st.pyplot(fig)

            preds = preds[0]
            st.subheader("Probabilities by class:")
            prob_df = {inv_class_indices[i]: float(preds[i]) for i in range(len(preds))}
            st.json(prob_df)
