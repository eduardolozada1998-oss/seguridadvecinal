from fastapi import FastAPI, UploadFile, Form, File, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import hashlib
import uuid
import os
import re
import base64
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
from typing import Optional

# ---------------------------------------------------------------------------
# Variables de entorno
# ---------------------------------------------------------------------------
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")
GMAIL_USER    = os.environ.get("GMAIL_USER", "")
GMAIL_PASS    = os.environ.get("GMAIL_PASS", "")
EMAIL_ALERTA  = os.environ.get("EMAIL_ALERTA", GMAIL_USER)
# Gmail API (reemplaza IMAP — HF bloquea puerto 993)
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# Inteligencia v2
SESSION_TIMEOUT_MIN = int(os.environ.get("SESSION_TIMEOUT_MIN", "15"))  # min sin actividad = nueva sesion
COOLDOWN_VEHICULO   = int(os.environ.get("COOLDOWN_VEHICULO",   "60"))  # cooldown vehiculos sin rostro
COOLDOWN_MOVIMIENTO = int(os.environ.get("COOLDOWN_MOVIMIENTO", "10"))  # cooldown movimiento puro
ALERT_THRESHOLD     = int(os.environ.get("ALERT_THRESHOLD",     "25"))  # score minimo para generar alerta

# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------
supabase_client    = None
model              = None
reader             = None
face_cascade       = None
FR_DISPONIBLE      = False
personas_conocidas: list = []   # [{nombre, encoding, foto_url}] — registradas manualmente

# Cache de identidades detectadas (conocidas + desconocidas) en memoria
# [{id, encoding, known, name, visit_count}]
_identity_cache: list = []
_identity_lock  = threading.Lock()

# Sesiones activas: clave="identity_id-cam-tipo" -> dict con estado
_active_sessions: dict = {}
_sessions_lock   = threading.Lock()

# Cooldown legacy para vehiculos/movimiento sin rostro
_ultimo_evento: dict = {}

# ---------------------------------------------------------------------------
# Lifespan — inicializacion segura
# ---------------------------------------------------------------------------
def _inicializar_modelos():
    """Carga modelos ML en un hilo daemon para no bloquear el startup del servidor."""
    global supabase_client, model, reader, face_cascade, FR_DISPONIBLE

    print("Iniciando carga de modelos en segundo plano...")

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

    # MediaPipe Face Detection (mucho mejor que Haar: detecta perfiles, nocturno, parcial)
    try:
        import mediapipe as mp
        face_cascade = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.4
        )
        print("MediaPipe Face Detection OK")
    except Exception as e:
        # Fallback a Haar si MediaPipe no está disponible
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cc = cv2.CascadeClassifier(cascade_path)
            face_cascade = cc if not cc.empty() else None
            print("Face cascade Haar OK (fallback)" if face_cascade else "Face cascade ERROR")
        except Exception as e2:
            print(f"Face cascade ERROR: {e} / {e2}")

    # Face recognition (dlib)
    try:
        import face_recognition  # noqa: F401
        FR_DISPONIBLE = True
        cargar_personas()
        _cargar_identity_cache()   # cargar desconocidos recientes
        print(f"Face recognition OK — {len(personas_conocidas)} persona(s) | {len(_identity_cache)} identidades")
    except Exception as e:
        print(f"Face recognition no disponible: {e}")

    # Hilo lector de emails (Gmail API > IMAP — HF bloquea IMAP)
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN:
        t = threading.Thread(target=_bucle_gmail, daemon=True, name="gmail")
        t.start()
        print("Gmail API reader iniciado")
    elif GMAIL_USER and GMAIL_PASS:
        t = threading.Thread(target=_bucle_emails, daemon=True, name="imap")
        t.start()
        print("IMAP iniciado (legacy — puede fallar en HF)")
    else:
        print("WARN: Gmail no configurado")

    # Hilo de limpieza de sesiones caducadas
    threading.Thread(target=_bucle_limpieza_sesiones, daemon=True, name="cleanup").start()

    print("Modelos listos ✓")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arrancar carga de modelos en segundo plano para que HF vea el servidor listo
    threading.Thread(target=_inicializar_modelos, daemon=True, name="init").start()
    print("Servidor listo — modelos cargando en segundo plano")
    yield
    print("Sistema detenido")


app = FastAPI(title="Seguridad Vecinal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://seguridadvecinal.pages.dev", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _numero_camara(texto: str) -> Optional[str]:
    """Extrae numero de camara de cualquier texto.
    Devuelve '01'-'08' si encuentra patron, None si no hay match."""
    if not texto:
        return None
    # Normalizar: quitar acentos, pasar a minusculas
    norm = texto.lower()
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("\xe1","a")]:
        norm = norm.replace(src, dst)
    # Buscar patron: camara/camera seguido de numero
    m = re.search(r'c[a\xe1]mara\s*[_\-]?\s*0?(\d)', norm) \
        or re.search(r'camara\s*[_\-]?\s*0?(\d)', norm) \
        or re.search(r'camera\s*[_\-]?\s*0?(\d)', norm) \
        or re.search(r'cam\s*[_\-]?\s*0?(\d)', norm)
    return m.group(1).zfill(2) if m else None


def _numero_camara_fallback(texto: str) -> str:
    """Como _numero_camara pero devuelve '01' si no encuentra (compatibilidad)."""
    return _numero_camara(texto) or "01"


def _camara_desde_cuerpo(texto: str):
    """Extrae numero de camara del cuerpo XML/texto del DVR Meriva.
    Busca <Input1>3</Input1> o 'Fuente alarma : Cámara3'.
    Devuelve '01'-'08' o None si no encuentra."""
    if not texto:
        return None
    # XML del DVR: <Input1>3</Input1>
    m = re.search(r'<Input1>(\d+)</Input1>', texto)
    if m:
        return m.group(1).zfill(2)
    # Texto plano: "Fuente alarma : Cámara3"
    norm = texto
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u")]:
        norm = norm.replace(src, dst)
    m = re.search(r'Fuente alarma\s*:\s*[Cc]amara\s*(\d)', norm)
    if m:
        return m.group(1).zfill(2)
    return None


# ---------------------------------------------------------------------------
# Zona horaria y helpers
# ---------------------------------------------------------------------------
def _es_horario_nocturno() -> bool:
    """True si la hora local (TZ_OFFSET env, default -6 Mexico) es 22:00-06:00."""
    offset = int(os.environ.get("TZ_OFFSET", "-6"))
    hora   = datetime.now(timezone(timedelta(hours=offset))).hour
    return hora >= 22 or hora < 6


def cargar_personas() -> None:
    """Carga encodings de personas conocidas desde Supabase."""
    global personas_conocidas
    if not supabase_client:
        return
    try:
        res = supabase_client.table("personas").select("nombre,encoding,foto_url").execute()
        personas_conocidas = [
            {
                "nombre":   r["nombre"],
                "encoding": np.array(r["encoding"], dtype=np.float64),
                "foto_url": r.get("foto_url", ""),
            }
            for r in (res.data or [])
        ]
        print(f"Personas cargadas: {len(personas_conocidas)}")
    except Exception as e:
        print(f"cargar_personas ERROR: {e}")


# ---------------------------------------------------------------------------
# Cache de identidades  (conocidas + desconocidas detectadas)
# ---------------------------------------------------------------------------
def _cargar_identity_cache() -> None:
    """Carga identidades recientes de Supabase al arranque."""
    global _identity_cache
    if not supabase_client:
        return
    try:
        hace_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        res = supabase_client.table("identities") \
            .select("id,embedding,known,name,visit_count") \
            .gte("last_seen_at", hace_30d) \
            .execute()
        with _identity_lock:
            _identity_cache = []
            for r in (res.data or []):
                enc = r.get("embedding")
                if enc:
                    _identity_cache.append({
                        "id":          r["id"],
                        "encoding":    np.array(enc, dtype=np.float64),
                        "known":       r.get("known", False),
                        "name":        r.get("name") or "Desconocido",
                        "visit_count": r.get("visit_count", 1),
                    })
        print(f"Identity cache: {len(_identity_cache)} identidades")
    except Exception as e:
        print(f"_cargar_identity_cache ERROR: {e}")


def _buscar_en_cache(encoding: np.ndarray) -> Optional[dict]:
    """Busca identidad mas cercana en cache in-memory. Retorna dict o None."""
    import face_recognition as fr
    with _identity_lock:
        if not _identity_cache:
            return None
        encs  = [i["encoding"] for i in _identity_cache]
        dists = fr.face_distance(encs, encoding)
        idx   = int(np.argmin(dists))
        if dists[idx] < 0.55:   # ~cosine similarity > 0.85
            return _identity_cache[idx]
    return None


def _get_or_create_identity(
    encoding: np.ndarray,
    foto_url: str = "",
    known: bool = False,
    name: Optional[str] = None,
) -> Optional[str]:
    """Retorna identity_id existente o crea uno nuevo. Actualiza last_seen."""
    existing = _buscar_en_cache(encoding)
    if existing:
        nueva_vc = existing.get("visit_count", 1) + 1
        if supabase_client:
            try:
                supabase_client.table("identities").update({
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                    "visit_count":  nueva_vc,
                }).eq("id", existing["id"]).execute()
            except Exception:
                pass
        with _identity_lock:
            existing["visit_count"] = nueva_vc
        return existing["id"]

    if not supabase_client:
        return str(uuid.uuid4())
    try:
        row = supabase_client.table("identities").insert({
            "embedding":  encoding.tolist(),
            "known":      known,
            "name":       name,
            "foto_url":   foto_url,
            "risk_level": 0,
        }).execute()
        new_id = row.data[0]["id"]
        with _identity_lock:
            _identity_cache.append({
                "id":          new_id,
                "encoding":    encoding,
                "known":       known,
                "name":        name or "Desconocido",
                "visit_count": 1,
            })
        return new_id
    except Exception as e:
        print(f"_get_or_create_identity ERROR: {e}")
        return None


# ---------------------------------------------------------------------------
# Sesiones de deteccion
# ---------------------------------------------------------------------------
def _get_or_create_session(
    identity_id: Optional[str],
    camera_id: str,
    tipo: str,
) -> tuple:
    """
    Retorna (session_id, es_nueva_sesion).
    Reutiliza sesion activa si hubo actividad en < SESSION_TIMEOUT_MIN min.
    """
    ahora = datetime.now(timezone.utc)
    clave = f"{identity_id or 'noid'}-{camera_id}-{tipo}"

    with _sessions_lock:
        sess = _active_sessions.get(clave)
        if sess:
            elapsed = (ahora - sess["last_seen_at"]).total_seconds()
            if elapsed < SESSION_TIMEOUT_MIN * 60:
                sess["last_seen_at"] = ahora
                sess["frame_count"] += 1
                return sess["session_id"], False

        sess_id = None
        if supabase_client:
            try:
                r = supabase_client.table("detection_sessions").insert({
                    "identity_id": identity_id,
                    "camera_id":   camera_id,
                    "tipo":        tipo,
                    "status":      "active",
                }).execute()
                sess_id = r.data[0]["id"]
            except Exception as e:
                print(f"Session create ERROR: {e}")
                sess_id = str(uuid.uuid4())
        else:
            sess_id = str(uuid.uuid4())

        _active_sessions[clave] = {
            "session_id":       sess_id,
            "identity_id":      identity_id,
            "camera_id":        camera_id,
            "started_at":       ahora,
            "last_seen_at":     ahora,
            "frame_count":      1,
            "alert_sent":       False,
            "max_threat_score": 0,
            "clave":            clave,
        }
        return sess_id, True


def _update_session_threat(clave: str, threat_score: int, evidence_url: str = "") -> None:
    """Actualiza max_threat_score de sesion en memoria y DB."""
    with _sessions_lock:
        sess = _active_sessions.get(clave)
        if not sess or threat_score <= sess["max_threat_score"]:
            return
        sess["max_threat_score"] = threat_score
        sess_id = sess["session_id"]

    if supabase_client and sess_id:
        try:
            upd: dict = {
                "max_threat_score": threat_score,
                "last_seen_at":     datetime.now(timezone.utc).isoformat(),
            }
            if evidence_url:
                upd["evidence_url"] = evidence_url
            supabase_client.table("detection_sessions").update(upd).eq("id", sess_id).execute()
        except Exception as e:
            print(f"_update_session_threat ERROR: {e}")


def _should_generate_alert(clave: str, threat_score: int) -> tuple:
    """
    Retorna (generar:bool, motivo:str).
    Primera alerta si score >= ALERT_THRESHOLD.
    Alerta de escalada si sube >= 20 pts.
    """
    with _sessions_lock:
        sess = _active_sessions.get(clave)
        if not sess:
            return False, ""
        if not sess["alert_sent"]:
            if threat_score >= ALERT_THRESHOLD:
                sess["alert_sent"] = True
                return True, "primera_deteccion"
            return False, ""
        if threat_score - sess["max_threat_score"] >= 20:
            return True, "escalada"
    return False, ""


def _bucle_limpieza_sesiones() -> None:
    """Cada 5 minutos cierra en DB las sesiones inactivas."""
    while True:
        time.sleep(300)
        try:
            ahora    = datetime.now(timezone.utc)
            caducadas = []
            with _sessions_lock:
                for clave, sess in list(_active_sessions.items()):
                    if (ahora - sess["last_seen_at"]).total_seconds() > SESSION_TIMEOUT_MIN * 60:
                        caducadas.append((clave, sess["session_id"]))
                for clave, _ in caducadas:
                    del _active_sessions[clave]
            if caducadas and supabase_client:
                ids = [sid for _, sid in caducadas if sid]
                if ids:
                    supabase_client.table("detection_sessions").update({
                        "status":   "closed",
                        "ended_at": ahora.isoformat(),
                    }).in_("id", ids).execute()
                    print(f"Sesiones cerradas: {len(ids)}")
        except Exception as e:
            print(f"_bucle_limpieza ERROR: {e}")


# ---------------------------------------------------------------------------
# Threat Scoring (0-100, basado en reglas)
# ---------------------------------------------------------------------------
def _calcular_threat_score(
    tipo: str,
    is_known: bool,
    is_nighttime: bool,
    n_personas: int = 0,
    tiene_placa: bool = False,
) -> tuple:
    """
    Retorna (score:int 0-100, razon:str).
    Persona desconocida:   +40 | nocturno: x1.2 | 3+ personas: +10
    Vehiculo detectado:    +20 | sin placa: +10  | nocturno: x1.2
    Movimiento puro:       +15 | nocturno: +10 extra
    """
    score   = 0
    razones = []

    if tipo == "persona":
        if not is_known:
            score += 40
            razones.append("rostro_desconocido")
        if n_personas >= 3:
            score += 10
            razones.append("multiples_personas")
        if is_nighttime:
            score = int(score * 1.2)
            razones.append("horario_nocturno")
    elif tipo == "vehiculo":
        score += 20
        razones.append("vehiculo_detectado")
        if not tiene_placa:
            score += 10
            razones.append("sin_placa")
        if is_nighttime:
            score = int(score * 1.2)
            razones.append("horario_nocturno")
    else:
        score += 15
        razones.append("movimiento")
        if is_nighttime:
            score += 10
            razones.append("horario_nocturno")

    return min(100, score), "_".join(razones) if razones else "deteccion"


def _nivel_amenaza(score: int) -> str:
    if score <= 25:  return "green"
    if score <= 50:  return "yellow"
    if score <= 75:  return "orange"
    return "red"


# ---------------------------------------------------------------------------
# Guardar alerta inteligente en Supabase (tabla 'alerts')
# ---------------------------------------------------------------------------
def _guardar_alerta(
    session_id: str,
    threat_score: int,
    razon: str,
    camera_id: str,
    tipo: str,
    foto_url: str,
    identity_name: str,
    foto_bytes: Optional[bytes] = None,
) -> None:
    if not supabase_client:
        return
    try:
        evidence_hash = ""
        if foto_bytes:
            evidence_hash = hashlib.sha256(foto_bytes).hexdigest()
        supabase_client.table("alerts").insert({
            "session_id":    session_id,
            "threat_score":  threat_score,
            "threat_level":  _nivel_amenaza(threat_score),
            "reason":        razon,
            "camera_id":     camera_id,
            "tipo":          tipo,
            "foto_url":      foto_url,
            "identity_name": identity_name,
            "evidence_hash": evidence_hash,
        }).execute()
        print(f"Alerta guardada: {_nivel_amenaza(threat_score).upper()} score={threat_score} cam={camera_id}")
    except Exception as e:
        print(f"_guardar_alerta ERROR: {e}")


# ---------------------------------------------------------------------------
# Deteccion de rostros + reconocimiento (MediaPipe + face_recognition)
# ---------------------------------------------------------------------------
def _detectar_y_reconocer(frame: np.ndarray):
    """Devuelve lista de (nombre, (x,y,w,h), recorte_bytes, encoding_np).
    nombre='Desconocido' si no reconoce. encoding_np=None si FR no disponible."""
    if face_cascade is None:
        return []

    h_img, w_img = frame.shape[:2]
    coords = []

    # --- MediaPipe ---
    try:
        import mediapipe as mp
        if isinstance(face_cascade, mp.solutions.face_detection.FaceDetection):
            rgb_mp = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res_mp = face_cascade.process(rgb_mp)
            if res_mp.detections:
                for det in res_mp.detections:
                    bb = det.location_data.relative_bounding_box
                    x = max(0, int(bb.xmin * w_img))
                    y = max(0, int(bb.ymin * h_img))
                    w = int(bb.width  * w_img)
                    h = int(bb.height * h_img)
                    pad_x = int(w * 0.15)
                    pad_y = int(h * 0.20)
                    x = max(0, x - pad_x)
                    y = max(0, y - pad_y)
                    w = min(w_img - x, w + 2 * pad_x)
                    h = min(h_img - y, h + 2 * pad_y)
                    coords.append((x, y, w, h))
    except Exception:
        pass

    # --- Fallback Haar ---
    if not coords:
        try:
            gris   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            coords = list(face_cascade.detectMultiScale(
                gris, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            ))
        except Exception:
            pass

    if not coords:
        return []

    resultados = []
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if FR_DISPONIBLE else None

    for (x, y, w, h) in coords:
        recorte   = frame[y:y+h, x:x+w]
        ok, buf   = cv2.imencode(".jpg", recorte, [cv2.IMWRITE_JPEG_QUALITY, 90])
        recorte_b = buf.tobytes() if ok else None
        nombre    = "Desconocido"
        encoding_np = None

        if FR_DISPONIBLE and rgb is not None:
            import face_recognition as fr
            face_locs = [(y, x + w, y + h, x)]
            encs      = fr.face_encodings(rgb, known_face_locations=face_locs)
            if encs:
                encoding_np = encs[0]
                if len(personas_conocidas) > 0:
                    dists = fr.face_distance(
                        [p["encoding"] for p in personas_conocidas], encoding_np
                    )
                    idx = int(np.argmin(dists))
                    if dists[idx] < 0.55:
                        nombre = personas_conocidas[idx]["nombre"]

        resultados.append((nombre, (x, y, w, h), recorte_b, encoding_np))
    return resultados


# ---------------------------------------------------------------------------
# Guardar rostro desconocido en Supabase (tabla 'desconocidos')
# ---------------------------------------------------------------------------
def _guardar_rostro_desconocido(recorte_b: bytes, camara_id: str) -> None:
    """Sube el recorte de cara a Storage y lo registra en tabla 'desconocidos'."""
    if not supabase_client:
        return
    try:
        ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        nombre_arch = f"desc_{camara_id}_{ts}.jpg"
        supabase_client.storage.from_("desconocidos").upload(
            nombre_arch, recorte_b,
            file_options={"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/desconocidos/{nombre_arch}"
        supabase_client.table("desconocidos").insert({
            "camara":   camara_id,
            "foto_url": foto_url,
            "aprobado": False,   # pendiente de revision en el panel
            "nombre":   None,
        }).execute()
        print(f"Rostro desconocido guardado: {nombre_arch} cam={camara_id}")
    except Exception as e:
        print(f"_guardar_rostro_desconocido ERROR: {e}")


# ---------------------------------------------------------------------------
# PROCESAMIENTO PRINCIPAL DE FOTO (v2 — con sesiones + threat scoring)
# ---------------------------------------------------------------------------
def procesar_foto(img_bytes: bytes, camara_id: str) -> None:
    """
    Flujo v2:
    1. YOLO → tipo (persona/vehiculo) + OCR placa
    2. MediaPipe + face_recognition → rostros + embeddings
    3. Para cada rostro: buscar/crear identidad en cache
    4. Obtener/crear sesion activa (agrupa frames del mismo sujeto)
    5. Calcular threat_score (0-100)
    6. Si nueva sesion o escalada → guardar alerta en tabla 'alerts'
    7. Guardar evento en tabla 'eventos' (retrocompat. con Galeria)
    8. Subir imagen anotada a Storage
    """
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        tipo        = None
        valor       = ""   # placa OCR
        tiene_placa = False
        is_night    = _es_horario_nocturno()

        # ── 1. YOLO ────────────────────────────────────────────────────────────────────
        if model is not None:
            results = model(frame, classes=[0, 2, 3, 5, 7], verbose=False)
            for r in results:
                for box in r.boxes:
                    cls  = int(box.cls[0])
                    conf = float(box.conf[0])
                    if conf < 0.3:
                        continue
                    if cls == 0:
                        tipo = "persona"
                    elif cls in [2, 3, 5, 7]:
                        tipo = "vehiculo"
                        if reader is not None:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            h_f, w_f = frame.shape[:2]
                            pad  = int((y2 - y1) * 0.35)
                            roi  = frame[max(0, y1-pad):min(h_f, y2+pad),
                                         max(0, x1):min(w_f, x2)]
                            if roi.size > 0:
                                roi_big = cv2.resize(roi, None, fx=2, fy=2,
                                                     interpolation=cv2.INTER_CUBIC)
                                gris    = cv2.cvtColor(roi_big, cv2.COLOR_BGR2GRAY)
                                gris    = cv2.equalizeHist(gris)
                                textos  = reader.readtext(gris, detail=0,
                                                          allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ')
                                raw_placa = re.sub(r'[^A-Z0-9\-]', '',
                                                   " ".join(textos).strip().upper())
                                if len(raw_placa) >= 3:
                                    valor = raw_placa
                                    tiene_placa = True
                                    print(f"Placa OCR: '{valor}'")

        # ── 2. Rostros ───────────────────────────────────────────────────────────────────
        reconocidos = _detectar_y_reconocer(frame)
        n_rostros   = len(reconocidos)
        if n_rostros > 0:
            tipo = "persona"

        # ── 3 & 4. Identidades + Sesiones por cada rostro ───────────────────────
        # tupla: (session_id, clave, nombre, threat, razon, es_nueva, is_known, recorte_b)
        sesiones_frame: list = []

        for (nombre_r, (rx, ry, rw, rh), recorte_b, encoding_np) in reconocidos:
            is_known_r = nombre_r != "Desconocido"
            color = (0, 255, 0) if is_known_r else (0, 0, 255)
            cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), color, 2)
            cv2.putText(frame, nombre_r, (rx, max(ry - 8, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

            t_score, razon = _calcular_threat_score(
                tipo="persona", is_known=is_known_r,
                is_nighttime=is_night, n_personas=n_rostros,
            )

            identity_id = None
            if FR_DISPONIBLE and encoding_np is not None:
                identity_id = _get_or_create_identity(
                    encoding=encoding_np,
                    foto_url="",
                    known=is_known_r,
                    name=nombre_r if is_known_r else None,
                )

            session_id, es_nueva = _get_or_create_session(identity_id, camara_id, "persona")
            clave_sess = f"{identity_id or 'noid'}-{camara_id}-persona"
            sesiones_frame.append((session_id, clave_sess, nombre_r, t_score,
                                   razon, es_nueva, is_known_r, recorte_b))

            # Guardar recorte en tabla legacy desconocidos
            if not is_known_r and recorte_b and supabase_client:
                threading.Thread(
                    target=_guardar_rostro_desconocido,
                    args=(recorte_b, camara_id), daemon=True
                ).start()

            # Email sospechoso nocturno
            if not is_known_r and is_night and recorte_b:
                threading.Thread(
                    target=_enviar_alerta_sospechoso,
                    args=(recorte_b, camara_id), daemon=True
                ).start()

        # ── Fallback sin rostro (vehiculo/movimiento) ────────────────────────────
        if not sesiones_frame:
            if tipo is None:
                tipo  = "movimiento"
                valor = ""
                print(f"Cam {camara_id}: sin deteccion YOLO — guardando como movimiento")

            # Cooldown legacy para vehiculo/movimiento
            cooldown_mins = COOLDOWN_VEHICULO if tipo == "vehiculo" else COOLDOWN_MOVIMIENTO
            clave_cd = f"{camara_id}-{tipo}"
            ahora    = datetime.now(timezone.utc)
            ultimo   = _ultimo_evento.get(clave_cd)
            if ultimo and (ahora - ultimo).total_seconds() < cooldown_mins * 60:
                restante = int(cooldown_mins * 60 - (ahora - ultimo).total_seconds())
                print(f"Cam {camara_id}: cooldown {tipo} — ignorado ({restante}s restantes)")
                return
            _ultimo_evento[clave_cd] = ahora

            session_id, es_nueva = _get_or_create_session(None, camara_id, tipo)
            clave_sess = f"noid-{camara_id}-{tipo}"
            t_score, razon = _calcular_threat_score(
                tipo=tipo, is_known=False, is_nighttime=is_night, tiene_placa=tiene_placa,
            )
            sesiones_frame.append((session_id, clave_sess, tipo, t_score,
                                   razon, es_nueva, False, None))

        # ── 5. Subir imagen anotada a Storage ────────────────────────────────────
        # Upscale si el DVR envió imagen pequeña (< 640px ancho)
        h_fr, w_fr = frame.shape[:2]
        if w_fr < 640:
            scale  = 640 / w_fr
            frame  = cv2.resize(frame, (640, int(h_fr * scale)),
                                interpolation=cv2.INTER_LANCZOS4)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return
        foto_out    = buf.tobytes()
        ts          = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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

        # ── 6. Guardar en tabla eventos (retrocompat. Galeria) ───────────────────
        if supabase_client:
            try:
                hay_conocido = any(is_kn for *_, is_kn, _ in sesiones_frame)
                supabase_client.table("eventos").insert({
                    "tipo":     tipo,
                    "valor":    valor,
                    "camara":   camara_id,
                    "foto_url": foto_url,
                    "conocido": hay_conocido,
                    "rostros":  n_rostros,
                }).execute()
                print(f"Evento guardado: {tipo} cam={camara_id}")
            except Exception as e:
                print(f"Insert eventos ERROR: {e}")

        # ── 7. Alertas inteligentes (una por sesion, no por frame) ───────────────
        max_score = 0
        for (session_id, clave_sess, nombre_r, t_score, razon, es_nueva, is_known_r, _) \
                in sesiones_frame:
            _update_session_threat(clave_sess, t_score, foto_url)
            gen_alerta, motivo = _should_generate_alert(clave_sess, t_score)
            if gen_alerta and session_id:
                razon_final      = ("[ESCALADA] " if motivo == "escalada" else "") + razon
                identity_display = nombre_r if nombre_r not in ("", tipo) else tipo
                threading.Thread(
                    target=_guardar_alerta,
                    args=(session_id, t_score, razon_final, camara_id,
                          tipo, foto_url, identity_display, foto_out),
                    daemon=True
                ).start()
            max_score = max(max_score, t_score)

        # ── 8. Email de alerta (score alto) ──────────────────────────────────────
        if max_score >= ALERT_THRESHOLD:
            threading.Thread(
                target=_enviar_alerta,
                args=(foto_out, tipo, valor, camara_id), daemon=True
            ).start()

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


def _enviar_alerta_sospechoso(recorte: bytes, camara: str) -> None:
    """Envia email con recorte de cara desconocida detectada en horario nocturno."""
    if not GMAIL_USER or not GMAIL_PASS or not EMAIL_ALERTA:
        return
    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"SOSPECHOSO detectado — Camara {camara}"
        msg["From"]    = GMAIL_USER
        msg["To"]      = EMAIL_ALERTA
        msg.attach(MIMEText(
            f"Persona DESCONOCIDA detectada en horario nocturno.\nCamara: {camara}\n"
            "Revisa el dashboard para mas detalles.", "plain"
        ))
        img = MIMEImage(recorte, _subtype="jpeg")
        img.add_header("Content-Disposition", "attachment", filename="sospechoso.jpg")
        msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, EMAIL_ALERTA, msg.as_string())
        print(f"Alerta sospechoso enviada a {EMAIL_ALERTA}")
    except Exception as e:
        print(f"Alerta sospechoso ERROR: {e}")


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
                if datetime.now(timezone.utc) - dt > timedelta(hours=24):
                    mail.store(num, "+FLAGS", "\\Seen")
                    print(f"Email antiguo ignorado")
                    return
            except Exception:
                pass

        # Detectar camara desde asunto — DECODIFICAR RFC2047 PRIMERO
        asunto_dec = _decodificar(asunto)
        camara_base = _numero_camara_fallback(asunto_dec)
        print(f"Email: '{asunto_dec}' -> camara base={camara_base}")

        # Refinar camara leyendo el cuerpo del email (XML/texto del DVR Meriva)
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ('text/plain', 'text/xml', 'application/xml', 'text/html'):
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        cuerpo = payload.decode('utf-8', errors='replace')
                        cam_cuerpo = _camara_desde_cuerpo(cuerpo)
                        if cam_cuerpo:
                            camara_base = cam_cuerpo
                            print(f"Camara desde cuerpo XML: {camara_base}")
                            break
                    except Exception:
                        pass

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
            # Precisar camara desde nombre del archivo SOLO si hay match real.
            # Si el filename no contiene número de cámara, usar camara_base
            # (evita que archivos sin patrón se asignen falsamente a CAM 01).
            cam_de_archivo = _numero_camara(filename) if filename else None
            cam = cam_de_archivo if cam_de_archivo else camara_base
            print(f"  filename='{filename}' cam_archivo={cam_de_archivo} base={camara_base} -> cam={cam}")

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


# Estado del bucle de emails para diagnóstico
_imap_estado = {"ok": False, "ultimo_check": None, "ultimo_error": None, "emails_procesados": 0}


# ---------------------------------------------------------------------------
# Gmail API — reemplaza IMAP (HF bloquea puerto 993, API usa HTTPS 443)
# ---------------------------------------------------------------------------
def _get_gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
    )
    return build("gmail", "v1", credentials=creds)


def _marcar_leido_gmail(service, msg_id: str) -> None:
    try:
        service.users().messages().modify(
            userId="me", id=msg_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
    except Exception as e:
        print(f"Gmail marcar leido ERROR: {e}")


def _procesar_mensaje_gmail(service, msg_id: str) -> None:
    """Descarga mensaje completo via Gmail API y lo procesa igual que IMAP."""
    try:
        raw = service.users().messages().get(
            userId="me", id=msg_id, format="raw"
        ).execute()
        raw_bytes = base64.urlsafe_b64decode(raw["raw"] + "==")
        msg = email.message_from_bytes(raw_bytes)

        asunto = msg.get("Subject", "")
        if "ALERTA:" in asunto:
            _marcar_leido_gmail(service, msg_id)
            return

        fecha_h = msg.get("Date")
        if fecha_h:
            try:
                dt = parsedate_to_datetime(fecha_h)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - dt > timedelta(hours=24):
                    _marcar_leido_gmail(service, msg_id)
                    print(f"Email antiguo ignorado")
                    return
            except Exception:
                pass

        asunto_dec  = _decodificar(asunto)
        camara_base = _numero_camara(asunto_dec)
        print(f"Gmail: '{asunto_dec}' -> camara base={camara_base}")

        # Leer camara desde cuerpo XML del DVR
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ("text/plain", "text/xml", "application/xml", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        cuerpo = payload.decode("utf-8", errors="replace")
                        cam_cuerpo = _camara_desde_cuerpo(cuerpo)
                        if cam_cuerpo:
                            camara_base = cam_cuerpo
                            print(f"Camara desde XML: {camara_base}")
                            break
                    except Exception:
                        pass

        fotos = 0
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = _decodificar(part.get_filename() or "")
            if not filename:
                ct = part.get("Content-Type", "")
                m  = re.search(r'name=["\']?([^";\']+)', ct)
                if m:
                    filename = _decodificar(m.group(1).strip())
            fname_lower = filename.lower()
            cam = _numero_camara(filename) if filename else camara_base
            if cam == "01" and camara_base != "01":
                cam = camara_base

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
                    tmp.write(data)
                    tmp_path = tmp.name
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
                    print(f"Video ERROR: {e}")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        _marcar_leido_gmail(service, msg_id)
        _imap_estado["emails_procesados"] += 1
        if fotos == 0:
            print("Sin adjuntos de imagen/video en este email")

    except Exception as e:
        print(f"_procesar_mensaje_gmail ERROR: {e}")
        traceback.print_exc()


def _bucle_gmail() -> None:
    """Polling Gmail API cada 30s. Usa HTTPS (puerto 443), funciona en HF."""
    global _imap_estado
    backoff = 30
    while True:
        try:
            service = _get_gmail_service()
            _imap_estado["ok"]          = True
            _imap_estado["ultimo_error"] = None
            backoff = 30
            print("Gmail API conectado OK")
            while True:
                res  = service.users().messages().list(
                    userId="me", q="is:unread in:inbox", maxResults=20
                ).execute()
                msgs = res.get("messages", [])
                _imap_estado["ultimo_check"] = datetime.now(timezone.utc).isoformat()
                if msgs:
                    print(f"{len(msgs)} email(s) nuevo(s)")
                    for m in msgs:
                        _procesar_mensaje_gmail(service, m["id"])
                else:
                    print("Sin emails nuevos")
                time.sleep(30)
        except Exception as e:
            _imap_estado["ok"]          = False
            _imap_estado["ultimo_error"] = str(e)
            print(f"Gmail API ERROR: {e} — reintento en {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


# ---------------------------------------------------------------------------
# Bucle IMAP legacy — mantiene conexion abierta, reconecta con backoff
# (solo se usa si no hay credenciales Gmail API configuradas)
# ---------------------------------------------------------------------------
def _bucle_emails() -> None:
    global _imap_estado
    backoff = 30
    while True:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(GMAIL_USER, GMAIL_PASS)
                backoff = 30
                _imap_estado["ok"] = True
                _imap_estado["ultimo_error"] = None
                while True:
                    mail.select("INBOX")
                    _, nums = mail.search(None, "UNSEEN")
                    ids = nums[0].split() if nums[0] else []
                    _imap_estado["ultimo_check"] = datetime.now(timezone.utc).isoformat()
                    if ids:
                        print(f"{len(ids)} email(s) nuevo(s)")
                        for num in ids:
                            _procesar_email(mail, num)
                            _imap_estado["emails_procesados"] += 1
                    else:
                        print("Sin emails nuevos")
                    time.sleep(30)
        except Exception as e:
            _imap_estado["ok"] = False
            _imap_estado["ultimo_error"] = str(e)
            print(f"IMAP ERROR: {e} — reintento en {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


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


# ---------------------------------------------------------------------------
# API — Alertas inteligentes (v2)
# ---------------------------------------------------------------------------
@app.get("/alerts")
def get_alerts(
    status_filter: str = Query("all", alias="status"),
    min_threat:    int  = Query(0),
    camera_id:     str  = Query(None),
    limit:         int  = Query(50),
):
    """
    Retorna alertas ordenadas por triggered_at DESC.
    status: all | active (no atendidas) | acknowledged
    """
    if not supabase_client:
        return []
    try:
        q = (
            supabase_client.table("alerts")
            .select("*")
            .gte("threat_score", min_threat)
            .order("triggered_at", desc=True)
            .limit(limit)
        )
        if status_filter == "active":
            q = q.eq("acknowledged", False)
        elif status_filter == "acknowledged":
            q = q.eq("acknowledged", True)
        if camera_id:
            q = q.eq("camera_id", camera_id)
        res = q.execute()
        return res.data or []
    except Exception as e:
        return {"error": str(e)}


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, operator: str = Form(default="operador")):
    """Marca una alerta como atendida."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    try:
        supabase_client.table("alerts").update({
            "acknowledged":    True,
            "acknowledged_by": operator,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", alert_id).execute()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/alerts/acknowledge-all")
def acknowledge_all_alerts(operator: str = Form(default="operador")):
    """Marca todas las alertas pendientes como atendidas."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    try:
        supabase_client.table("alerts").update({
            "acknowledged":    True,
            "acknowledged_by": operator,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        }).eq("acknowledged", False).execute()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/alerts/stats")
def get_alert_stats():
    """Resumen de alertas de las ultimas 24h por nivel de amenaza."""
    if not supabase_client:
        return {}
    try:
        hace_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        res = supabase_client.table("alerts") \
            .select("threat_level, acknowledged") \
            .gte("triggered_at", hace_24h) \
            .execute()
        stats = {"red": 0, "orange": 0, "yellow": 0, "green": 0, "total": 0, "pending": 0}
        for r in (res.data or []):
            lvl = r.get("threat_level", "green")
            stats[lvl] = stats.get(lvl, 0) + 1
            stats["total"] += 1
            if not r.get("acknowledged", False):
                stats["pending"] += 1
        return stats
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# API — Sesiones de deteccion
# ---------------------------------------------------------------------------
@app.get("/sessions")
def get_sessions(
    status_filter: str = Query("active", alias="status"),
    limit:         int  = Query(20),
):
    if not supabase_client:
        return []
    try:
        q = supabase_client.table("detection_sessions") \
            .select("*") \
            .order("last_seen_at", desc=True) \
            .limit(limit)
        if status_filter != "all":
            q = q.eq("status", status_filter)
        res = q.execute()
        return res.data or []
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# API — Identidades
# ---------------------------------------------------------------------------
@app.get("/identities")
def get_identities(limit: int = 50):
    """Lista identidades detectadas (sin embeddings para no saturar la respuesta)."""
    if not supabase_client:
        return []
    try:
        res = supabase_client.table("identities") \
            .select("id,known,name,risk_level,foto_url,first_seen_at,last_seen_at,visit_count") \
            .order("last_seen_at", desc=True) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception as e:
        return {"error": str(e)}


@app.delete("/identities/old")
def limpiar_identidades_viejas(dias: int = Query(30)):
    """Elimina identidades desconocidas no vistas hace X dias (privacidad/GDPR)."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    try:
        corte = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        supabase_client.table("identities").delete() \
            .eq("known", False) \
            .lt("last_seen_at", corte) \
            .execute()
        _cargar_identity_cache()
        return {"ok": True, "dias": dias}
    except Exception as e:
        return {"error": str(e)}


@app.get("/personas")
def listar_personas():
    """Lista las personas registradas para reconocimiento."""
    return [
        {"nombre": p["nombre"], "foto_url": p.get("foto_url", "")}
        for p in personas_conocidas
    ]


@app.post("/registrar-persona")
async def registrar_persona(nombre: str = Form(...), foto: UploadFile = File(...)):
    """Registra una persona conocida. Se sube una foto con cara visible."""
    if not FR_DISPONIBLE:
        return {"error": "face_recognition no disponible en este servidor"}
    import face_recognition as fr

    data  = await foto.read()
    nparr = np.frombuffer(data, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "No se pudo leer la imagen"}

    rgb  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    encs = fr.face_encodings(rgb)
    if not encs:
        return {"error": "No se detectó ningún rostro en la imagen"}

    enc      = encs[0].tolist()   # 128 floats
    foto_url = ""

    if supabase_client:
        # Guardar foto en storage
        ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        arch = f"{nombre}_{ts}.jpg"
        try:
            supabase_client.storage.from_("personas").upload(
                arch, data, file_options={"content-type": "image/jpeg"}
            )
            foto_url = f"{SUPABASE_URL}/storage/v1/object/public/personas/{arch}"
        except Exception as e:
            print(f"Storage personas ERROR: {e}")
        # Guardar encoding en tabla
        try:
            supabase_client.table("personas").insert({
                "nombre":   nombre,
                "encoding": enc,
                "foto_url": foto_url,
            }).execute()
        except Exception as e:
            return {"error": str(e)}

    cargar_personas()
    # Tambien sincronizar con tabla identities
    _get_or_create_identity(encs[0], foto_url, known=True, name=nombre)
    return {"ok": True, "nombre": nombre, "total": len(personas_conocidas)}


@app.delete("/personas/{nombre}")
def eliminar_persona(nombre: str):
    """Elimina una persona del registro."""
    if supabase_client:
        supabase_client.table("personas").delete().eq("nombre", nombre).execute()
    cargar_personas()
    return {"ok": True}


@app.post("/recargar-personas")
def recargar_personas_endpoint():
    """Fuerza recarga de encodings desde Supabase."""
    cargar_personas()
    _cargar_identity_cache()
    return {"ok": True, "total": len(personas_conocidas), "identidades": len(_identity_cache)}


@app.get("/debug")
def debug():
    """Diagnostico completo del sistema v2."""
    hilos = [t.name for t in threading.enumerate()]
    sb_ok = False
    sb_error = None
    sb_eventos = None
    if supabase_client:
        try:
            r = supabase_client.table("eventos").select("id,camara,tipo,created_at").order("created_at", desc=True).limit(5).execute()
            sb_ok = True
            sb_eventos = r.data
        except Exception as e:
            sb_error = str(e)
    return {
        "version": "2.0",
        "modelos": {
            "yolo":             model is not None,
            "ocr":              reader is not None,
            "face_cascade":     face_cascade is not None,
            "face_recognition": FR_DISPONIBLE,
            "supabase":         supabase_client is not None,
        },
        "inteligencia": {
            "identity_cache_size":   len(_identity_cache),
            "active_sessions":       len(_active_sessions),
            "session_timeout_min":   SESSION_TIMEOUT_MIN,
            "alert_threshold_score": ALERT_THRESHOLD,
            "cooldown_vehiculo_min": COOLDOWN_VEHICULO,
            "cooldown_movimiento_min": COOLDOWN_MOVIMIENTO,
        },
        "imap":   _imap_estado,
        "gmail_api_configurada": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN),
        "gmail_user":            GMAIL_USER[:4] + "****" if GMAIL_USER else None,
        "personas_cargadas":     len(personas_conocidas),
        "hilos_activos":         hilos,
        "supabase_query":        {"ok": sb_ok, "error": sb_error, "ultimos_eventos": sb_eventos},
        "hora_servidor_utc":     datetime.now(timezone.utc).isoformat(),
    }


@app.post("/forzar-emails")
def forzar_emails():
    """Fuerza procesado de todos los emails no leidos via Gmail API."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_REFRESH_TOKEN:
        return {"error": "Gmail API no configurada. Agrega GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REFRESH_TOKEN en los Secrets del HF Space."}
    resultados = []
    try:
        service = _get_gmail_service()
        res  = service.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=20
        ).execute()
        msgs = res.get("messages", [])
        resultados.append(f"Emails no leidos encontrados: {len(msgs)}")
        for m in msgs:
            try:
                raw = service.users().messages().get(
                    userId="me", id=m["id"], format="raw"
                ).execute()
                raw_bytes = base64.urlsafe_b64decode(raw["raw"] + "==")
                msg    = email.message_from_bytes(raw_bytes)
                asunto = _decodificar(msg.get("Subject", ""))
                fecha  = msg.get("Date", "")
                resultados.append(f"Email: '{asunto}' | {fecha}")
                _procesar_mensaje_gmail(service, m["id"])
            except Exception as e:
                resultados.append(f"Error en email {m['id']}: {e}")
    except Exception as e:
        return {"error": str(e), "log": resultados}
    return {"ok": True, "log": resultados}


def _procesar_email_forzado(mail, num, msg) -> None:
    """Igual que _procesar_email pero sin filtro de antiguedad."""
    try:
        asunto = msg.get("Subject", "")
        if "ALERTA:" in asunto:
            mail.store(num, "+FLAGS", "\\Seen")
            return

        asunto_dec  = _decodificar(asunto)
        camara_base = _numero_camara(asunto_dec)
        print(f"[FORZADO] Email: '{asunto_dec}' -> camara base={camara_base}")

        # Leer camara desde cuerpo XML
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ('text/plain', 'text/xml', 'application/xml', 'text/html'):
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        cuerpo = payload.decode('utf-8', errors='replace')
                        cam_cuerpo = _camara_desde_cuerpo(cuerpo)
                        if cam_cuerpo:
                            camara_base = cam_cuerpo
                            print(f"[FORZADO] Camara desde XML: {camara_base}")
                            break
                    except Exception:
                        pass

        fotos = 0
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename   = _decodificar(part.get_filename() or "")
            fname_lower = filename.lower()
            cam = _numero_camara(filename) if filename else camara_base
            if cam == "01" and camara_base != "01":
                cam = camara_base

            if any(fname_lower.endswith(e) for e in [".jpg", ".jpeg", ".png"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                fotos += 1
                print(f"[FORZADO] Imagen '{filename}' -> cam {cam}")
                threading.Thread(target=procesar_foto, args=(data, cam), daemon=True).start()

            elif any(fname_lower.endswith(e) for e in [".mov", ".mp4", ".avi", ".mkv"]):
                data = part.get_payload(decode=True)
                if not data:
                    continue
                ext = fname_lower[-4:]
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
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
                            print(f"[FORZADO] Video '{filename}' -> cam {cam}")
                            threading.Thread(target=procesar_foto, args=(buf.tobytes(), cam), daemon=True).start()
                except Exception as e:
                    print(f"[FORZADO] Video ERROR: {e}")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        mail.store(num, "+FLAGS", "\\Seen")
        print(f"[FORZADO] {fotos} foto(s)/video(s) procesados en cam={camara_base}")
    except Exception as e:
        print(f"_procesar_email_forzado ERROR: {e}")
        traceback.print_exc()


@app.post("/test-supabase")
def test_supabase():
    """Inserta un evento de prueba en Supabase para verificar la conexion."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    try:
        supabase_client.table("eventos").insert({
            "tipo":     "persona",
            "valor":    "TEST",
            "camara":   "03",
            "foto_url": "",
            "conocido": False,
            "rostros":  0,
        }).execute()
        return {"ok": True, "mensaje": "Evento de prueba insertado en camara 03"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# API — Desconocidos (panel de administracion)
# ---------------------------------------------------------------------------
@app.get("/desconocidos")
def listar_desconocidos(limit: int = 50):
    """Lista los rostros desconocidos capturados, pendientes de revision."""
    if not supabase_client:
        return []
    try:
        res = (
            supabase_client.table("desconocidos")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        return {"error": str(e)}


@app.post("/desconocidos/{id}/aprobar")
async def aprobar_desconocido(id: int, nombre: str = Form(...)):
    """Aprueba un rostro desconocido: le asigna nombre y lo registra como persona conocida.
    El sistema descargara la foto y generara el encoding automaticamente."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    if not FR_DISPONIBLE:
        return {"error": "face_recognition no disponible"}
    try:
        import face_recognition as fr
        import urllib.request

        # Obtener el registro
        row = supabase_client.table("desconocidos").select("*").eq("id", id).single().execute()
        if not row.data:
            return {"error": "No encontrado"}
        foto_url = row.data["foto_url"]

        # Descargar foto y generar encoding
        with urllib.request.urlopen(foto_url) as resp:
            img_bytes = resp.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "No se pudo leer la imagen"}
        rgb  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encs = fr.face_encodings(rgb)
        if not encs:
            return {"error": "No se detecto rostro en la imagen guardada"}

        enc = encs[0].tolist()

        # Registrar en tabla personas
        supabase_client.table("personas").insert({
            "nombre":   nombre,
            "encoding": enc,
            "foto_url": foto_url,
        }).execute()

        # Marcar como aprobado en tabla desconocidos
        supabase_client.table("desconocidos").update({
            "aprobado": True,
            "nombre":   nombre,
        }).eq("id", id).execute()

        cargar_personas()
        return {"ok": True, "nombre": nombre, "total_personas": len(personas_conocidas)}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/desconocidos/{id}")
def eliminar_desconocido(id: int):
    """Elimina un rostro desconocido de la lista (descartar)."""
    if not supabase_client:
        return {"error": "Supabase no conectado"}
    try:
        supabase_client.table("desconocidos").delete().eq("id", id).execute()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
