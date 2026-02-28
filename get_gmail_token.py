"""
Ejecutar UNA SOLA VEZ localmente para obtener el refresh_token de Gmail API.

Pasos previos:
  1. Ve a https://console.cloud.google.com/
  2. Crea un proyecto (o selecciona uno existente)
  3. Habilita "Gmail API" en "APIs y Servicios" > "Biblioteca"
  4. En "APIs y Servicios" > "Credenciales" > "Crear Credenciales" > "ID de cliente OAuth 2.0"
     - Tipo: "Aplicacion de escritorio"
     - Descarga el JSON o copia el Client ID y Client Secret
  5. En "Pantalla de Consentimiento OAuth" agrega tu email como usuario de prueba
  6. Pon tu CLIENT_ID y CLIENT_SECRET abajo y ejecuta:
       python get_gmail_token.py

Copia los 3 valores que se imprimen y agregalos en HF Space > Settings > Variables and secrets.
"""

CLIENT_ID     = "TU_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "TU_GOOGLE_CLIENT_SECRET"

# -----------------------------------------------------------------------
import json, webbrowser, urllib.parse, urllib.request, http.server, threading

REDIRECT_URI = "http://localhost:8888"
SCOPE        = "https://www.googleapis.com/auth/gmail.modify"

auth_url = (
    "https://accounts.google.com/o/oauth2/auth?"
    + urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
    })
)

code_holder = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code_holder["code"] = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Listo! Puedes cerrar esta ventana.</h2>")
    def log_message(self, *a): pass

server = http.server.HTTPServer(("localhost", 8888), Handler)
t = threading.Thread(target=server.handle_request)
t.start()

print("Abriendo navegador para autorizar Gmail API...")
webbrowser.open(auth_url)
t.join(timeout=120)

code = code_holder.get("code")
if not code:
    print("ERROR: no se recibio el codigo. Verifica que CLIENT_ID sea correcto.")
    exit(1)

# Intercambiar code por tokens
data = urllib.parse.urlencode({
    "code":          code,
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri":  REDIRECT_URI,
    "grant_type":    "authorization_code",
}).encode()

req  = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
resp = urllib.request.urlopen(req)
tokens = json.loads(resp.read())

print("\n" + "="*60)
print("Agrega estos 3 secrets en HF Space > Settings > Secrets:")
print("="*60)
print(f"GOOGLE_CLIENT_ID     = {CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET = {CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN = {tokens.get('refresh_token')}")
print("="*60)
