import { useState, useEffect } from 'react'
import { useEventos } from '../hooks/useEventos'
import { useSearchParams } from 'react-router-dom'
import EventoCard from '../components/EventoCard'
import SkeletonCard from '../components/SkeletonCard'
import FiltrosBar from '../components/FiltrosBar'
import PhotoModal from '../components/PhotoModal'

export default function Galeria() {
  const [searchParams] = useSearchParams()
  const camaraInicial = searchParams.get('camara') || 'todas'

  const [filtros, setFiltros] = useState({ tipo: 'todos', camara: camaraInicial, fecha: '' })
  const [eventoSeleccionado, setEventoSeleccionado] = useState(null)

  // Si cambia el query param (ej. navegar desde Cámaras), actualizar filtro
  useEffect(() => {
    const camara = searchParams.get('camara') || 'todas'
    setFiltros(prev => ({ ...prev, camara }))
  }, [searchParams])

  const { eventos, cargando, error, cargarMas, hayMas, totalDisponible, recargar } = useEventos({
    tipo: filtros.tipo,
    camara: filtros.camara,
    fecha: filtros.fecha,
    limite: 20,
  })

  const manejarCambioFiltro = (nuevosFiltros) => {
    setFiltros(nuevosFiltros)
  }

  return (
    <div className="p-4 lg:p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Galería de Eventos</h2>
          <p className="text-slate-400 text-sm">
            {!cargando && `${totalDisponible.toLocaleString('es-MX')} eventos encontrados`}
          </p>
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

      {/* Barra de filtros */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <FiltrosBar filtros={filtros} onChange={manejarCambioFiltro} />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
          <span className="text-red-400">⚠️</span>
          <div>
            <p className="text-red-400 font-medium text-sm">Error al cargar imágenes</p>
            <p className="text-slate-400 text-xs">{error}</p>
          </div>
          <button onClick={recargar} className="ml-auto btn-primary text-xs py-1.5">Reintentar</button>
        </div>
      )}

      {/* Grid de eventos */}
      {cargando && eventos.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : eventos.length === 0 ? (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-14 text-center">
          <p className="text-5xl mb-4">📷</p>
          <p className="text-slate-300 font-semibold text-lg">Sin eventos para mostrar</p>
          <p className="text-slate-500 text-sm mt-2">
            {filtros.tipo !== 'todos' || filtros.camara !== 'todas' || filtros.fecha
              ? 'Prueba ajustando los filtros de búsqueda'
              : 'Aún no se han registrado eventos en el sistema'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {eventos.map(evento => (
            <EventoCard
              key={evento.id}
              evento={evento}
              onClick={setEventoSeleccionado}
            />
          ))}
        </div>
      )}

      {/* Botón cargar más */}
      {hayMas && !error && (
        <div className="flex justify-center pt-2">
          <button
            onClick={cargarMas}
            disabled={cargando}
            className="btn-secondary flex items-center gap-2 min-w-40 justify-center"
          >
            {cargando ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Cargando...
              </>
            ) : (
              <>
                Cargar más
                <span className="text-slate-500 text-xs">({totalDisponible - eventos.length} restantes)</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Modal foto */}
      {eventoSeleccionado && (
        <PhotoModal
          evento={eventoSeleccionado}
          onCerrar={() => setEventoSeleccionado(null)}
        />
      )}
    </div>
  )
}
