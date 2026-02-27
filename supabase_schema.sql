-- ─────────────────────────────────────────────
-- La tabla eventos ya existe, solo agregar columnas faltantes
-- ─────────────────────────────────────────────
alter table public.eventos add column if not exists id         bigserial;
alter table public.eventos add column if not exists tipo       text not null default 'persona';
alter table public.eventos add column if not exists valor      text default '';
alter table public.eventos add column if not exists camara     text not null default '01';
alter table public.eventos add column if not exists foto_url   text default '';
alter table public.eventos add column if not exists conocido   boolean default false;
alter table public.eventos add column if not exists rostros    integer default 0;
alter table public.eventos add column if not exists created_at timestamptz default now() not null;
-- Nuevo: nombre de la persona reconocida (null si desconocida)
alter table public.eventos add column if not exists nombre_persona text default null;

-- Índices para acelerar consultas del dashboard
create index if not exists eventos_created_at_idx on public.eventos (created_at desc);
create index if not exists eventos_camara_idx     on public.eventos (camara);
create index if not exists eventos_tipo_idx       on public.eventos (tipo);

-- ─────────────────────────────────────────────
-- Tabla de placas registradas (vehículos conocidos)
-- ─────────────────────────────────────────────
create table if not exists public.placas_registradas (
  id      bigserial primary key,
  placa   text not null unique,
  nombre  text not null,              -- nombre del dueño / descripción
  activo  boolean default true
);

-- ─────────────────────────────────────────────
-- Permisos: acceso público de lectura (anon key)
-- ─────────────────────────────────────────────
alter table public.eventos           enable row level security;
alter table public.placas_registradas enable row level security;

-- Política: cualquiera puede leer (el front usa anon key)
create policy "Lectura pública eventos"
  on public.eventos for select using (true);

create policy "Lectura pública placas"
  on public.placas_registradas for select using (true);

-- Política: solo el service role puede insertar (el backend usa service key)
create policy "Inserción service role eventos"
  on public.eventos for insert
  with check (true);

-- ─────────────────────────────────────────────
-- Storage bucket para fotos (si no existe)
-- ─────────────────────────────────────────────
insert into storage.buckets (id, name, public)
values ('eventos', 'eventos', true)
on conflict (id) do nothing;

-- Política storage: lectura pública
create policy "Lectura pública storage"
  on storage.objects for select
  using (bucket_id = 'eventos');

-- Política storage: subida con service role
create policy "Subida service role storage"
  on storage.objects for insert
  with check (bucket_id = 'eventos');

-- ─────────────────────────────────────────────
-- RECONOCIMIENTO FACIAL: tabla personas_conocidas
-- Ejecutar este bloque en Supabase SQL Editor
-- ─────────────────────────────────────────────
create table if not exists public.personas_conocidas (
  id          bigserial primary key,
  nombre      text      not null unique,
  descripcion text      default '',
  -- El embedding Facenet es un array JSON de 128 floats
  embedding   text      not null,          -- JSON serializado: "[0.12, -0.34, ...]"
  activo      boolean   default true,
  created_at  timestamptz default now() not null
);

-- Índice para búsqueda por nombre
create index if not exists personas_nombre_idx on public.personas_conocidas (nombre);

-- Permisos: el service role puede todo; anon solo lee (para el dashboard)
alter table public.personas_conocidas enable row level security;

create policy "Lectura pública personas"
  on public.personas_conocidas for select using (true);

create policy "Escritura service role personas"
  on public.personas_conocidas for all
  using (true) with check (true);
