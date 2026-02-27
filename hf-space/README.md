---
title: Seguridad Vecinal — Backend Completo
emoji: 🔒
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Backend Sistema de Seguridad Vecinal

FastAPI + YOLOv8n ONNX + Tesseract OCR + DeepFace + Supabase.

Reemplaza completamente al backend de Render.com.

## Secrets requeridos (Settings → Variables)

| Secret | Descripción |
|--------|-------------|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | **Service Role Key** de Supabase |
| `GMAIL_USER` | Email Gmail del DVR |
| `GMAIL_PASS` | Contraseña de aplicación Gmail |
| `EMAIL_ALERTA` | Email destino de alertas (puede ser el mismo) |
| `FACE_THRESHOLD` | Umbral similitud facial (default: `0.72`) |

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Estado del sistema (YOLO, DeepFace, Supabase, Tesseract) |
| `POST` | `/reconocer` | Reconoce rostro en imagen base64 |
| `POST` | `/registrar` | Registra nueva persona conocida |
| `GET` | `/personas` | Lista personas registradas |
| `DELETE` | `/personas/{id}` | Desactiva una persona |
