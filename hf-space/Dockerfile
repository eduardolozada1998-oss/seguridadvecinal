FROM python:3.11-slim

# Librerías del sistema: OpenCV + Tesseract + DeepFace
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tesseract-ocr \
    tesseract-ocr-spa \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar modelo YOLOv8n ONNX en build time (no penaliza startup)
RUN wget -q -O /app/yolov8n.onnx \
    "https://huggingface.co/amikelive/yolov8n-onnx/resolve/main/yolov8n.onnx" \
    || wget -q -O /app/yolov8n.onnx \
    "https://github.com/niconielsen32/YOLOv8ONNX/releases/download/v1.0/yolov8n.onnx" \
    || echo "YOLO no descargado — se intentara en runtime"

# Pre-calentar DeepFace (descarga modelo Facenet ~90 MB)
RUN python -c "from deepface.basemodels import Facenet; Facenet.loadModel()" || true

COPY . .

# HuggingFace Spaces expone el puerto 7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
