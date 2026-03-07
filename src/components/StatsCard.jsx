/**
 * Tarjeta de estadísticas para el dashboard
 */
export default function StatsCard({ titulo, valor, icono, color = 'blue', subtitulo, cargando }) {
  const colores = {
    blue: 'border-blue-500/30 bg-blue-500/5',
    green: 'border-green-500/30 bg-green-500/5',
    yellow: 'border-yellow-500/30 bg-yellow-500/5',
    red: 'border-red-500/30 bg-red-500/5',
    slate: 'border-slate-600 bg-slate-700/30',
  }

  const coloresTexto = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
    slate: 'text-slate-300',
  }

  if (cargando) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 sm:p-5 animate-pulse">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <div className="h-3 bg-slate-700 rounded w-20" />
            <div className="h-7 bg-slate-700 rounded w-12" />
          </div>
          <div className="w-8 h-8 sm:w-10 sm:h-10 bg-slate-700 rounded-lg" />
        </div>
        <div className="h-2.5 bg-slate-700 rounded w-24 mt-2.5" />
      </div>
    )
  }

  return (
    <div className={`bg-slate-800 border rounded-xl p-3 sm:p-5 hover:shadow-lg transition-all duration-300 ${colores[color]}`}>
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0">
          <p className="text-slate-400 text-[10px] sm:text-xs font-medium uppercase tracking-wider truncate">{titulo}</p>
          <p className={`text-2xl sm:text-3xl font-bold mt-0.5 sm:mt-1 ${coloresTexto[color]}`}>{valor ?? '—'}</p>
        </div>
        {icono && (
          <div className="text-xl sm:text-2xl p-1.5 sm:p-2 rounded-lg bg-slate-700/50 flex-shrink-0">
            {icono}
          </div>
        )}
      </div>
      {subtitulo && (
        <p className="text-slate-500 text-[10px] sm:text-xs mt-1.5 sm:mt-2 truncate">{subtitulo}</p>
      )}
    </div>
  )
}
