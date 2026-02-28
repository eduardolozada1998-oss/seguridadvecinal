$CLIENT_ID     = "TU_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
$CLIENT_SECRET = "TU_GOOGLE_CLIENT_SECRET"
$REDIRECT_URI  = "http://localhost:8888"
$SCOPE         = "https://www.googleapis.com/auth/gmail.modify"

# Abrir navegador para autorizar
$authUrl = "https://accounts.google.com/o/oauth2/auth?" +
    "client_id=$CLIENT_ID" +
    "&redirect_uri=$([Uri]::EscapeDataString($REDIRECT_URI))" +
    "&response_type=code" +
    "&scope=$([Uri]::EscapeDataString($SCOPE))" +
    "&access_type=offline" +
    "&prompt=consent"

Write-Host "Abriendo navegador para autorizar Gmail API..." -ForegroundColor Cyan
Start-Process $authUrl

# Escuchar en puerto 8888 para capturar el codigo
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("$REDIRECT_URI/")
$listener.Start()
Write-Host "Esperando autorizacion en $REDIRECT_URI ..." -ForegroundColor Yellow

$context = $listener.GetContext()
$query = $context.Request.Url.Query.TrimStart('?')
$params = @{}
$query -split '&' | ForEach-Object {
    $kv = $_ -split '=', 2
    if ($kv.Length -eq 2) { $params[$kv[0]] = [Uri]::UnescapeDataString($kv[1]) }
}
$code = $params["code"]

# Responder al navegador
$response = $context.Response
$html = "<h2>Listo! Puedes cerrar esta ventana.</h2>"
$buffer = [System.Text.Encoding]::UTF8.GetBytes($html)
$response.ContentLength64 = $buffer.Length
$response.OutputStream.Write($buffer, 0, $buffer.Length)
$response.OutputStream.Close()
$listener.Stop()

if (-not $code) {
    Write-Host "ERROR: no se recibio el codigo." -ForegroundColor Red
    exit 1
}

Write-Host "Codigo recibido, obteniendo tokens..." -ForegroundColor Green

# Intercambiar code por refresh_token
$body = "code=$code" +
    "&client_id=$CLIENT_ID" +
    "&client_secret=$CLIENT_SECRET" +
    "&redirect_uri=$([Uri]::EscapeDataString($REDIRECT_URI))" +
    "&grant_type=authorization_code"

$resp = Invoke-RestMethod -Method POST `
    -Uri "https://oauth2.googleapis.com/token" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $body

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "Agrega estos 3 secrets en HF Space > Settings > Secrets:" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "GOOGLE_CLIENT_ID     = $CLIENT_ID" -ForegroundColor White
Write-Host "GOOGLE_CLIENT_SECRET = $CLIENT_SECRET" -ForegroundColor White
Write-Host "GOOGLE_REFRESH_TOKEN = $($resp.refresh_token)" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Green
