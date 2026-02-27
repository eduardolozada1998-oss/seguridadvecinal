"""
Sistema de Seguridad Vecinal — Backend Completo
HuggingFace Space (Docker) — CPU tier, 16 GB RAM

Stack:
  * YOLOv8n ONNX   — deteccion personas/vehiculos
  * Tesseract OCR   — lectura de placas
  * OpenCV Haar     — deteccion de rostros
  * DeepFace Facenet— reconocimiento facial
  * Supabase        — base de datos + storage
  * FastAPI         — API REST + polling de emails IMAP

Endpoints de la API:
  GET  /                 -> health check
  POST /reconocer        -> reconocimiento facial (imagen base64)
  POST /registrar        -> registrar persona conocida
  GET  /personas         -> listar personas registradas
  DELETE /personas/{id}  -> desactivar persona
"""

import os, re, json, base64, shutil, time, math
import threading, imaplib, email, email.header
import smtplib, tempfile, traceback
import urllib.request, urllib.error
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Optional

import cv2
import numpy as np
import pytesseract
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client

# DeepFace (lazy import)
_deepface_ok = False
try:
    from deepface import DeepFace
    _deepface_ok = True
    print("DeepFace importado OK")
except Exception as _e:
    print(f"DeepFace no disponible: {_e}")

# ---------------------------------------------------------------------------
# Variables de entorno
# ---------------------------------------------------------------------------
SUPABASE_URL  = os.environ.get("SUPABASE_URL",  "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY",  "")
GMAIL_USER    = os.environ.get("GMAIL_USER",    "")
GMAIL_PASS    = os.environ.get("GMAIL_PASS",    "")
EMAIL_ALERTA  = os.environ.get("EMAIL_ALERTA",  GMAIL_USER)
IMAP_SERVER   = os.environ.get("IMAP_SERVER",   "imap.gmail.com")
UMBRAL_FACE   = float(os.environ.get("FACE_THRESHOLD", "0.72"))

TESSERACT_CMD = (
    os.environ.get("TESSERACT_CMD", "")
    or shutil.which("tesseract")
    or "/usr/bin/tesseract"
)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ---------------------------------------------------------------------------
# Constantes YOLO
# ---------------------------------------------------------------------------
CLASE_PERSONA   = 0
CLASES_VEHICULO = {2, 3, 5, 7}
YOLO_INPUT_SIZE = 640
CONF_THRESHOLD  = 0.5
IOU_THRESHOLD   = 0.45

YOLO_PATHS = ["/app/yolov8n.onnx", "yolov8n.onnx"]
YOLO_URLS  = [
    "https://huggingface.co/amikelive/yolov8n-onnx/resolve/main/yolov8n.onnx",
    "https://github.com/niconielsen32/YOLOv8ONNX/releases/download/v1.0/yolov8n.onnx",
]
URL_HAARCASCADE = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "data/haarcascades/haarcascade_frontalface_default.xml"
)

# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------
supabase_client = None
yolo_session    = None
yolo_input_name = None
face_cascade    = None
_hog_detector   = None
_modelo_lock    = threading.Lock()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    global supabase_client, yolo_session, yolo_input_name, face_cascade, _hog_detector

    print("Iniciando Sistema de Seguridad Vecinal (HF Space)...")

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("Supabase conectado OK")
        except Exception as e:
            print(f"Supabase error: {e}")

    yolo_path = _hallar_yolo()
    if yolo_path:
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 2
            yolo_session    = ort.InferenceSession(yolo_path, sess_options=opts)
            yolo_input_name = yolo_session.get_inputs()[0].name
            print(f"YOLOv8n ONNX cargado: {yolo_path}")
        except Exception as e:
            print(f"YOLO error: {e}")

    hc_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(hc_path):
        _descargar(URL_HAARCASCADE, hc_path, "Haarcascade")
    cascade = cv2.CascadeClassifier(hc_path)
    face_cascade = cascade if not cascade.empty() else None
    print("Face cascade OK" if face_cascade else "Face cascade ERROR")

    _hog_detector = cv2.HOGDescriptor()
    _hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    print("HOG detector OK")

    tess_ok = bool(shutil.which("tesseract") or os.path.exists(TESSERACT_CMD or ""))
    print(f"Tesseract: {'OK' if tess_ok else 'NO ENCONTRADO'} -> {TESSERACT_CMD}")
    print(f"DeepFace: {'OK' if _deepface_ok else 'no disponible'}")

    if GMAIL_USER and GMAIL_PASS:
        t = threading.Thread(target=_bucle_leer_emails, daemon=True, name="imap")
        t.start()
        print("Lector IMAP iniciado")
    else:
        print("GMAIL no configurado — polling desactivado")

    print("Sistema listo")
    yield
    print("Sistema detenido")


app = FastAPI(title="Seguridad Vecinal", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------
class PeticionReconocer(BaseModel):
    imagen_b64: str
    camara_id:  Optional[str] = "00"

class PeticionRegistrar(BaseModel):
    imagen_b64:  str
    nombre:      str
    descripcion: Optional[str] = ""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _descargar(url: str, destino: str, nombre: str) -> bool:
    print(f"Descargando {nombre} desde {url} ...")
    try:
        urllib.request.urlretrieve(url, destino)
        print(f"{nombre} descargado ({os.path.getsize(destino)//1024} KB)")
        return True
    except Exception as e:
        print(f"Fallo {url}: {e}")
        return False


def _hallar_yolo() -> "str | None":
    for p in YOLO_PATHS:
        if os.path.exists(p):
            print(f"YOLO encontrado en {p}")
            return p
    for url in YOLO_URLS:
        if _descargar(url, "yolov8n.onnx", "YOLOv8n ONNX"):
            return "yolov8n.onnx"
    return None


def _decodificar_filename(raw: str) -> str:
    if not raw:
        return ""
    try:
        partes = email.header.decode_header(raw)
        res = []
        for frag, enc in partes:
            if isinstance(frag, bytes):
                res.append(frag.decode(enc or "utf-8", errors="replace"))
            else:
                res.append(str(frag))
        return "".join(res).strip()
    except Exception:
        return raw.strip()


# ---------------------------------------------------------------------------
# Deteccion de camara — REGEX robusto
# Matches: Camara2, Cámara2, camara 2, camara_2, Camera2, etc.
# ---------------------------------------------------------------------------
_RE_CAM = re.compile(
    r'c(?:a|\xe1|%C3%A1)mara\s*[_\-]?\s*0?(\d)', re.IGNORECASE
)
_RE_CAM2 = re.compile(r'camera\s*[_\-]?\s*0?(\d)', re.IGNORECASE)


def _extraer_num_cam(texto: str) -> "str | None":
    if not texto:
        return None
    # Normalizar: reemplazar a con a para matches sin acento también
    normalizado = texto.lower().replace("\xe1", "a")
    m = re.search(r'c(?:a|\xe1)mara\s*[_\-]?\s*0?(\d)', texto.lower()) \
        or re.search(r'camara\s*[_\-]?\s*0?(\d)', normalizado) \
        or re.search(r'camera\s*[_\-]?\s*0?(\d)', normalizado)
    return m.group(1).zfill(2) if m else None


def _detectar_camara_desde_asunto(asunto: str) -> str:
    return _extraer_num_cam(_decodificar_filename(asunto)) or "01"


def _detectar_camara_desde_filename(filename: str) -> "str | None":
    return _extraer_num_cam(filename)


# ---------------------------------------------------------------------------
# YOLO
# ---------------------------------------------------------------------------
def _pre_procesar(frame: np.ndarray):
    h, w   = frame.shape[:2]
    scale  = YOLO_INPUT_SIZE / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    canvas = np.zeros((YOLO_INPUT_SIZE, YOLO_INPUT_SIZE, 3), dtype=np.uint8)
    canvas[:nh, :nw] = cv2.resize(frame, (nw, nh))
    blob = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.expand_dims(blob, 0), scale, w, h


def _inferir_yolo(frame: np.ndarray) -> list:
    if yolo_session is None:
        return []
    blob, scale, orig_w, orig_h = _pre_procesar(frame)
    with _modelo_lock:
        outs = yolo_session.run(None, {yolo_input_name: blob})
    preds = outs[0][0].T
    boxes, scores, classes = [], [], []
    for row in preds:
        confs = row[4:]
        cls   = int(np.argmax(confs))
        conf  = float(confs[cls])
        if conf < CONF_THRESHOLD or cls not in ([CLASE_PERSONA] + list(CLASES_VEHICULO)):
            continue
        cx, cy, bw, bh = row[:4]
        x1 = max(0, int((cx - bw / 2) / scale))
        y1 = max(0, int((cy - bh / 2) / scale))
        x2 = min(orig_w - 1, int((cx + bw / 2) / scale))
        y2 = min(orig_h - 1, int((cy + bh / 2) / scale))
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        scores.append(conf)
        classes.append(cls)
    idx = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
    keep = idx.flatten().tolist() if len(idx) > 0 else []
    return [{"cls": classes[i], "box": (boxes[i][0], boxes[i][1],
             boxes[i][0]+boxes[i][2], boxes[i][1]+boxes[i][3]),
             "conf": scores[i]} for i in keep]


# ---------------------------------------------------------------------------
# OCR placas
# ---------------------------------------------------------------------------
def _leer_placa_ocr(roi: np.ndarray) -> str:
    try:
        gris  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw    = cv2.resize(bw, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        texto = pytesseract.image_to_string(
            bw,
            config="--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        ).strip()
        limpio = re.sub(r"[^A-Z0-9]", "", texto.upper())
        return limpio if 5 <= len(limpio) <= 8 else ""
    except Exception:
        return ""


def _buscar_placa_registrada(placa: str) -> "str | None":
    if not supabase_client or not placa:
        return None
    try:
        rows = supabase_client.table("placas_registradas").select("placa,nombre").eq("activo", True).execute().data
        for r in rows:
            if r["placa"].replace(" ", "").upper() == placa.replace(" ", "").upper():
                return r["nombre"]
    except Exception as e:
        print(f"placas_registradas error: {e}")
    return None


# ---------------------------------------------------------------------------
# Deteccion de rostros
# ---------------------------------------------------------------------------
def _detectar_rostros(frame: np.ndarray):
    if face_cascade is None:
        return 0, []
    gris   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    coords = face_cascade.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return (len(coords), list(coords)) if len(coords) > 0 else (0, [])


# ---------------------------------------------------------------------------
# Reconocimiento facial (DeepFace)
# ---------------------------------------------------------------------------
def _extraer_embedding(frame: np.ndarray) -> list:
    if not _deepface_ok:
        raise RuntimeError("DeepFace no disponible")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = DeepFace.represent(img_path=rgb, model_name="Facenet",
                             enforce_detection=True, detector_backend="opencv")
    if not res:
        raise ValueError("Sin rostro")
    return res[0]["embedding"]


def _similitud_coseno(v1, v2) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1  = math.sqrt(sum(a * a for a in v1))
    n2  = math.sqrt(sum(b * b for b in v2))
    return dot / (n1 * n2) if n1 and n2 else 0.0


def _obtener_personas() -> list:
    if not supabase_client:
        return []
    try:
        rows = (supabase_client.table("personas_conocidas")
                .select("id,nombre,descripcion,embedding")
                .eq("activo", True).execute().data)
        result = []
        for r in rows:
            emb = r.get("embedding")
            if isinstance(emb, str):
                emb = json.loads(emb)
            if emb:
                result.append({**r, "embedding": emb})
        return result
    except Exception as e:
        print(f"personas_conocidas error: {e}")
        return []


def _reconocer_rostro_local(face_frame: np.ndarray) -> dict:
    if not _deepface_ok:
        return {"conocido": False, "nombre": "desconocido", "confianza": 0.0}
    try:
        emb_q = _extraer_embedding(face_frame)
    except Exception as e:
        print(f"Embedding error: {e}")
        return {"conocido": False, "nombre": "desconocido", "confianza": 0.0}

    personas = _obtener_personas()
    mejor_sim, mejor_nombre, mejor_id = 0.0, "desconocido", None
    for p in personas:
        sim = _similitud_coseno(emb_q, p["embedding"])
        if sim > mejor_sim:
            mejor_sim, mejor_nombre, mejor_id = sim, p["nombre"], p["id"]

    conocido = mejor_sim >= UMBRAL_FACE
    print(f"Reconocimiento: {mejor_nombre} sim={mejor_sim:.3f} conocido={conocido}")
    return {
        "conocido":   conocido,
        "nombre":     mejor_nombre if conocido else "desconocido",
        "confianza":  round(mejor_sim, 4),
        "persona_id": mejor_id if conocido else None,
    }


# ---------------------------------------------------------------------------
# Procesamiento de foto
# ---------------------------------------------------------------------------
def procesar_foto(img_bytes: bytes, camara_id: str) -> None:
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            print("Imagen no decodificable")
            return

        tipo = None; valor = ""; conocido = False; nombre_conocido = ""

        # YOLO
        if yolo_session is not None:
            for det in _inferir_yolo(frame):
                cls, (x1, y1, x2, y2) = det["cls"], det["box"]
                if cls == CLASE_PERSONA:
                    tipo = "persona"
                elif cls in CLASES_VEHICULO:
                    tipo  = "vehiculo"
                    placa = _leer_placa_ocr(frame[y1:y2, x1:x2])
                    if placa:
                        valor  = placa
                        nombre = _buscar_placa_registrada(valor)
                        if nombre:
                            conocido = True; nombre_conocido = nombre
                        print(f"Placa: '{valor}' | {nombre_conocido or 'desconocida'}")
        elif _hog_detector is not None:
            h_frame = cv2.resize(frame, (640, 480)) if frame.shape[1] > 640 else frame
            rects, _ = _hog_detector.detectMultiScale(h_frame, winStride=(8,8), padding=(4,4), scale=1.05)
            if len(rects) > 0:
                tipo = "persona"
                print(f"HOG: {len(rects)} persona(s) — cam {camara_id}")

        # Rostros + reconocimiento
        rostros_count, coords_rostros = _detectar_rostros(frame)
        if rostros_count > 0:
            tipo = "persona"
            for (rx, ry, rw, rh) in coords_rostros:
                recorte = frame[ry:ry+rh, rx:rx+rw]
                if recorte.size > 0:
                    res = _reconocer_rostro_local(recorte)
                    if res["conocido"]:
                        conocido = True; nombre_conocido = res["nombre"]
                        color, etiqueta = (0, 200, 0), nombre_conocido
                    else:
                        color, etiqueta = (0, 0, 255), "Desconocido"
                    cv2.rectangle(frame, (rx, ry), (rx+rw, ry+rh), color, 2)
                    cv2.putText(frame, etiqueta, (rx, ry-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            print(f"Rostros: {rostros_count} — cam {camara_id}")

        if tipo is None:
            print(f"Cam {camara_id}: sin deteccion relevante")
            return

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return
        foto_out = buf.tobytes()

        ts          = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        nombre_arch = f"{camara_id}_{ts}.jpg"
        foto_url    = ""

        if supabase_client:
            try:
                supabase_client.storage.from_("eventos").upload(
                    nombre_arch, foto_out, file_options={"content-type": "image/jpeg"})
                foto_url = f"{SUPABASE_URL}/storage/v1/object/public/eventos/{nombre_arch}"
                print(f"Foto subida: {nombre_arch}")
            except Exception as e:
                print(f"Storage error: {e}")
            try:
                supabase_client.table("eventos").insert({
                    "tipo": tipo, "valor": valor, "camara": camara_id,
                    "foto_url": foto_url, "conocido": conocido,
                    "rostros": rostros_count, "nombre_persona": nombre_conocido or None,
                }).execute()
                print(f"Evento guardado cam={camara_id} tipo={tipo} persona='{nombre_conocido}'")
            except Exception as e:
                print(f"Insert evento error: {e}")

        _enviar_alerta(foto_out, tipo, valor, camara_id, rostros_count, conocido, nombre_conocido)

    except Exception as e:
        print(f"procesar_foto error cam={camara_id}: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Alerta email
# ---------------------------------------------------------------------------
def _enviar_alerta(foto, tipo, valor, camara, rostros, conocido, nombre):
    if not GMAIL_USER or not GMAIL_PASS or not EMAIL_ALERTA:
        return
    try:
        subj_parts = [f"ALERTA: {tipo.upper()} — Cam {camara}"]
        if valor:
            subj_parts.append(f"| {valor}")
        if nombre:
            subj_parts.append(f"| {nombre}")
        msg         = MIMEMultipart()
        msg["Subject"] = " ".join(subj_parts)
        msg["From"]    = GMAIL_USER
        msg["To"]      = EMAIL_ALERTA
        msg.attach(MIMEText(
            f"Camara: {camara}\nTipo: {tipo}\nPlaca: {valor}\n"
            f"Rostros: {rostros}\nConocido: {conocido}\nNombre: {nombre or '-'}", "plain"))
        img_part = MIMEImage(foto, _subtype="jpeg")
        img_part.add_header("Content-Disposition", "attachment", filename="alerta.jpg")
        msg.attach(img_part)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, EMAIL_ALERTA, msg.as_string())
        print(f"Alerta enviada a {EMAIL_ALERTA}")
    except Exception as e:
        print(f"Alerta email error: {e}")


# ---------------------------------------------------------------------------
# Procesamiento de email individual
# ---------------------------------------------------------------------------
def _procesar_email(mail: imaplib.IMAP4_SSL, num: bytes) -> None:
    try:
        _, msg_data = mail.fetch(num, "(RFC822)")
        if not msg_data or not msg_data[0]:
            return
        msg    = email.message_from_bytes(msg_data[0][1])
        asunto = msg.get("Subject", "")

        if "ALERTA:" in asunto:
            mail.store(num, "+FLAGS", "\\Seen")
            return

        fecha_h = msg.get("Date")
        if fecha_h:
            try:
                dt = parsedate_to_datetime(fecha_h)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - dt > timedelta(hours=2):
                    mail.store(num, "+FLAGS", "\\Seen")
                    print("Email antiguo ignorado")
                    return
            except Exception:
                pass

        camara_id = _detectar_camara_desde_asunto(asunto)
        print(f"Email: '{_decodificar_filename(asunto)}' -> cam base={camara_id}")

        fotos = 0
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = _decodificar_filename(part.get_filename() or "")
            if not filename:
                ct = part.get("Content-Type", "")
                m  = re.search(r'name=["\']?([^";]+)', ct)
                if m:
                    filename = _decodificar_filename(m.group(1).strip())
            fname_lower = filename.lower()
            cam = _detectar_camara_desde_filename(filename) or camara_id

            if any(fname_lower.endswith(e) for e in [".jpg", ".jpeg", ".png"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                fotos += 1
                print(f"Imagen '{filename}' -> cam {cam} ({len(data)//1024} KB)")
                threading.Thread(target=procesar_foto, args=(data, cam),
                                 daemon=True, name=f"proc-{cam}").start()

            elif any(fname_lower.endswith(e) for e in [".mov", ".mp4", ".avi", ".mkv"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                print(f"Video '{filename}' -> cam {cam} ({len(data)//1024} KB)")
                ext = fname_lower[-4:]
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(data); tmp_path = tmp.name
                try:
                    cap   = cv2.VideoCapture(tmp_path)
                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(total * 0.20)))
                    ret, fr = cap.read()
                    cap.release()
                    if ret and fr is not None:
                        ok, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ok:
                            fotos += 1
                            threading.Thread(target=procesar_foto, args=(buf.tobytes(), cam),
                                             daemon=True, name=f"proc-{cam}").start()
                except Exception as e:
                    print(f"Video error: {e}")
                finally:
                    try: os.unlink(tmp_path)
                    except Exception: pass

        mail.store(num, "+FLAGS", "\\Seen")
        if fotos == 0:
            print("Sin adjuntos imagen/video")
    except Exception as e:
        print(f"_procesar_email error: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Bucle IMAP (hilo daemon)
# ---------------------------------------------------------------------------
def _bucle_leer_emails() -> None:
    backoff = 30
    while True:
        try:
            with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
                mail.login(GMAIL_USER, GMAIL_PASS)
                backoff = 30
                while True:
                    mail.select("INBOX")
                    _, nums = mail.search(None, "UNSEEN")
                    ids = nums[0].split() if nums[0] else []
                    if ids:
                        print(f"{len(ids)} email(s) nuevo(s)")
                        for num in ids:
                            _procesar_email(mail, num)
                    else:
                        print("Sin emails nuevos")
                    time.sleep(30)
        except Exception as e:
            print(f"IMAP error: {e} — reintento en {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def raiz():
    return {
        "status":    "Sistema de seguridad vecinal activo",
        "yolo":      yolo_session is not None,
        "deepface":  _deepface_ok,
        "supabase":  supabase_client is not None,
        "tesseract": bool(shutil.which("tesseract")),
    }


@app.post("/reconocer")
def reconocer_rostro(datos: PeticionReconocer):
    if not _deepface_ok:
        raise HTTPException(503, "DeepFace no disponible")
    try:
        b64 = datos.imagen_b64
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        raw   = base64.b64decode(b64)
        nparr = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(400, "Imagen invalida")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "base64 invalido")
    return _reconocer_rostro_local(frame)


@app.post("/registrar")
def registrar_persona(datos: PeticionRegistrar):
    if not _deepface_ok:
        raise HTTPException(503, "DeepFace no disponible")
    if not supabase_client:
        raise HTTPException(503, "Supabase no disponible")
    if not datos.nombre.strip():
        raise HTTPException(400, "Nombre vacio")
    try:
        b64 = datos.imagen_b64
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        frame = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise HTTPException(400, "Imagen invalida")
    try:
        emb = _extraer_embedding(frame)
    except Exception as e:
        raise HTTPException(422, f"Sin rostro: {e}")

    nombre   = datos.nombre.strip()
    emb_json = json.dumps(emb)
    try:
        existente = supabase_client.table("personas_conocidas").select("id").eq("nombre", nombre).execute().data
        if existente:
            pid = existente[0]["id"]
            supabase_client.table("personas_conocidas").update(
                {"embedding": emb_json, "descripcion": datos.descripcion or "", "activo": True}
            ).eq("id", pid).execute()
            accion = "actualizado"
        else:
            res    = supabase_client.table("personas_conocidas").insert(
                {"nombre": nombre, "descripcion": datos.descripcion or "",
                 "embedding": emb_json, "activo": True}).execute()
            pid    = res.data[0]["id"] if res.data else None
            accion = "registrado"
        print(f"Persona '{nombre}' {accion}")
        return {"ok": True, "nombre": nombre, "accion": accion, "persona_id": pid}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/personas")
def listar_personas():
    if not supabase_client:
        raise HTTPException(503, "Supabase no disponible")
    try:
        rows = supabase_client.table("personas_conocidas").select(
            "id,nombre,descripcion,activo,created_at").order("nombre").execute().data
        return {"personas": rows, "total": len(rows)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/personas/{persona_id}")
def eliminar_persona(persona_id: int):
    if not supabase_client:
        raise HTTPException(503, "Supabase no disponible")
    try:
        supabase_client.table("personas_conocidas").update(
            {"activo": False}).eq("id", persona_id).execute()
        return {"ok": True, "persona_id": persona_id}
    except Exception as e:
        raise HTTPException(500, str(e))
