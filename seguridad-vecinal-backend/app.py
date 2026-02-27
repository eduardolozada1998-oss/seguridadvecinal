"""
Sistema de Seguridad Vecinal — Backend
Detección con YOLOv8 ONNX + OpenCV + Tesseract OCR.
Optimizado para Render.com FREE plan (512 MB RAM).

RAM estimada en runtime:
  onnxruntime-cpu  ~100 MB
  opencv-headless  ~80  MB
  pytesseract      ~50  MB
  Total:           ~290 MB  ✅  (cabe en 512 MB gratis)
"""

import os
import re
import json
import base64
import shutil
import time
import threading
import imaplib
import email
import email.header
import smtplib
import urllib.request
import urllib.error
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import cv2
import numpy as np
import pytesseract
from PIL import Image
from fastapi import FastAPI
from supabase import create_client
import onnxruntime as ort

# ─────────────────────────────────────────────
#  Variables de entorno
# ─────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GMAIL_USER   = os.environ.get("GMAIL_USER", "")
GMAIL_PASS   = os.environ.get("GMAIL_PASS", "")
EMAIL_ALERTA = os.environ.get("EMAIL_ALERTA", GMAIL_USER)

# HuggingFace Space de reconocimiento facial (vacío = desactivado)
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "").rstrip("/")

# Ruta del binario tesseract — auto-detecta si no está en la variable de entorno
_tess_env = os.environ.get("TESSERACT_CMD", "")
TESSERACT_CMD = _tess_env or shutil.which("tesseract") or "/usr/bin/tesseract"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Clases COCO relevantes para seguridad
CLASE_PERSONA   = 0
CLASES_VEHICULO = {2, 3, 5, 7}          # auto, moto, bus, camión
CLASES_INTERES  = [CLASE_PERSONA] + list(CLASES_VEHICULO)
YOLO_INPUT_SIZE = 640
CONF_THRESHOLD  = 0.5
IOU_THRESHOLD   = 0.45

# URLs ONNX — GitHub solo publica .pt, estos son mirrors comunitarios públicos
URL_YOLO_ONNX_FALLBACKS = [
    "https://github.com/ibaiGorordo/ONNX-YOLOv8-Object-Detection/releases/download/v1.0/yolov8n.onnx",
    "https://github.com/WuJunde/yolov8_onnx/releases/download/v1.0/yolov8n.onnx",
]
URL_HAARCASCADE = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

# HOG para personas (fallback si YOLO no está disponible — ya incluido en OpenCV)
_hog_detector = None

# ─────────────────────────────────────────────
#  Estado global (se inicializa en lifespan)
# ─────────────────────────────────────────────
supabase_client  = None
yolo_session     = None   # onnxruntime.InferenceSession
face_cascade     = None   # cv2.CascadeClassifier
yolo_input_name  = None

# Serializa inferencia entre hilos (onnxruntime no es 100% thread-safe en CPU)
_modelo_lock = threading.Lock()


# ─────────────────────────────────────────────
#  Helper descarga
# ─────────────────────────────────────────────

def _decodificar_filename(raw: str) -> str:
    """Decodifica filename con RFC 2047 (=?utf-8?B?...?= o =?utf-8?Q?...?=)."""
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
        decoded = ""
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded += part.decode(charset or "utf-8", errors="replace")
            else:
                decoded += part
        return decoded.strip()
    except Exception:
        return raw


def _descargar_si_falta(url: str, destino: str, descripcion: str) -> bool:
    if os.path.exists(destino):
        print(f"✅ {descripcion} ya existe en disco")
        return True
    print(f"📥 Descargando {descripcion} ({url}) ...")
    try:
        urllib.request.urlretrieve(url, destino)
        tam_kb = os.path.getsize(destino) // 1024
        print(f"✅ {descripcion} descargado ({tam_kb} KB)")
        return True
    except Exception as e:
        print(f"❌ Error descargando {descripcion}: {e}")
        return False


def _descargar_yolo_con_fallbacks(destino: str) -> bool:
    for url in URL_YOLO_ONNX_FALLBACKS:
        print(f"📥 Descargando YOLOv8n ONNX desde {url} ...")
        try:
            urllib.request.urlretrieve(url, destino)
            tam_kb = os.path.getsize(destino) // 1024
            print(f"✅ YOLOv8n ONNX descargado ({tam_kb} KB)")
            return True
        except Exception as e:
            print(f"⚠️  Falló {url}: {e}")
            if os.path.exists(destino):
                os.remove(destino)
    print("❌ No se pudo descargar YOLOv8n ONNX desde ninguna fuente")
    return False


# ─────────────────────────────────────────────
#  Inicialización / lifespan (FastAPI moderno)
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa todos los recursos al arrancar. Sin PyTorch."""
    global supabase_client, yolo_session, yolo_input_name, face_cascade

    print("🚀 Iniciando Sistema de Seguridad Vecinal (ONNX — plan gratuito)...")

    # Validar variables de entorno
    vars_faltantes = [v for v in ["SUPABASE_URL", "SUPABASE_KEY", "GMAIL_USER", "GMAIL_PASS"]
                      if not os.environ.get(v)]
    if vars_faltantes:
        print(f"⚠️  Variables faltantes: {', '.join(vars_faltantes)}")

    # Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase conectado")
    else:
        print("❌ Supabase no configurado")

    # Haarcascade OpenCV
    if _descargar_si_falta(URL_HAARCASCADE, "haarcascade_frontalface_default.xml", "Haarcascade"):
        cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        face_cascade = cascade if not cascade.empty() else None
        print("✅ Face cascade cargado" if face_cascade else "❌ Face cascade inválido")

    # YOLOv8n ONNX (~6 MB) — sin PyTorch
    if _descargar_yolo_con_fallbacks("yolov8n.onnx"):
        try:
            so = ort.SessionOptions()
            so.intra_op_num_threads = 2
            so.inter_op_num_threads = 2
            yolo_session = ort.InferenceSession(
                "yolov8n.onnx",
                sess_options=so,
                providers=["CPUExecutionProvider"],
            )
            yolo_input_name = yolo_session.get_inputs()[0].name
            print(f"✅ YOLOv8n ONNX cargado (entrada: '{yolo_input_name}')")
        except Exception as e:
            print(f"❌ Error cargando YOLO ONNX: {e}")

    # Tesseract OCR
    try:
        ver = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR v{ver} disponible")
    except Exception as e:
        print(f"❌ Tesseract no encontrado: {e} — verifica buildCommand en render.yaml")

    # Lector de emails
    if GMAIL_USER and GMAIL_PASS:
        hilo = threading.Thread(target=_bucle_leer_emails, daemon=True, name="email-reader")
        hilo.start()
        print("📬 Lector de emails iniciado (polling cada 30 s)")
    else:
        print("⚠️  Gmail no configurado — emails deshabilitados")

    # HOG People Detector — fallback si YOLO falla (no requiere descarga)
    global _hog_detector
    _hog_detector = cv2.HOGDescriptor()
    _hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    print("✅ HOG people detector listo (fallback para YOLO)")

    print("✅ Sistema listo")
    yield
    print("🛑 Sistema detenido")


app = FastAPI(
    title="Seguridad Vecinal API",
    description="Backend con YOLOv8 ONNX + OpenCV + Tesseract (sin PyTorch)",
    version="2.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
#  Inferencia YOLO ONNX  (reemplaza ultralytics)
# ─────────────────────────────────────────────

def _letterbox(frame: np.ndarray, size: int = 640):
    """Redimensiona manteniendo ratio; rellena con negro hasta size×size."""
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    return canvas, scale


def _inferir_yolo(frame: np.ndarray) -> list:
    """
    Corre YOLOv8n ONNX. Devuelve lista de:
    {'cls': int, 'conf': float, 'box': (x1,y1,x2,y2)}
    """
    if yolo_session is None:
        return []

    h_orig, w_orig = frame.shape[:2]
    canvas, scale = _letterbox(frame, YOLO_INPUT_SIZE)

    # BGR→RGB, HWC→NCHW, normalizar [0,1]
    blob = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = blob[np.newaxis]

    with _modelo_lock:
        outputs = yolo_session.run(None, {yolo_input_name: blob})

    # output[0]: [1, 84, 8400]  →  [8400, 84]
    preds       = outputs[0][0].T
    boxes_raw   = preds[:, :4]     # cx, cy, w, h
    class_conf  = preds[:, 4:]     # 80 scores COCO

    class_ids  = np.argmax(class_conf, axis=1)
    confianzas = np.max(class_conf, axis=1)

    mask = (confianzas >= CONF_THRESHOLD) & np.isin(class_ids, CLASES_INTERES)
    if not mask.any():
        return []

    boxes_raw  = boxes_raw[mask]
    class_ids  = class_ids[mask]
    confianzas = confianzas[mask]

    # cx,cy,w,h → x1,y1,x2,y2 en coordenadas originales
    bx, by, bw, bh = boxes_raw[:, 0], boxes_raw[:, 1], boxes_raw[:, 2], boxes_raw[:, 3]
    x1 = np.clip((bx - bw / 2) / scale, 0, w_orig).astype(int)
    y1 = np.clip((by - bh / 2) / scale, 0, h_orig).astype(int)
    x2 = np.clip((bx + bw / 2) / scale, 0, w_orig).astype(int)
    y2 = np.clip((by + bh / 2) / scale, 0, h_orig).astype(int)

    # NMS
    boxes_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
    indices   = cv2.dnn.NMSBoxes(boxes_nms, confianzas.tolist(), CONF_THRESHOLD, IOU_THRESHOLD)

    detecciones = []
    if len(indices) > 0:
        for i in np.array(indices).flatten():
            detecciones.append({
                "cls":  int(class_ids[i]),
                "conf": round(float(confianzas[i]), 3),
                "box":  (int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])),
            })
    return detecciones


# ─────────────────────────────────────────────
#  OCR de placas con Tesseract  (reemplaza EasyOCR)
# ─────────────────────────────────────────────

def _leer_placa_ocr(roi: np.ndarray) -> str:
    """Lee texto de una placa vehicular con Tesseract."""
    if roi is None or roi.size == 0:
        return ""
    try:
        h, w = roi.shape[:2]
        # Escalar si el ROI es demasiado pequeño
        if h < 40:
            factor = 80 / h
            roi = cv2.resize(roi, (int(w * factor), 80), interpolation=cv2.INTER_CUBIC)
        gris = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binario = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img_pil = Image.fromarray(binario)
        config  = (
            "--psm 7 --oem 3 "
            "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        )
        texto = pytesseract.image_to_string(img_pil, lang="spa+eng", config=config)
        limpio = re.sub(r"[^A-Z0-9\-]", "", texto.strip().upper())
        return limpio if len(limpio) >= 3 else ""
    except Exception as e:
        print(f"⚠️  Error OCR placa: {e}")
        return ""


# ─────────────────────────────────────────────
#  Detección de rostros (OpenCV — sin cambios)
# ─────────────────────────────────────────────

def _detectar_rostros(frame: np.ndarray) -> tuple[int, list]:
    """Detecta rostros en frame BGR. Devuelve (cantidad, coords)."""
    if face_cascade is None:
        return 0, []
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    coords = face_cascade.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return (len(coords), list(coords)) if len(coords) > 0 else (0, [])


# ─────────────────────────────────────────────
#  Reconocimiento facial vía HuggingFace Space
# ─────────────────────────────────────────────

def _reconocer_rostro_hf(face_frame: np.ndarray, camara_id: str = "00") -> dict:
    """
    Envía un recorte de rostro al HF Space y devuelve el resultado.
    Retorna dict con: conocido, nombre, confianza
    Si HF_SPACE_URL está vacío o hay error → devuelve desconocido.
    """
    if not HF_SPACE_URL:
        return {"conocido": False, "nombre": "desconocido", "confianza": 0.0}
    try:
        # Codificar recorte a JPEG base64
        ok, buf = cv2.imencode(".jpg", face_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            return {"conocido": False, "nombre": "desconocido", "confianza": 0.0}
        b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

        payload = json.dumps({"imagen_b64": b64, "camara_id": camara_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{HF_SPACE_URL}/reconocer",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resultado = json.loads(resp.read().decode("utf-8"))
        print(
            f"🤖 HF Space reconoció: {resultado.get('nombre')} "
            f"| confianza={resultado.get('confianza', 0):.3f} "
            f"| conocido={resultado.get('conocido')}"
        )
        return resultado
    except urllib.error.URLError as e:
        print(f"⚠️  HF Space no accesible: {e}")
    except Exception as e:
        print(f"⚠️  Error en reconocimiento facial HF: {e}")
    return {"conocido": False, "nombre": "desconocido", "confianza": 0.0}


# ─────────────────────────────────────────────
#  Consulta placas registradas (Supabase)
# ─────────────────────────────────────────────

def _buscar_placa_registrada(placa: str) -> str | None:
    if not supabase_client or not placa:
        return None
    placa_limpia = placa.replace(" ", "").upper()
    try:
        result = (
            supabase_client.table("placas_registradas")
            .select("placa, nombre")
            .eq("activo", True)
            .execute()
        )
        for row in result.data:
            if row["placa"].replace(" ", "").upper() == placa_limpia:
                return row["nombre"]
    except Exception as e:
        print(f"⚠️  Error consultando placas_registradas: {e}")
    return None


# ─────────────────────────────────────────────
#  Procesamiento de foto
# ─────────────────────────────────────────────

def procesar_foto(img_bytes: bytes, camara_id: str) -> None:
    """
    Analiza una imagen con YOLOv8 ONNX + Tesseract + OpenCV.
    Si detecta algo relevante → guarda en Supabase y envía alerta.
    """
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            print("⚠️  No se pudo decodificar la imagen")
            return

        tipo            = None
        valor           = ""
        conocido        = False
        nombre_conocido = ""

        # ── Inferencia YOLO ONNX (si disponible) ──
        if yolo_session is not None:
            detecciones = _inferir_yolo(frame)
            for det in detecciones:
                cls, (x1, y1, x2, y2) = det["cls"], det["box"]

                if cls == CLASE_PERSONA:
                    tipo = "persona"

                elif cls in CLASES_VEHICULO:
                    tipo = "vehiculo"
                    roi = frame[y1:y2, x1:x2]
                    placa_detectada = _leer_placa_ocr(roi)
                    if placa_detectada:
                        valor = placa_detectada
                        nombre = _buscar_placa_registrada(valor)
                        if nombre:
                            conocido        = True
                            nombre_conocido = nombre
                        print(f"🔖 Placa OCR: '{valor}' | Conocido: {nombre_conocido or 'no'}")

        # ── Fallback: HOG people detector (si YOLO no está disponible) ──
        elif _hog_detector is not None:
            h_frame = cv2.resize(frame, (640, 480)) if frame.shape[1] > 640 else frame
            rects, _ = _hog_detector.detectMultiScale(
                h_frame, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            if len(rects) > 0:
                tipo = "persona"
                print(f"🚶 HOG: {len(rects)} persona(s) detectada(s) — cámara {camara_id}")

        # ── Detección de rostros con OpenCV ──
        rostros_count, coords_rostros = _detectar_rostros(frame)
        nombres_reconocidos = []

        if rostros_count > 0:
            tipo = "persona"
            for (rx, ry, rw, rh) in coords_rostros:
                # Recorte del rostro para reconocimiento
                recorte = frame[ry:ry + rh, rx:rx + rw]
                if recorte.size > 0:
                    res_hf = _reconocer_rostro_hf(recorte, camara_id)
                    if res_hf.get("conocido"):
                        nombres_reconocidos.append(res_hf["nombre"])
                        conocido        = True
                        nombre_conocido = res_hf["nombre"]
                        color_rect = (0, 200, 0)    # verde — conocido
                        etiqueta   = nombre_conocido
                    else:
                        color_rect = (0, 0, 255)    # rojo — desconocido
                        etiqueta   = "Desconocido"

                    cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), color_rect, 2)
                    cv2.putText(
                        frame, etiqueta, (rx, ry - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_rect, 2,
                    )
                else:
                    cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)

            label_log = ", ".join(nombres_reconocidos) if nombres_reconocidos else "desconocidos"
            print(f"👤 {rostros_count} rostro(s) ({label_log}) — cámara {camara_id}")

        # ── Ignorar si no hay nada relevante ──
        if tipo is None:
            print(f"ℹ️  Cámara {camara_id}: sin detección relevante, foto ignorada")
            return

        # ── Codificar imagen procesada ──
        success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            print("❌ Error al codificar imagen procesada")
            return
        foto_bytes_out = buffer.tobytes()

        # ── Subir a Supabase Storage ──
        nombre_archivo = f"{camara_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jpg"
        foto_url = ""

        if supabase_client:
            try:
                supabase_client.storage.from_("eventos").upload(
                    nombre_archivo,
                    foto_bytes_out,
                    file_options={"content-type": "image/jpeg"},
                )
                foto_url = f"{SUPABASE_URL}/storage/v1/object/public/eventos/{nombre_archivo}"
                print(f"📤 Foto subida: {nombre_archivo}")
            except Exception as e:
                print(f"❌ Error subiendo foto a Supabase Storage: {e}")

            # ── Insertar evento en Supabase ──
            try:
                supabase_client.table("eventos").insert({
                    "tipo":           tipo,
                    "valor":          valor,
                    "camara":         camara_id,
                    "foto_url":       foto_url,
                    "conocido":       conocido,
                    "rostros":        rostros_count,
                    "nombre_persona": nombre_conocido or None,
                    # created_at lo genera Supabase automáticamente (default now())
                }).execute()
                print(
                    f"✅ Evento guardado | tipo={tipo} | placa='{valor}' "
                    f"| rostros={rostros_count} | conocido={conocido} "
                    f"| persona='{nombre_conocido}' | cámara={camara_id}"
                )
            except Exception as e:
                print(f"❌ Error insertando evento en Supabase: {e}")
        else:
            print("⚠️  Supabase no disponible — evento no guardado")

        # ── Enviar alerta por email ──
        enviar_alerta(foto_bytes_out, tipo, valor, camara_id, rostros_count, conocido, nombre_conocido)

    except Exception as e:
        print(f"❌ Error inesperado procesando foto (cámara {camara_id}): {e}")


# ─────────────────────────────────────────────
#  Envío de alerta por email
# ─────────────────────────────────────────────

def enviar_alerta(
    foto_bytes: bytes,
    tipo: str,
    valor: str,
    camara_id: str,
    rostros_count: int = 0,
    conocido: bool = False,
    nombre: str = "",
) -> None:
    """Envía email de alerta con foto procesada adjunta."""
    if not GMAIL_USER or not GMAIL_PASS or not EMAIL_ALERTA:
        print("⚠️  Credenciales de Gmail no configuradas — alerta no enviada")
        return

    try:
        msg             = MIMEMultipart()
        msg["From"]     = GMAIL_USER
        msg["To"]       = EMAIL_ALERTA
        msg["Subject"]  = f"🚨 ALERTA: {tipo.upper()} detectado — Cámara {camara_id}"

        hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lineas = [
            f"Tipo de detección : {tipo.capitalize()}",
            f"Cámara            : {camara_id}",
            f"Hora              : {hora_local}",
        ]
        if rostros_count > 0:
            lineas.append(f"Rostros detectados: {rostros_count}")
        if valor:
            lineas.append(f"Placa detectada   : {valor}")
        if conocido:
            lineas.append(f"Vehículo conocido : ✅ {nombre}")

        msg.attach(MIMEText("\n".join(lineas), "plain"))

        img_adjunta = MIMEImage(foto_bytes, _subtype="jpeg")
        img_adjunta.add_header(
            "Content-Disposition", "attachment",
            filename=f"alerta_cam{camara_id}_{datetime.now().strftime('%H%M%S')}.jpg",
        )
        msg.attach(img_adjunta)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, EMAIL_ALERTA, msg.as_string())

        print(f"📧 Alerta enviada a {EMAIL_ALERTA}")
    except smtplib.SMTPAuthenticationError:
        print("❌ Error de autenticación Gmail — verifica GMAIL_USER y GMAIL_PASS (usa contraseña de aplicación)")
    except Exception as e:
        print(f"❌ Error enviando alerta: {e}")


# ─────────────────────────────────────────────
#  Lector de emails (corre en hilo daemon)
# ─────────────────────────────────────────────

def _detectar_camara_desde_asunto(asunto: str) -> str:
    """Extrae número de cámara del asunto. Ej: 'Camara3' → '03'."""
    # Decodificar RFC 2047 si el asunto viene codificado (=?utf-8?B?...?=)
    asunto_dec = _decodificar_filename(asunto)
    asunto_lower = asunto_dec.lower()
    for i in range(1, 9):
        if f"camara{i}" in asunto_lower or f"cámara{i}" in asunto_lower or f"camera{i}" in asunto_lower:
            return str(i).zfill(2)
    return "01"  # Default cámara 01


def _detectar_camara_desde_filename(filename: str) -> str | None:
    """Extrae número de cámara del nombre del archivo adjunto. Ej: 'Cámara3.jpg' → '03'."""
    fname_lower = filename.lower()
    for i in range(1, 9):
        if f"camara{i}" in fname_lower or f"cámara{i}" in fname_lower or f"camera{i}" in fname_lower:
            return str(i).zfill(2)
    return None


def _procesar_mensaje_email(mail: imaplib.IMAP4_SSL, num: bytes) -> None:
    """Extrae imágenes de un email y lanza hilos de procesamiento."""
    try:
        _, msg_data = mail.fetch(num, "(RFC822)")
        if not msg_data or not msg_data[0]:
            return

        msg    = email.message_from_bytes(msg_data[0][1])
        asunto = msg.get("Subject", "")

        # Ignorar emails de alerta que generamos nosotros
        if "ALERTA:" in asunto:
            mail.store(num, "+FLAGS", "\\Seen")
            print(f"⏭️  Email de alerta propio ignorado: '{asunto}'")
            return

        # Ignorar emails más antiguos de 2 horas
        fecha_header = msg.get("Date")
        if fecha_header:
            try:
                fecha_dt = parsedate_to_datetime(fecha_header)
                # Asegurar que sea timezone-aware para comparar
                if fecha_dt.tzinfo is None:
                    fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
                antiguedad = datetime.now(timezone.utc) - fecha_dt
                if antiguedad > timedelta(hours=2):
                    mail.store(num, "+FLAGS", "\\Seen")
                    print(f"⏭️  Email antiguo ignorado ({antiguedad} de antigüedad): '{asunto}'")
                    return
            except Exception as e:
                print(f"⚠️  No se pudo parsear fecha del email: {e}")

        asunto_dec = _decodificar_filename(asunto)
        camara_id      = _detectar_camara_desde_asunto(asunto)
        print(f"📧 Email: '{asunto_dec}' → cámara {camara_id}")
        fotos_halladas = 0

        # Debug: mostrar todas las partes del email para diagnosticar formato del DVR
        for i, p in enumerate(msg.walk()):
            if p.get_content_maintype() != "multipart":
                fn  = p.get_filename() or ""
                ct  = p.get_content_type()
                cd  = p.get("Content-Disposition", "—")
                print(f"  [parte {i}] ct={ct} | fn='{fn}' | cd={cd[:60]}")

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = _decodificar_filename(part.get_filename() or "")
            # Si no hay filename en Content-Disposition buscar en Content-Type
            if not filename:
                ct = part.get("Content-Type", "")
                m = re.search(r'name=["\']?([^";]+)', ct)
                if m:
                    filename = _decodificar_filename(m.group(1).strip())
            fname_lower = filename.lower()

            # ── Imagen directa ──────────────────────────────────────
            if any(fname_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                img_bytes = part.get_payload(decode=True)
                if not img_bytes:
                    print(f"⚠️  Adjunto vacío: {filename}")
                    continue

                # Intentar precisar la cámara desde el nombre del archivo
                cam = _detectar_camara_desde_filename(filename) or camara_id

                fotos_halladas += 1
                print(f"📸 Imagen recibida: '{filename}' — Cámara {cam} ({len(img_bytes) // 1024} KB)")

                hilo = threading.Thread(
                    target=procesar_foto,
                    args=(img_bytes, cam),
                    daemon=True,
                    name=f"proc-cam{cam}",
                )
                hilo.start()

            # ── Video (.mov / .mp4 / .avi) → extraer frame ──────────
            elif any(fname_lower.endswith(ext) for ext in [".mov", ".mp4", ".avi", ".mkv"]):
                video_bytes = part.get_payload(decode=True)
                if not video_bytes:
                    print(f"⚠️  Adjunto de video vacío: {filename}")
                    continue

                cam = _detectar_camara_desde_filename(filename) or camara_id
                print(f"🎥 Video recibido: '{filename}' — Cámara {cam} ({len(video_bytes) // 1024} KB) — extrayendo frame…")

                # Escribir a archivo temporal y leer con OpenCV
                import tempfile, os as _os
                with tempfile.NamedTemporaryFile(suffix=fname_lower[-4:], delete=False) as tmp:
                    tmp.write(video_bytes)
                    tmp_path = tmp.name

                try:
                    cap = cv2.VideoCapture(tmp_path)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    # Ir al 20% del video para evitar pantalla negra inicial
                    target_frame = max(0, int(total_frames * 0.20))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    ret, frame_cv = cap.read()
                    cap.release()

                    if ret and frame_cv is not None:
                        success, buf = cv2.imencode(".jpg", frame_cv, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if success:
                            img_bytes = buf.tobytes()
                            fotos_halladas += 1
                            hilo = threading.Thread(
                                target=procesar_foto,
                                args=(img_bytes, cam),
                                daemon=True,
                                name=f"proc-cam{cam}",
                            )
                            hilo.start()
                        else:
                            print(f"❌ No se pudo codificar frame del video: {filename}")
                    else:
                        print(f"❌ No se pudo leer frame del video: {filename}")
                except Exception as ve:
                    print(f"❌ Error procesando video '{filename}': {ve}")
                finally:
                    _os.unlink(tmp_path)

        if fotos_halladas == 0:
            print(f"ℹ️  Email sin adjuntos de imagen/video procesables: '{asunto}'")

        # Marcar como leído independientemente
        mail.store(num, "+FLAGS", "\\Seen")

    except Exception as e:
        print(f"❌ Error procesando mensaje de email: {e}")
        try:
            mail.store(num, "+FLAGS", "\\Seen")
        except Exception:
            pass


def _bucle_leer_emails() -> None:
    """Bucle infinito que lee emails no leídos cada 30 segundos."""
    intentos_fallidos = 0

    while True:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
            mail.login(GMAIL_USER, GMAIL_PASS)
            mail.select("inbox")

            _, messages = mail.search(None, "UNSEEN")
            ids_no_leidos = messages[0].split() if messages[0] else []

            if ids_no_leidos:
                print(f"📬 {len(ids_no_leidos)} email(s) no leído(s) encontrado(s)")
                for num in ids_no_leidos:
                    _procesar_mensaje_email(mail, num)
            else:
                print("📭 Sin emails nuevos")

            mail.close()
            mail.logout()
            intentos_fallidos = 0  # Reset contador en éxito

        except imaplib.IMAP4.abort as e:
            intentos_fallidos += 1
            print(f"❌ Conexión IMAP abortada (intento {intentos_fallidos}): {e}")
        except imaplib.IMAP4.error as e:
            intentos_fallidos += 1
            print(f"❌ Error IMAP (intento {intentos_fallidos}): {e}")
        except OSError as e:
            intentos_fallidos += 1
            print(f"❌ Error de red (intento {intentos_fallidos}): {e}")
        except Exception as e:
            intentos_fallidos += 1
            print(f"❌ Error inesperado en lector de email (intento {intentos_fallidos}): {e}")

        # Backoff exponencial en errores consecutivos (máx 5 min)
        if intentos_fallidos > 0:
            espera = min(30 * (2 ** (intentos_fallidos - 1)), 300)
            print(f"⏳ Reintentando en {espera} segundos...")
            time.sleep(espera)
        else:
            time.sleep(30)


# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────

@app.get("/", tags=["Estado"])
def status():
    """Verifica que el servicio esté activo y qué modelos están cargados."""
    def _tesseract_ok() -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    return {
        "status":    "activo",
        "servicio":  "Sistema de Seguridad Vecinal",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modelos": {
            "yolo_onnx":  yolo_session is not None,
            "tesseract":  _tesseract_ok(),
            "opencv":     face_cascade is not None,
            "supabase":   supabase_client is not None,
        },
    }


@app.get("/eventos", tags=["Datos"])
def get_eventos(limite: int = 50):
    """Devuelve los últimos N eventos registrados."""
    if not supabase_client:
        return {"error": "Supabase no configurado", "data": []}
    try:
        data = (
            supabase_client.table("eventos")
            .select("*")
            .order("created_at", desc=True)
            .limit(min(limite, 200))
            .execute()
        )
        return {"total": len(data.data), "data": data.data}
    except Exception as e:
        return {"error": str(e), "data": []}


@app.get("/eventos/hoy", tags=["Datos"])
def get_eventos_hoy():
    """Devuelve eventos del día actual."""
    if not supabase_client:
        return {"error": "Supabase no configurado", "data": []}
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        data = (
            supabase_client.table("eventos")
            .select("*")
            .gte("created_at", f"{hoy}T00:00:00+00:00")
            .order("created_at", desc=True)
            .execute()
        )
        return {"fecha": hoy, "total": len(data.data), "data": data.data}
    except Exception as e:
        return {"error": str(e), "data": []}


@app.get("/placas", tags=["Datos"])
def get_placas():
    """Devuelve detecciones con placa identificada."""
    if not supabase_client:
        return {"error": "Supabase no configurado", "data": []}
    try:
        data = (
            supabase_client.table("eventos")
            .select("*")
            .not_.is_("valor", "null")
            .neq("valor", "")
            .order("created_at", desc=True)
            .execute()
        )
        return {"total": len(data.data), "data": data.data}
    except Exception as e:
        return {"error": str(e), "data": []}
