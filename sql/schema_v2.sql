-- ============================================================
-- SEGURIDAD VECINAL — Schema v2 (Inteligencia + Deduplicacion)
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- ------------------------------------------------------------
-- 1. Identidades (cada persona/entidad detectada, conocida o no)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.identities (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  embedding     float8[]    NOT NULL,           -- 128 floats (dlib face_recognition)
  known         boolean     NOT NULL DEFAULT false,
  name          text,
  risk_level    int         NOT NULL DEFAULT 0, -- calculado, 0-100
  foto_url      text,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  visit_count   int         NOT NULL DEFAULT 1,
  metadata      jsonb                           -- edad estimada, notas, etc.
);

-- ------------------------------------------------------------
-- 2. Sesiones de deteccion (una por "visita" continua)
-- Una sesion agrupa todos los frames del mismo sujeto hasta 15 min de inactividad
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.detection_sessions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_id      uuid        REFERENCES public.identities(id) ON DELETE SET NULL,
  camera_id        text        NOT NULL,
  started_at       timestamptz NOT NULL DEFAULT now(),
  last_seen_at     timestamptz NOT NULL DEFAULT now(),
  ended_at         timestamptz,
  max_threat_score int         NOT NULL DEFAULT 0,
  frame_count      int         NOT NULL DEFAULT 1,
  tipo             text,       -- persona/vehiculo/movimiento
  evidence_url     text,       -- foto del momento pico de amenaza
  evidence_hash    text,       -- SHA-256 para cadena de custodia
  status           text        NOT NULL DEFAULT 'active', -- active/closed/escalated
  metadata         jsonb
);

-- ------------------------------------------------------------
-- 3. Alertas generadas (UNA por sesion relevante, no por frame)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.alerts (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id       uuid        REFERENCES public.detection_sessions(id) ON DELETE CASCADE,
  triggered_at     timestamptz NOT NULL DEFAULT now(),
  threat_score     int         NOT NULL DEFAULT 0,
  threat_level     text        NOT NULL DEFAULT 'green',
  -- green (0-25) / yellow (26-50) / orange (51-75) / red (76-100)
  reason           text,       -- 'rostro_desconocido_horario_nocturno'
  camera_id        text        NOT NULL,
  tipo             text,
  foto_url         text,
  identity_name    text,
  acknowledged     boolean     NOT NULL DEFAULT false,
  acknowledged_by  text,
  acknowledged_at  timestamptz,
  evidence_hash    text,       -- SHA-256 para autenticidad legal
  metadata         jsonb
);

-- ------------------------------------------------------------
-- RLS (Row Level Security)
-- ------------------------------------------------------------
ALTER TABLE public.identities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.detection_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts            ENABLE ROW LEVEL SECURITY;

-- identities
CREATE POLICY "identities_public_read"    ON public.identities FOR SELECT USING (true);
CREATE POLICY "identities_service_insert" ON public.identities FOR INSERT WITH CHECK (true);
CREATE POLICY "identities_service_update" ON public.identities FOR UPDATE USING (true);
CREATE POLICY "identities_service_delete" ON public.identities FOR DELETE USING (true);

-- detection_sessions
CREATE POLICY "sessions_public_read"    ON public.detection_sessions FOR SELECT USING (true);
CREATE POLICY "sessions_service_insert" ON public.detection_sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "sessions_service_update" ON public.detection_sessions FOR UPDATE USING (true);
CREATE POLICY "sessions_service_delete" ON public.detection_sessions FOR DELETE USING (true);

-- alerts
CREATE POLICY "alerts_public_read"    ON public.alerts FOR SELECT USING (true);
CREATE POLICY "alerts_service_insert" ON public.alerts FOR INSERT WITH CHECK (true);
CREATE POLICY "alerts_service_update" ON public.alerts FOR UPDATE USING (true);
CREATE POLICY "alerts_service_delete" ON public.alerts FOR DELETE USING (true);

-- ------------------------------------------------------------
-- Indices para rendimiento
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessions_camera_status  ON public.detection_sessions(camera_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_identity       ON public.detection_sessions(identity_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_seen      ON public.detection_sessions(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered        ON public.alerts(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged     ON public.alerts(acknowledged, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_threat           ON public.alerts(threat_score DESC);
CREATE INDEX IF NOT EXISTS idx_identities_known        ON public.identities(known, last_seen_at DESC);

-- ------------------------------------------------------------
-- NOTA: Si ya tienes la tabla desconocidos del schema v1,
-- puedes mantenerla. El nuevo sistema la complementa.
-- ------------------------------------------------------------

-- Tabla desconocidos (schema v1 — mantener por retrocompatibilidad)
CREATE TABLE IF NOT EXISTS public.desconocidos (
  id         bigserial   PRIMARY KEY,
  camara     text        NOT NULL,
  foto_url   text        NOT NULL DEFAULT '',
  aprobado   boolean     NOT NULL DEFAULT false,
  nombre     text,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.desconocidos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "desc_public_read"    ON public.desconocidos FOR SELECT USING (true);
CREATE POLICY "desc_service_insert" ON public.desconocidos FOR INSERT WITH CHECK (true);
CREATE POLICY "desc_service_update" ON public.desconocidos FOR UPDATE USING (true);
CREATE POLICY "desc_service_delete" ON public.desconocidos FOR DELETE USING (true);
