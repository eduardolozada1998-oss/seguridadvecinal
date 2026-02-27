import { useState } from 'react'

/**
 * Formatea la fecha en español de forma legible
 */
function formatearFecha(isoString) {
  if (!isoString) return 'Sin fecha'
  const fecha = new Date(isoString)
  return fecha.toLocaleDateString('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Calcula hace cuánto tiempo ocurrió el evento
 */
function tiempoRelativo(isoString) {
  if (!isoString) return ''
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora mismo'
  if (mins < 60) return `hace ${mins} min`
  const horas = Math.floor(mins / 60)
  if (horas < 24) return `hace ${horas}h`
  return `hace ${Math.floor(horas / 24)} días`
}

/**
 * Tarjeta de evento individual con foto y metadatos
 */
export default function EventoCard({ evento, onClick }) {
  const [imgError, setImgError] = useState(false)
  const esVehiculo = evento.tipo === 'vehiculo'

  return (
    <div
      className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden hover:border-slate-500 hover:shadow-lg hover:shadow-black/30 transition-all duration-300 cursor-pointer group"
      onClick={() => onClick && onClick(evento)}
    >
      {/* Foto */}
      <div className="relative aspect-video bg-slate-900 overflow-hidden">
        {!imgError ? (
          <img
            src={evento.foto_url}
            alt={`Evento cámara ${evento.camara}`}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 gap-2">
            <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-xs">Imagen no disponible</span>
          </div>
        )}

        {/* Overlay con badges */}
        <div className="absolute top-2 left-2 flex flex-wrap gap-1">
          <span className={esVehiculo ? 'badge-vehiculo' : 'badge-persona'}>
            {esVehiculo ? '🚗 VEHÍCULO' : '🚶 PERSONA'}
          </span>
          <span className="bg-slate-900/80 text-slate-300 border border-slate-600 px-2 py-0.5 rounded text-xs font-semibold">
            CAM {evento.camara}
          </span>
        </div>

        {/* Placa si existe */}
        {evento.valor && evento.valor.trim() && (
          <div className="absolute bottom-2 left-2">
            <span className="badge-placa">
              🔖 {evento.valor}
            </span>
          </div>
        )}
      </div>

      {/* Metadatos */}
      <div className="p-3">
        <p className="text-slate-300 text-sm font-medium">{formatearFecha(evento.created_at)}</p>
        <p className="text-slate-500 text-xs mt-0.5">{tiempoRelativo(evento.created_at)}</p>
      </div>
    </div>
  )
}

export { formatearFecha, tiempoRelativo }
