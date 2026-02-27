import { useEffect, useState } from 'react'
import { formatearFecha } from './EventoCard'

/**
 * Modal con imagen grande y detalle completo del evento
 */
export default function PhotoModal({ evento, onCerrar }) {
  const [imgError, setImgError] = useState(false)

  // Cerrar con Escape
  useEffect(() => {
    const manejarTeclado = (e) => {
      if (e.key === 'Escape') onCerrar()
    }
    window.addEventListener('keydown', manejarTeclado)
    return () => window.removeEventListener('keydown', manejarTeclado)
  }, [onCerrar])

  // Bloquear scroll del body
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  if (!evento) return null

  const esVehiculo = evento.tipo === 'vehiculo'

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onCerrar}
    >
      <div
        className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <span className={esVehiculo ? 'badge-vehiculo text-sm px-3 py-1' : 'badge-persona text-sm px-3 py-1'}>
              {esVehiculo ? '🚗 VEHÍCULO' : '🚶 PERSONA'}
            </span>
            <span className="text-slate-400 text-sm">Cámara {evento.camara}</span>
          </div>
          <button
            onClick={onCerrar}
            className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-700"
            aria-label="Cerrar modal"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Imagen */}
        <div className="flex-1 overflow-hidden bg-slate-900 min-h-0">
          {!imgError ? (
            <img
              src={evento.foto_url}
              alt={`Evento cámara ${evento.camara}`}
              className="w-full h-full object-contain max-h-[60vh]"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="w-full h-64 flex flex-col items-center justify-center text-slate-500 gap-3">
              <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <p>Imagen no disponible</p>
            </div>
          )}
        </div>

        {/* Detalles del evento */}
        <div className="px-5 py-4 border-t border-slate-700 grid grid-cols-2 gap-4">
          <div>
            <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">Fecha y Hora</p>
            <p className="text-slate-200 text-sm font-medium">{formatearFecha(evento.created_at)}</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">Cámara</p>
            <p className="text-slate-200 text-sm font-medium">Cámara {evento.camara}</p>
          </div>
          {evento.valor && evento.valor.trim() && (
            <div className="col-span-2">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">Placa Detectada</p>
              <span className="badge-placa text-base px-3 py-1">🔖 {evento.valor}</span>
            </div>
          )}
          {evento.foto_url && (
            <div className="col-span-2">
              <a
                href={evento.foto_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1 transition-colors"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                Abrir imagen original
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
