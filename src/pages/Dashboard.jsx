import { useState, useEffect } from 'react'
import { useEstadisticas } from '../hooks/useEstadisticas'
import StatsCard from '../components/StatsCard'
import EventoCard from '../components/EventoCard'
import PhotoModal from '../components/PhotoModal'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

/**
 * Tooltip personalizado para la gráfica de recharts
 */
const TooltipPersonalizado = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm shadow-lg">
      <p className="text-slate-300 font-medium mb-1">{label}</p>
      {payload.map(entry => (
        <p key={entry.dataKey} style={{ color: entry.color }} className="text-xs">
          {entry.name}: <span className="font-bold">{entry.value}</span>
        </p>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { stats, grafica, ultimosEventos, cargando, error, recargar } = useEstadisticas()
  const [horaActual, setHoraActual] = useState(new Date())
  const [eventoSeleccionado, setEventoSeleccionado] = useState(null)

  // Reloj en tiempo real
  useEffect(() => {
    const timer = setInterval(() => setHoraActual(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatHora = (fecha) =>
    fecha.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const formatFecha = (fecha) =>
    fecha.toLocaleDateString('es-MX', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <p className="text-red-400 font-medium">Error al cargar datos</p>
          <p className="text-slate-400 text-sm mt-1">{error}</p>
          <button onClick={recargar} className="mt-4 btn-primary">Reintentar</button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-6 space-y-6">
      {/* ──── HEADER ──── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Dashboard</h2>
          <p className="text-slate-400 text-sm capitalize">{formatFecha(horaActual)}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-3xl font-mono font-bold text-blue-400">{formatHora(horaActual)}</p>
          </div>
          <button
            onClick={recargar}
            disabled={cargando}
            className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors disabled:opacity-50"
            aria-label="Recargar datos"
          >
            <svg className={`w-4 h-4 ${cargando ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* ──── STATS DEL DÍA ──── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          titulo="Total hoy"
          valor={stats.totalHoy}
          icono="📊"
          color="blue"
          subtitulo="Eventos registrados"
          cargando={cargando}
        />
        <StatsCard
          titulo="Personas"
          valor={stats.personasHoy}
          icono="🚶"
          color="blue"
          subtitulo="Detectadas hoy"
          cargando={cargando}
        />
        <StatsCard
          titulo="Vehículos"
          valor={stats.vehiculosHoy}
          icono="🚗"
          color="green"
          subtitulo="Detectados hoy"
          cargando={cargando}
        />
        <StatsCard
          titulo="Placas leídas"
          valor={stats.placasHoy}
          icono="🔖"
          color="yellow"
          subtitulo="Con lectura OCR"
          cargando={cargando}
        />
      </div>

      {/* ──── GRÁFICA DE BARRAS ──── */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
        <h3 className="text-slate-200 font-semibold mb-4">Actividad por hora — últimas 24 horas</h3>
        {cargando ? (
          <div className="h-56 bg-slate-700 rounded animate-pulse" />
        ) : grafica.length > 0 ? (
          <ResponsiveContainer width="100%" height={224}>
            <BarChart data={grafica} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis
                dataKey="hora"
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                interval={2}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<TooltipPersonalizado />} cursor={{ fill: 'rgba(148,163,184,0.05)' }} />
              <Legend
                wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
                formatter={(value) => value === 'personas' ? '🚶 Personas' : '🚗 Vehículos'}
              />
              <Bar dataKey="personas" stackId="a" fill="#3b82f6" radius={[0, 0, 0, 0]} name="personas" />
              <Bar dataKey="vehiculos" stackId="a" fill="#22c55e" radius={[4, 4, 0, 0]} name="vehiculos" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-56 flex items-center justify-center text-slate-500">
            <div className="text-center">
              <p className="text-4xl mb-2">📭</p>
              <p>Sin actividad en las últimas 24 horas</p>
            </div>
          </div>
        )}
      </div>

      {/* ──── ÚLTIMOS 6 EVENTOS ──── */}
      <div>
        <h3 className="text-slate-200 font-semibold mb-4">Últimos eventos</h3>
        {cargando ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="animate-pulse bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
                <div className="aspect-video bg-slate-700" />
                <div className="p-3 space-y-2">
                  <div className="h-3 bg-slate-700 rounded w-3/4" />
                  <div className="h-3 bg-slate-700 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : ultimosEventos.length === 0 ? (
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-10 text-center">
            <p className="text-4xl mb-3">🛡️</p>
            <p className="text-slate-300 font-medium">Sin eventos registrados</p>
            <p className="text-slate-500 text-sm mt-1">El sistema está monitoreando activamente</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {ultimosEventos.map(evento => (
              <EventoCard
                key={evento.id}
                evento={evento}
                onClick={setEventoSeleccionado}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modal detalle */}
      {eventoSeleccionado && (
        <PhotoModal
          evento={eventoSeleccionado}
          onCerrar={() => setEventoSeleccionado(null)}
        />
      )}

      {/* Indicador auto-refresh */}
      <div className="flex items-center justify-end gap-2 text-slate-500 text-xs">
        <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        <span>Actualización automática cada 30 segundos</span>
      </div>
    </div>
  )
}
