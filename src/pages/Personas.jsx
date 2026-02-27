import { useState, useEffect, useRef } from 'react'

const HF_URL = import.meta.env.VITE_HF_API_URL || ''

const IconUsuario = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
)

const IconTrash = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
)

export default function Personas() {
  const [personas, setPersonas]     = useState([])
  const [cargando, setCargando]     = useState(true)
  const [nombre, setNombre]         = useState('')
  const [fotoFile, setFotoFile]     = useState(null)
  const [preview, setPreview]       = useState(null)
  const [enviando, setEnviando]     = useState(false)
  const [mensaje, setMensaje]       = useState(null)  // {ok, texto}
  const inputRef                    = useRef(null)

  const cargar = async () => {
    setCargando(true)
    try {
      const r = await fetch(`${HF_URL}/personas`)
      if (r.ok) setPersonas(await r.json())
    } catch { /* ignora */ }
    finally { setCargando(false) }
  }

  useEffect(() => { cargar() }, [])

  const manejarFoto = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFotoFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const registrar = async (e) => {
    e.preventDefault()
    if (!nombre.trim() || !fotoFile) return
    setEnviando(true)
    setMensaje(null)
    try {
      const fd = new FormData()
      fd.append('nombre', nombre.trim())
      fd.append('foto', fotoFile)
      const r   = await fetch(`${HF_URL}/registrar-persona`, { method: 'POST', body: fd })
      const res = await r.json()
      if (res.ok) {
        setMensaje({ ok: true, texto: `"${res.nombre}" registrado correctamente.` })
        setNombre('')
        setFotoFile(null)
        setPreview(null)
        if (inputRef.current) inputRef.current.value = ''
        cargar()
      } else {
        setMensaje({ ok: false, texto: res.error || 'Error al registrar.' })
      }
    } catch (err) {
      setMensaje({ ok: false, texto: `Error de red: ${err.message}` })
    } finally {
      setEnviando(false)
    }
  }

  const eliminar = async (nom) => {
    if (!confirm(`¿Eliminar a "${nom}" del registro?`)) return
    await fetch(`${HF_URL}/personas/${encodeURIComponent(nom)}`, { method: 'DELETE' })
    cargar()
  }

  const noDisponible = !HF_URL

  return (
    <div className="p-6 max-w-3xl space-y-8">
      {/* Cabecera */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Reconocimiento Facial</h1>
        <p className="text-slate-400 text-sm mt-1">
          Registra personas conocidas (vecinos, familia). El sistema las identificará
          y solo te alertará cuando detecte rostros desconocidos entre las 10 pm y las 6 am.
        </p>
      </div>

      {noDisponible && (
        <div className="bg-yellow-900/30 border border-yellow-600/40 text-yellow-300 text-sm px-4 py-3 rounded-lg">
          <strong>VITE_HF_API_URL</strong> no está configurado. El reconocimiento facial
          no estará disponible hasta que redeploys con esa variable.
        </div>
      )}

      {/* Formulario registro */}
      <form onSubmit={registrar}
        className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-4">
        <h2 className="text-slate-100 font-semibold text-lg flex items-center gap-2">
          <IconUsuario /> Registrar persona
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Nombre */}
          <div className="space-y-1">
            <label className="text-slate-400 text-sm">Nombre completo</label>
            <input
              value={nombre}
              onChange={e => setNombre(e.target.value)}
              placeholder="Ej: Eduardo López"
              className="w-full bg-slate-900 text-slate-100 border border-slate-600 rounded-lg
                         px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition"
            />
          </div>

          {/* Foto */}
          <div className="space-y-1">
            <label className="text-slate-400 text-sm">Foto con cara visible</label>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              onChange={manejarFoto}
              className="w-full text-sm text-slate-400 file:mr-3 file:py-1.5 file:px-3
                         file:rounded-lg file:border-0 file:text-sm file:font-medium
                         file:bg-blue-600 file:text-white hover:file:bg-blue-500
                         file:cursor-pointer cursor-pointer"
            />
          </div>
        </div>

        {/* Preview */}
        {preview && (
          <div className="flex items-center gap-4">
            <img src={preview} alt="preview"
              className="w-24 h-24 object-cover rounded-lg border border-slate-600" />
            <p className="text-slate-400 text-sm">Vista previa de la foto seleccionada</p>
          </div>
        )}

        {/* Mensaje */}
        {mensaje && (
          <div className={`text-sm px-3 py-2 rounded-lg ${
            mensaje.ok
              ? 'bg-green-900/30 text-green-300 border border-green-600/40'
              : 'bg-red-900/30 text-red-300 border border-red-600/40'
          }`}>
            {mensaje.texto}
          </div>
        )}

        <button
          type="submit"
          disabled={enviando || !nombre.trim() || !fotoFile || noDisponible}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed
                     text-white px-5 py-2 rounded-lg text-sm font-medium transition"
        >
          {enviando ? 'Registrando…' : 'Registrar persona'}
        </button>
      </form>

      {/* Lista de personas */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-slate-100 font-semibold text-lg">
            Personas registradas
            <span className="ml-2 text-sm text-slate-400 font-normal">({personas.length})</span>
          </h2>
          <button onClick={cargar}
            className="text-slate-400 hover:text-slate-200 text-sm transition">
            ↺ Actualizar
          </button>
        </div>

        {cargando ? (
          <div className="space-y-2">
            {[1,2,3].map(i => (
              <div key={i} className="h-14 bg-slate-700/40 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : personas.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            <div className="text-4xl mb-2">👤</div>
            <p>Sin personas registradas aún.</p>
            <p className="text-xs mt-1">Todos los rostros detectados apareceran como "Desconocido".</p>
          </div>
        ) : (
          <div className="space-y-2">
            {personas.map((p) => (
              <div key={p.nombre}
                className="flex items-center gap-4 bg-slate-700/40 rounded-lg px-4 py-3">
                {p.foto_url ? (
                  <img src={p.foto_url} alt={p.nombre}
                    className="w-10 h-10 rounded-full object-cover border border-slate-600 flex-shrink-0" />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-slate-600 flex items-center justify-center
                                  text-slate-300 flex-shrink-0 font-bold text-sm">
                    {p.nombre[0]?.toUpperCase()}
                  </div>
                )}
                <span className="text-slate-100 text-sm font-medium flex-1">{p.nombre}</span>
                <span className="inline-flex items-center gap-1 text-xs bg-green-900/40
                                 text-green-400 border border-green-600/30 rounded-full px-2 py-0.5">
                  Conocido
                </span>
                <button onClick={() => eliminar(p.nombre)}
                  className="text-slate-500 hover:text-red-400 transition p-1 rounded">
                  <IconTrash />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
