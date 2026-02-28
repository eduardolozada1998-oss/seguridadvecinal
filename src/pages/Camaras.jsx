import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEstadisticasCamaras } from '../hooks/useEstadisticas'
import { formatearFecha, tiempoRelativo } from '../components/EventoCard'

export default function Camaras() {
  const navigate = useNavigate()
  const { camaras, cargando, error, recargar } = useEstadisticasCamaras()

  const irAGaleria = (numCamara) => {
    navigate(`/galeria?camara=${numCamara}`)
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <p className="text-red-400 font-medium">Error al cargar datos de cámaras</p>
          <p className="text-slate-400 text-sm mt-1">{error}</p>
          <button onClick={recargar} className="mt-4 btn-primary">Reintentar</button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Estado de Cámaras</h2>
          <p className="text-slate-400 text-sm">DVR Meriva N9000 · 4 canales activos</p>
        </div>
        <button
          onClick={recargar}
          disabled={cargando}
          className="btn-secondary flex items-center gap-2 self-start sm:self-auto"
        >
          <svg className={`w-4 h-4 ${cargando ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Actualizar
        </button>
      </div>

      {/* Cards de cámaras */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {cargando
          ? Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden animate-pulse">
              <div className="aspect-video bg-slate-700" />
              <div className="p-5 space-y-3">
                <div className="h-5 bg-slate-700 rounded w-1/3" />
                <div className="h-3 bg-slate-700 rounded w-2/3" />
                <div className="h-3 bg-slate-700 rounded w-1/2" />
                <div className="h-9 bg-slate-700 rounded" />
              </div>
            </div>
          ))
          : camaras.map((camara) => (
            <CamaraCard
              key={camara.id}
              camara={camara}
              onVerGaleria={() => irAGaleria(camara.id)}
            />
          ))}
      </div>

      {/* Leyenda */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <h3 className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3">Leyenda</h3>
        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
            <span className="text-slate-300 text-sm">Activa — tuvo actividad en la última hora</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-500" />
            <span className="text-slate-300 text-sm">Inactiva — sin eventos recientes</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function CamaraCard({ camara, onVerGaleria }) {
  const { nombre, totalHoy, ultimoEvento, activa } = camara
  const [imgError, setImgError] = useState(false)

  return (
    <div
      className={`bg-slate-800 border rounded-xl overflow-hidden hover:shadow-lg hover:shadow-black/30 transition-all duration-300 ${activa ? 'border-green-500/30 hover:border-green-500/50' : 'border-slate-700 hover:border-slate-600'
        }`}
    >
      {/* Foto última captura */}
      <div className="relative aspect-video bg-slate-900">
        {ultimoEvento?.foto_url && !imgError ? (
          <img
            src={ultimoEvento.foto_url}
            alt={`Última captura ${nombre}`}
            loading="lazy"
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-600 gap-2">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span className="text-xs">Sin capturas disponibles</span>
          </div>
        )}

        {/* Badge estado */}
        <div className="absolute top-3 right-3">
          <span className={`flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full ${activa
              ? 'bg-green-500/90 text-white'
              : 'bg-slate-700/90 text-slate-400'
            }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${activa ? 'bg-white animate-pulse' : 'bg-slate-500'}`} />
            {activa ? 'ACTIVA' : 'INACTIVA'}
          </span>
        </div>

        {/* Overlay nombre */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-4 py-3">
          <h3 className="text-white font-bold text-lg">{nombre}</h3>
        </div>
      </div>

      {/* Datos */}
      <div className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-center">
            <p className="text-2xl font-bold text-white">{totalHoy}</p>
            <p className="text-slate-500 text-xs">eventos hoy</p>
          </div>
          <div className="text-right">
            <p className="text-slate-300 text-sm font-medium">
              {ultimoEvento ? tiempoRelativo(ultimoEvento.created_at) : 'Sin eventos'}
            </p>
            <p className="text-slate-500 text-xs">
              {ultimoEvento ? formatearFecha(ultimoEvento.created_at) : '—'}
            </p>
          </div>
        </div>

        {/* Tipo del último evento */}
        {ultimoEvento && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 text-xs">Último:</span>
            <span className={ultimoEvento.tipo === 'vehiculo' ? 'badge-vehiculo' : 'badge-persona'}>
              {ultimoEvento.tipo === 'vehiculo' ? '🚗 Vehículo' : '🚶 Persona'}
            </span>
            {ultimoEvento.valor && (
              <span className="badge-placa">{ultimoEvento.valor}</span>
            )}
          </div>
        )}

        {/* Botón galería */}
        <button
          onClick={onVerGaleria}
          className="w-full btn-secondary flex items-center justify-center gap-2 mt-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          Ver galería
        </button>
      </div>
    </div>
  )
}

