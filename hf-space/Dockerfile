FROM python:3.11-slim

# Librerias del sistema necesarias para OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# HuggingFace requiere usuario con UID 1000
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Pre-descargar yolov8n.pt en build time (evita descarga al iniciar)
RUN python -c 'from ultralytics import YOLO; YOLO("yolov8n.pt"); print("yolov8n.pt OK")' \
    || echo 'YOLO pre-download fallo, se intentara en runtime'

# Pre-descargar modelos EasyOCR (en build time, no en el primer request)
RUN python -c 'import easyocr; easyocr.Reader(["es","en"], gpu=False, verbose=False); print("EasyOCR OK")' \
    || echo 'EasyOCR pre-download fallo'

COPY --chown=user . /app

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
