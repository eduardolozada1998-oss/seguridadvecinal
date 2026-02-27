# Seguridad Vecinal

Sistema de seguridad vecinal con detección de personas, vehículos y placas usando YOLOv8 + OpenCV + Tesseract OCR.

## Estructura

```
├── src/                          # Frontend React (Cloudflare Pages)
├── seguridad-vecinal-backend/    # Backend FastAPI (Render.com)
│   ├── app.py
│   ├── requirements.txt
│   └── render.yaml
├── .env.example
├── vite.config.js
└── package.json
```

## Frontend (React + Vite)

```bash
npm install
npm run dev
```

## Backend (FastAPI + ONNX)

Ver `seguridad-vecinal-backend/README` o deploy directo en Render.com conectando este repo.

## Variables de entorno

Copia `.env.example` a `.env` y completa tus credenciales.
