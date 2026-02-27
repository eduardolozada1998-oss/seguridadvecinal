/**
 * Barra de filtros para galería y placas
 */
export default function FiltrosBar({ filtros, onChange }) {
  const { tipo = 'todos', camara = 'todas', fecha = '' } = filtros

  const btnTipo = (valor, label) => (
    <button
      key={valor}
      onClick={() => onChange({ ...filtros, tipo: valor })}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${
        tipo === valor
          ? 'bg-blue-600 text-white'
          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Filtro tipo */}
      <div className="flex gap-2 flex-wrap">
        {btnTipo('todos', 'Todos')}
        {btnTipo('persona', '🚶 Personas')}
        {btnTipo('vehiculo', '🚗 Vehículos')}
      </div>

      {/* Filtro cámara */}
      <select
        value={camara}
        onChange={e => onChange({ ...filtros, camara: e.target.value })}
        className="bg-slate-700 border border-slate-600 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"
      >
        <option value="todas">Todas las cámaras</option>
        <option value="01">Cámara 01</option>
        <option value="02">Cámara 02</option>
        <option value="03">Cámara 03</option>
        <option value="04">Cámara 04</option>
      </select>

      {/* Filtro fecha */}
      <input
        type="date"
        value={fecha}
        onChange={e => onChange({ ...filtros, fecha: e.target.value })}
        className="bg-slate-700 border border-slate-600 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"
        style={{ colorScheme: 'dark' }}
      />

      {/* Botón limpiar filtros */}
      {(tipo !== 'todos' || camara !== 'todas' || fecha) && (
        <button
          onClick={() => onChange({ tipo: 'todos', camara: 'todas', fecha: '' })}
          className="px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Limpiar
        </button>
      )}
    </div>
  )
}
