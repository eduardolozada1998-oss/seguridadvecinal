from fastapi import FastAPI
from contextlib import asynccontextmanager
import threading
import os
import re
import tempfile
import traceback
import email
import email.header
import imaplib
import smtplib
import time
import numpy as np
import cv2
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# ---------------------------------------------------------------------------
# Variables de entorno
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GMAIL_USER   = os.environ.get("GMAIL_USER", "")
GMAIL_PASS   = os.environ.get("GMAIL_PASS", "")
EMAIL_ALERTA = os.environ.get("EMAIL_ALERTA", GMAIL_USER)

# ---------------------------------------------------------------------------
# Estado global (se inicializa en lifespan, no al importar)
# ---------------------------------------------------------------------------
supabase_client = None
model           = None
reader          = None
face_cascade    = None

# ---------------------------------------------------------------------------
# Lifespan — inicializacion segura
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase_client, model, reader, face_cascade

    print("Iniciando Sistema de Seguridad Vecinal...")

    # Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("Supabase OK")
        except Exception as e:
            print(f"Supabase ERROR: {e}")
    else:
        print("WARN: SUPABASE_URL/KEY no configurados")

    # YOLO — busca .pt primero, luego intenta descargar
    yolo_path = None
    for p in ["/app/yolov8n.pt", "yolov8n.pt"]:
        if os.path.exists(p):
            yolo_path = p
            break
    if yolo_path:
        try:
            from ultralytics import YOLO
            model = YOLO(yolo_path)
            print(f"YOLO cargado: {yolo_path}")
        except Exception as e:
            print(f"YOLO ERROR: {e}")
    else:
        print("WARN: yolov8n.pt no encontrado")

    # EasyOCR
    try:
        import easyocr
        reader = easyocr.Reader(['es', 'en'], gpu=False, verbose=False)
        print("EasyOCR OK")
    except Exception as e:
        print(f"EasyOCR ERROR: {e}")

    # OpenCV Haar cascade para rostros (ya incluido en opencv, 0 MB extra)
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cc = cv2.CascadeClassifier(cascade_path)
        face_cascade = cc if not cc.empty() else None
        print("Face cascade OK" if face_cascade else "Face cascade ERROR")
    except Exception as e:
        print(f"Face cascade ERROR: {e}")

    # Hilo IMAP
    if GMAIL_USER and GMAIL_PASS:
        t = threading.Thread(target=_bucle_emails, daemon=True, name="imap")
        t.start()
        print("Lector IMAP iniciado")
    else:
        print("WARN: GMAIL no configurado")

    print("Sistema listo")
    yield
    print("Sistema detenido")


app = FastAPI(title="Seguridad Vecinal", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Deteccion de camara — REGEX robusto con decode RFC2047
# ---------------------------------------------------------------------------
def _decodificar(raw: str) -> str:
    """Decodifica RFC2047. '=?utf-8?B?Q8OhbWFyYTIuanBn?=' -> 'Camara2.jpg'"""
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


def _numero_camara(texto: str) -> str:
    """Extrae numero de camara de cualquier texto. Devuelve '01'-'08'."""
    if not texto:
        return "01"
    # Normaliza: c con o sin acento, espacios, guiones
    norm = texto.lower().replace("\xe1", "a")  # a con acento -> a
    m = re.search(r'c(?:a|\xe1)mara\s*[_\-]?\s*0?(\d)', texto.lower()) \
        or re.search(r'camara\s*[_\-]?\s*0?(\d)', norm) \
        or re.search(r'camera\s*[_\-]?\s*0?(\d)', norm)
    return m.group(1).zfill(2) if m else "01"


# ---------------------------------------------------------------------------
# Deteccion de rostros (OpenCV — sin dependencias extra)
# ---------------------------------------------------------------------------
def _detectar_rostros(frame: np.ndarray):
    if face_cascade is None:
        return 0, []
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    coords = face_cascade.detectMultiScale(
        gris, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )
    return (len(coords), list(coords)) if len(coords) > 0 else (0, [])


# ---------------------------------------------------------------------------
# Procesamiento de foto
# ---------------------------------------------------------------------------
def procesar_foto(img_bytes: bytes, camara_id: str) -> None:
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        tipo  = None
        valor = ""

        # YOLO
        if model is not None:
            results = model(frame, classes=[0, 2, 3, 5, 7], verbose=False)
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if float(box.conf[0]) < 0.5:
                        continue
                    if cls == 0:
                        tipo = "persona"
                    elif cls in [2, 3, 5, 7]:
                        tipo = "vehiculo"
                        if reader is not None:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            roi    = frame[y1:y2, x1:x2]
                            textos = reader.readtext(roi, detail=0)
                            valor  = " ".join(textos).strip().upper()
                            print(f"Placa OCR: '{valor}'")

        # Rostros Haar cascade (fallback y complemento)
        n_rostros, coords_rostros = _detectar_rostros(frame)
        if n_rostros > 0:
            tipo = "persona"
            for (rx, ry, rw, rh) in coords_rostros:
                cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
            print(f"Rostros detectados: {n_rostros} — cam {camara_id}")

        if tipo is None:
            print(f"Cam {camara_id}: sin deteccion relevante")
            return

        # Codificar imagen anotada
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return
        foto_out = buf.tobytes()

        ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        nombre_arch = f"{camara_id}_{ts}.jpg"
        foto_url    = ""

        if supabase_client:
            try:
                supabase_client.storage.from_("eventos").upload(
                    nombre_arch, foto_out,
                    file_options={"content-type": "image/jpeg"}
                )
                foto_url = f"{SUPABASE_URL}/storage/v1/object/public/eventos/{nombre_arch}"
                print(f"Foto subida: {nombre_arch}")
            except Exception as e:
                print(f"Storage ERROR: {e}")
            try:
                supabase_client.table("eventos").insert({
                    "tipo":     tipo,
                    "valor":    valor,
                    "camara":   camara_id,
                    "foto_url": foto_url,
                    "conocido": False,
                    "rostros":  n_rostros,
                }).execute()
                print(f"Evento guardado: {tipo} cam={camara_id}")
            except Exception as e:
                print(f"Insert ERROR: {e}")

        _enviar_alerta(foto_out, tipo, valor, camara_id)

    except Exception as e:
        print(f"procesar_foto ERROR cam={camara_id}: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Alerta email
# ---------------------------------------------------------------------------
def _enviar_alerta(foto: bytes, tipo: str, valor: str, camara: str) -> None:
    if not GMAIL_USER or not GMAIL_PASS or not EMAIL_ALERTA:
        return
    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"ALERTA: {tipo.upper()} detectado — Camara {camara}" + (f" | {valor}" if valor else "")
        msg["From"]    = GMAIL_USER
        msg["To"]      = EMAIL_ALERTA
        msg.attach(MIMEText(f"Camara: {camara}\nTipo: {tipo}\nPlaca/valor: {valor or '-'}", "plain"))
        img = MIMEImage(foto, _subtype="jpeg")
        img.add_header("Content-Disposition", "attachment", filename="alerta.jpg")
        msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, EMAIL_ALERTA, msg.as_string())
        print(f"Alerta enviada a {EMAIL_ALERTA}")
    except Exception as e:
        print(f"Alerta email ERROR: {e}")


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

        # Ignorar alertas propias para no crear bucle
        if "ALERTA:" in asunto:
            mail.store(num, "+FLAGS", "\\Seen")
            return

        # Ignorar emails mas antiguos de 2 horas
        fecha_h = msg.get("Date")
        if fecha_h:
            try:
                dt = parsedate_to_datetime(fecha_h)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - dt > timedelta(hours=2):
                    mail.store(num, "+FLAGS", "\\Seen")
                    print(f"Email antiguo ignorado")
                    return
            except Exception:
                pass

        # Detectar camara desde asunto — DECODIFICAR RFC2047 PRIMERO
        asunto_dec = _decodificar(asunto)
        camara_base = _numero_camara(asunto_dec)
        print(f"Email: '{asunto_dec}' -> camara base={camara_base}")

        fotos = 0
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            # Obtener filename y decodificar RFC2047
            filename = _decodificar(part.get_filename() or "")
            if not filename:
                ct = part.get("Content-Type", "")
                m  = re.search(r'name=["\']?([^";]+)', ct)
                if m:
                    filename = _decodificar(m.group(1).strip())

            fname_lower = filename.lower()
            # Precisar camara desde nombre del archivo si es posible
            cam = _numero_camara(filename) if filename else camara_base
            if cam == "01" and camara_base != "01":
                cam = camara_base

            # Imagenes
            if any(fname_lower.endswith(e) for e in [".jpg", ".jpeg", ".png"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                fotos += 1
                print(f"Imagen '{filename}' -> cam {cam} ({len(data)//1024} KB)")
                threading.Thread(
                    target=procesar_foto, args=(data, cam),
                    daemon=True, name=f"proc-{cam}"
                ).start()

            # Videos (.mov que envia el DVR, tambien .mp4/.avi)
            elif any(fname_lower.endswith(e) for e in [".mov", ".mp4", ".avi", ".mkv"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                print(f"Video '{filename}' -> cam {cam} ({len(data)//1024} KB) - extrayendo frame...")
                ext = fname_lower[-4:]
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
                try:
                    cap   = cv2.VideoCapture(tmp_path)
                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    # Frame al 20% para evitar pantalla negra inicial
                    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(total * 0.20)))
                    ret, fr = cap.read()
                    cap.release()
                    if ret and fr is not None:
                        ok, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ok:
                            fotos += 1
                            threading.Thread(
                                target=procesar_foto, args=(buf.tobytes(), cam),
                                daemon=True, name=f"proc-{cam}"
                            ).start()
                except Exception as e:
                    print(f"Video ERROR: {e}")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        mail.store(num, "+FLAGS", "\\Seen")
        if fotos == 0:
            print("Sin adjuntos de imagen/video en este email")

    except Exception as e:
        print(f"_procesar_email ERROR: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Bucle IMAP — mantiene conexion abierta, reconecta con backoff
# ---------------------------------------------------------------------------
def _bucle_emails() -> None:
    backoff = 30
    while True:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(GMAIL_USER, GMAIL_PASS)
                backoff = 30  # reset al conectar bien
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
            print(f"IMAP ERROR: {e} — reintento en {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)  # maximo 5 minutos


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/")
def status():
    return {
        "status":   "Sistema de seguridad vecinal activo",
        "yolo":     model is not None,
        "ocr":      reader is not None,
        "supabase": supabase_client is not None,
    }


@app.get("/eventos")
def get_eventos():
    if not supabase_client:
        return []
    data = (
        supabase_client.table("eventos")
        .select("*")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return data.data
