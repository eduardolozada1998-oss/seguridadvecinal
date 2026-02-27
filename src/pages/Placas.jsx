import { useState } from 'react'
import { usePlacas } from '../hooks/usePlacas'
import { SkeletonFila } from '../components/SkeletonCard'
import PhotoModal from '../components/PhotoModal'
import { formatearFecha } from '../components/EventoCard'

const IconOrden = ({ activo, asc }) => {
  if (!activo) return <span className="text-slate-600 ml-1">↕</span>
  return <span className="text-blue-400 ml-1">{asc ? '↑' : '↓'}</span>
}

export default function Placas() {
  const [busqueda, setBusqueda] = useState('')
  const [textoInput, setTextoInput] = useState('')
  const [eventoSeleccionado, setEventoSeleccionado] = useState(null)

  const { placas, cargando, error, ordenPor, ordenAsc, cambiarOrden, recargar } = usePlacas(busqueda)

  const manejarBusqueda = (e) => {
    e.preventDefault()
    setBusqueda(textoInput.trim())
  }

  const limpiarBusqueda = () => {
    setTextoInput('')
    setBusqueda('')
  }

  const thClase = (campo) =>
    `px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider cursor-pointer select-none hover:text-slate-200 transition-colors ${
      ordenPor === campo ? 'text-blue-400' : ''
    }`

  return (
    <div className="p-4 lg:p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Registro de Placas</h2>
          <p className="text-slate-400 text-sm">
            {!cargando && `${placas.length} registro${placas.length !== 1 ? 's' : ''} con placa detectada`}
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

      {/* Buscador */}
      <form onSubmit={manejarBusqueda} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={textoInput}
              onChange={e => setTextoInput(e.target.value.toUpperCase())}
              placeholder="Buscar placa ej. ABC-123"
              className="w-full bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-500 rounded-lg pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition-colors uppercase"
            />
          </div>
          <button type="submit" className="btn-primary px-5">
            Buscar
          </button>
          {busqueda && (
            <button type="button" onClick={limpiarBusqueda} className="btn-secondary px-4">
              Limpiar
            </button>
          )}
        </div>
        {busqueda && (
          <p className="text-slate-500 text-xs mt-2">
            Mostrando resultados para: <span className="text-yellow-400 font-medium">"{busqueda}"</span>
          </p>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-center">
          <p className="text-red-400 font-medium">Error al cargar registros</p>
          <p className="text-slate-400 text-xs mt-1">{error}</p>
          <button onClick={recargar} className="mt-3 btn-primary text-xs">Reintentar</button>
        </div>
      )}

      {/* Tabla */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Foto
                </th>
                <th className={thClase('valor')} onClick={() => cambiarOrden('valor')}>
                  Placa <IconOrden activo={ordenPor === 'valor'} asc={ordenAsc} />
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Cámara
                </th>
                <th className={thClase('created_at')} onClick={() => cambiarOrden('created_at')}>
                  Fecha y Hora <IconOrden activo={ordenPor === 'created_at'} asc={ordenAsc} />
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {cargando ? (
                Array.from({ length: 6 }).map((_, i) => <SkeletonFila key={i} />)
              ) : placas.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-16 text-center">
                    <p className="text-4xl mb-3">🔖</p>
                    <p className="text-slate-300 font-medium">
                      {busqueda ? `Sin resultados para "${busqueda}"` : 'Sin registros de placas'}
                    </p>
                    <p className="text-slate-500 text-sm mt-1">
                      {busqueda
                        ? 'Intenta con otro número de placa'
                        : 'Cuando EasyOCR detecte una placa, aparecerá aquí'}
                    </p>
                  </td>
                </tr>
              ) : (
                placas.map(evento => (
                  <tr
                    key={evento.id}
                    className="hover:bg-slate-700/30 transition-colors"
                  >
                    {/* Miniatura */}
                    <td className="px-4 py-3">
                      <div
                        className="w-14 h-10 rounded overflow-hidden bg-slate-700 cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all"
                        onClick={() => setEventoSeleccionado(evento)}
                      >
                        <img
                          src={evento.foto_url}
                          alt="Miniatura"
                          loading="lazy"
                          className="w-full h-full object-cover"
                          onError={e => { e.currentTarget.style.display = 'none' }}
                        />
                      </div>
                    </td>
                    {/* Placa */}
                    <td className="px-4 py-3">
                      <span className="badge-placa text-sm px-3 py-1">🔖 {evento.valor}</span>
                    </td>
                    {/* Cámara */}
                    <td className="px-4 py-3">
                      <span className="text-slate-300 text-sm bg-slate-700 px-2 py-0.5 rounded">
                        CAM {evento.camara}
                      </span>
                    </td>
                    {/* Fecha */}
                    <td className="px-4 py-3">
                      <span className="text-slate-300 text-sm">{formatearFecha(evento.created_at)}</span>
                    </td>
                    {/* Acciones */}
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setEventoSeleccionado(evento)}
                        className="text-blue-400 hover:text-blue-300 text-xs font-medium flex items-center gap-1 transition-colors bg-blue-500/10 hover:bg-blue-500/20 px-3 py-1.5 rounded-lg"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                        Ver foto
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

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
