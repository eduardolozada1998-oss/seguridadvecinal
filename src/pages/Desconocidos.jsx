import { useState, useEffect } from 'react'

const HF_URL = import.meta.env.VITE_HF_API_URL || ''

const IconEye = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7
         -1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
  </svg>
)

const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const IconTrash = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
)

const IconRefresh = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0
         0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
)

function ModalAprobar({ registro, onCerrar, onAprobado }) {
  const [nombre, setNombre] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

  const aprobar = async (e) => {
    e.preventDefault()
    if (!nombre.trim()) return
    setCargando(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('nombre', nombre.trim())
      const r = await fetch(`${HF_URL}/desconocidos/${registro.id}/aprobar`, {
        method: 'POST', body: fd,
      })
      const res = await r.json()
      if (res.ok) {
        onAprobado(nombre.trim())
      } else {
        setError(res.error || 'Error al aprobar')
      }
    } catch (err) {
      setError(`Error de red: ${err.message}`)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
         onClick={onCerrar}>
      <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-sm w-full space-y-4"
           onClick={e => e.stopPropagation()}>
        <h3 className="text-slate-100 font-bold text-lg">Registrar como conocido</h3>

        {/* Foto */}
        <div className="flex justify-center">
          <img
            src={registro.foto_url}
            alt="Rostro"
            className="w-32 h-32 object-cover rounded-xl border-2 border-slate-600"
            onError={e => { e.target.src = '' }}
          />
        </div>

        <p className="text-slate-400 text-xs text-center">
          Cámara {registro.camara} · {new Date(registro.created_at).toLocaleString('es-MX')}
        </p>

        <form onSubmit={aprobar} className="space-y-3">
          <div>
            <label className="text-slate-400 text-sm block mb-1">Nombre de la persona</label>
            <input
              autoFocus
              value={nombre}
              onChange={e => setNombre(e.target.value)}
              placeholder="Ej: Eduardo López"
              className="w-full bg-slate-900 text-slate-100 border border-slate-600 rounded-lg
                         px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition"
            />
          </div>

          {error && (
            <p className="text-red-400 text-xs">{error}</p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCerrar}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg py-2 text-sm transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!nombre.trim() || cargando}
              className="flex-1 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white
                         rounded-lg py-2 text-sm font-medium transition flex items-center justify-center gap-2"
            >
              {cargando ? (
                <span className="animate-spin">⏳</span>
              ) : (
                <><IconCheck /><span>Registrar</span></>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Desconocidos() {
  const [lista, setLista]       = useState([])
  const [cargando, setCargando] = useState(true)
  const [filtro, setFiltro]     = useState('pendientes') // 'pendientes' | 'todos'
  const [modal, setModal]       = useState(null)         // registro seleccionado
  const [toast, setToast]       = useState(null)

  const cargar = async () => {
    setCargando(true)
    try {
      const r = await fetch(`${HF_URL}/desconocidos?limit=100`)
      if (r.ok) setLista(await r.json())
    } catch { /* ignora */ }
    finally { setCargando(false) }
  }

  useEffect(() => { cargar() }, [])

  const mostrarToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const eliminar = async (id) => {
    if (!confirm('¿Descartar este rostro?')) return
    await fetch(`${HF_URL}/desconocidos/${id}`, { method: 'DELETE' })
    setLista(prev => prev.filter(r => r.id !== id))
    mostrarToast('Eliminado correctamente')
  }

  const onAprobado = (nombre) => {
    setModal(null)
    cargar()
    mostrarToast(`"${nombre}" registrado como conocido ✓`)
  }

  const visibles = filtro === 'pendientes'
    ? lista.filter(r => !r.aprobado)
    : lista

  const pendientes = lista.filter(r => !r.aprobado).length

  return (
    <div className="p-6 max-w-5xl space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg text-sm font-medium shadow-xl
          ${toast.ok ? 'bg-green-700 text-white' : 'bg-red-700 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <ModalAprobar
          registro={modal}
          onCerrar={() => setModal(null)}
          onAprobado={onAprobado}
        />
      )}

      {/* Cabecera */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
            Rostros Desconocidos
            {pendientes > 0 && (
              <span className="bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                {pendientes}
              </span>
            )}
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            El sistema captura automáticamente cada cara no reconocida.
            Aquí puedes registrarlos como conocidos o descartarlos.
          </p>
        </div>
        <button
          onClick={cargar}
          className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-slate-200
                     px-4 py-2 rounded-lg text-sm transition"
        >
          <IconRefresh /> Actualizar
        </button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2">
        {['pendientes', 'todos'].map(f => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition
              ${filtro === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
          >
            {f === 'pendientes' ? `Pendientes (${pendientes})` : `Todos (${lista.length})`}
          </button>
        ))}
      </div>

      {/* Grid */}
      {cargando ? (
        <div className="flex justify-center py-16">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
        </div>
      ) : visibles.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p className="text-4xl mb-3">👁</p>
          <p className="font-medium">
            {filtro === 'pendientes'
              ? 'No hay rostros desconocidos pendientes'
              : 'No se han capturado rostros aún'}
          </p>
          <p className="text-sm mt-1 text-slate-600">
            El sistema captura automáticamente cuando detecta una cara nueva
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {visibles.map(reg => (
            <div
              key={reg.id}
              className={`bg-slate-800 border rounded-xl overflow-hidden group transition
                ${reg.aprobado
                  ? 'border-green-700/40 opacity-60'
                  : 'border-slate-700 hover:border-slate-500'}`}
            >
              {/* Foto */}
              <div className="relative aspect-square bg-slate-900">
                {reg.foto_url ? (
                  <img
                    src={reg.foto_url}
                    alt="Desconocido"
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-4xl text-slate-600">
                    👤
                  </div>
                )}
                {reg.aprobado && (
                  <div className="absolute inset-0 bg-green-900/50 flex items-center justify-center">
                    <span className="text-green-300 text-xs font-bold bg-green-900/80 px-2 py-1 rounded">
                      ✓ {reg.nombre}
                    </span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="p-2 space-y-1">
                <div className="flex items-center gap-1 text-xs text-slate-400">
                  <span className="bg-slate-700 px-1.5 py-0.5 rounded text-slate-300">
                    Cam {reg.camara}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  {new Date(reg.created_at).toLocaleString('es-MX', {
                    month: 'short', day: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </p>

                {/* Acciones */}
                {!reg.aprobado && (
                  <div className="flex gap-1 pt-1">
                    <button
                      onClick={() => setModal(reg)}
                      title="Registrar como conocido"
                      className="flex-1 flex items-center justify-center gap-1 bg-green-700/80
                                 hover:bg-green-600 text-white text-xs py-1.5 rounded-lg transition"
                    >
                      <IconCheck /> <span className="hidden sm:inline">Registrar</span>
                    </button>
                    <button
                      onClick={() => eliminar(reg.id)}
                      title="Descartar"
                      className="bg-slate-700 hover:bg-red-700/80 text-slate-400 hover:text-white
                                 p-1.5 rounded-lg transition"
                    >
                      <IconTrash />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
