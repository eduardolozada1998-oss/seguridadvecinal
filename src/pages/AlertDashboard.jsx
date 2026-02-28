import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

const HF_URL = import.meta.env.VITE_HF_API_URL || ''

// ─── Colores y etiquetas por nivel de amenaza ────────────────────────────────
const NIVELES = {
  red:    { label: 'CRÍTICO',   bg: 'bg-red-500/20',    border: 'border-red-500/50',    text: 'text-red-400',    dot: 'bg-red-500',    badge: 'bg-red-500/30 text-red-300' },
  orange: { label: 'ALERTA',    bg: 'bg-orange-500/20', border: 'border-orange-500/50', text: 'text-orange-400', dot: 'bg-orange-500', badge: 'bg-orange-500/30 text-orange-300' },
  yellow: { label: 'ATENCIÓN',  bg: 'bg-yellow-500/20', border: 'border-yellow-500/50', text: 'text-yellow-400', dot: 'bg-yellow-500', badge: 'bg-yellow-500/30 text-yellow-300' },
  green:  { label: 'MONITOREO', bg: 'bg-green-500/10',  border: 'border-green-500/30',  text: 'text-green-400',  dot: 'bg-green-500',  badge: 'bg-green-500/20 text-green-300' },
}

const TIPO_ICONS = {
  persona:   '🧑',
  vehiculo:  '🚗',
  movimiento:'💨',
}

function ThreatBadge({ score, level }) {
  const n = NIVELES[level] || NIVELES.green
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${n.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${n.dot} animate-pulse`} />
      {score} · {n.label}
    </div>
  )
}

function formatFecha(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'medium' })
}

function formatRazon(r) {
  if (!r) return ''
  return r
    .replace(/_/g, ' ')
    .replace('rostro desconocido', '👤 Rostro desconocido')
    .replace('vehiculo detectado', '🚗 Vehículo detectado')
    .replace('sin placa', '🚫 Sin placa')
    .replace('horario nocturno', '🌙 Horario nocturno')
    .replace('movimiento', '💨 Movimiento')
    .replace('multiples personas', '👥 Múltiples personas')
    .replace('[ESCALADA]', '⚠️ ESCALADA')
}

// ─── Barra de stats resumidas ────────────────────────────────────────────────
function StatsBar({ stats, onFiltroNivel }) {
  const items = [
    { key: 'red',    icon: '🔴', label: 'Críticos' },
    { key: 'orange', icon: '🟠', label: 'Alertas' },
    { key: 'yellow', icon: '🟡', label: 'Atención' },
    { key: 'green',  icon: '🟢', label: 'Monitoreo' },
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {items.map(({ key, icon, label }) => (
        <button
          key={key}
          onClick={() => onFiltroNivel(key)}
          className={`${NIVELES[key].bg} ${NIVELES[key].border} border rounded-xl p-3 text-center
            hover:scale-[1.02] transition-transform cursor-pointer`}
        >
          <div className={`text-2xl font-bold ${NIVELES[key].text}`}>{stats[key] ?? 0}</div>
          <div className="text-xs text-slate-400 mt-0.5">{icon} {label}</div>
        </button>
      ))}
    </div>
  )
}

// ─── Tarjeta de alerta individual ────────────────────────────────────────────
function AlertCard({ alert, onAcknowledge }) {
  const [expanded, setExpanded]   = useState(false)
  const [imgError, setImgError]   = useState(false)
  const n = NIVELES[alert.threat_level] || NIVELES.green
  return (
    <div className={`${n.bg} ${n.border} border rounded-xl overflow-hidden
      transition-all duration-200 ${alert.acknowledged ? 'opacity-50' : ''}`}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer select-none"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Foto miniatura */}
        <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-slate-700">
          {alert.foto_url && !imgError ? (
            <img
              src={alert.foto_url}
              alt="evidencia"
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-2xl">
              {TIPO_ICONS[alert.tipo] || '📷'}
            </div>
          )}
        </div>

        {/* Info principal */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <ThreatBadge score={alert.threat_score} level={alert.threat_level} />
            {alert.acknowledged && (
              <span className="text-xs bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full">✓ Atendida</span>
            )}
          </div>
          <p className="text-white font-medium mt-1 truncate">
            {alert.identity_name || alert.tipo || 'Detección'}
            <span className="text-slate-400 text-sm font-normal ml-2">· Cam {alert.camera_id}</span>
          </p>
          <p className="text-xs text-slate-400 mt-0.5">{formatFecha(alert.triggered_at)}</p>
        </div>

        {/* Expand chevron */}
        <svg
          className={`w-4 h-4 text-slate-500 flex-shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Detalle expandido */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/10 pt-3">
          {/* Imagen grande */}
          {alert.foto_url && !imgError && (
            <img
              src={alert.foto_url}
              alt="evidencia"
              className="w-full max-h-64 object-contain rounded-lg bg-slate-800"
            />
          )}

          {/* Razón */}
          <div className="text-sm text-slate-300">
            <span className="text-slate-500 text-xs uppercase tracking-wide">Razón</span>
            <br />
            {formatRazon(alert.reason)}
          </div>

          {/* Hash forense */}
          {alert.evidence_hash && (
            <div className="text-xs">
              <span className="text-slate-500 uppercase tracking-wide">SHA-256 (cadena de custodia)</span>
              <div className="font-mono text-slate-400 break-all mt-0.5 bg-slate-800/60 rounded p-2">
                {alert.evidence_hash}
              </div>
            </div>
          )}

          {/* Botón acknowledger */}
          {!alert.acknowledged && (
            <button
              onClick={(e) => { e.stopPropagation(); onAcknowledge(alert.id) }}
              className="w-full py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm
                font-medium transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Marcar como atendida
            </button>
          )}
          {alert.acknowledged && alert.acknowledged_by && (
            <p className="text-xs text-slate-500 text-center">
              ✓ Atendida por: {alert.acknowledged_by} · {formatFecha(alert.acknowledged_at)}
            </p>
          )}

          {/* Enlace a evidencia forense */}
          <a
            href={`/evidencia?alertId=${alert.id}`}
            className="block text-center text-xs text-blue-400 hover:text-blue-300 mt-1"
            onClick={e => e.stopPropagation()}
          >
            🔍 Ver evidencia forense completa →
          </a>
        </div>
      )}
    </div>
  )
}

// ─── Panel principal ─────────────────────────────────────────────────────────
export default function AlertDashboard() {
  const [alerts,      setAlerts]      = useState([])
  const [stats,       setStats]       = useState({})
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [filtroStatus, setFiltroStatus] = useState('active')  // all | active | acknowledged
  const [filtroNivel,  setFiltroNivel]  = useState('')         // '' | red | orange | yellow | green
  const [filtroCam,    setFiltroCam]    = useState('')
  const [minScore,     setMinScore]     = useState(0)
  const [ackAll,       setAckAll]       = useState(false)

  const fetchAlerts = useCallback(async () => {
    if (!HF_URL) { setError('VITE_HF_API_URL no configurado'); setLoading(false); return }
    try {
      const params = new URLSearchParams({ status: filtroStatus, min_threat: minScore, limit: 60 })
      if (filtroCam) params.set('camera_id', filtroCam)
      const res = await fetch(`${HF_URL}/alerts?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      let data = await res.json()
      // Filtro de nivel en frontend cuando se selecciona un nivel específico
      if (filtroNivel) data = data.filter(a => a.threat_level === filtroNivel)
      setAlerts(data)
      setError('')
    } catch (e) {
      setError(`Error al cargar alertas: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [filtroStatus, filtroNivel, filtroCam, minScore])

  const fetchStats = useCallback(async () => {
    if (!HF_URL) return
    try {
      const res = await fetch(`${HF_URL}/alerts/stats`)
      if (res.ok) setStats(await res.json())
    } catch (_) {}
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchAlerts()
    fetchStats()
  }, [fetchAlerts, fetchStats])

  // Auto-refresh cada 15 segundos
  useEffect(() => {
    const id = setInterval(() => { fetchAlerts(); fetchStats() }, 15000)
    return () => clearInterval(id)
  }, [fetchAlerts, fetchStats])

  const handleAcknowledge = async (alertId) => {
    try {
      const fd = new FormData()
      fd.append('operator', 'operador')
      await fetch(`${HF_URL}/alerts/${alertId}/acknowledge`, { method: 'POST', body: fd })
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a))
      fetchStats()
    } catch (e) {
      console.error(e)
    }
  }

  const handleAcknowledgeAll = async () => {
    if (!window.confirm('¿Marcar todas las alertas pendientes como atendidas?')) return
    setAckAll(true)
    try {
      const fd = new FormData()
      fd.append('operator', 'operador')
      await fetch(`${HF_URL}/alerts/acknowledge-all`, { method: 'POST', body: fd })
      fetchAlerts()
      fetchStats()
    } catch (e) {
      console.error(e)
    } finally {
      setAckAll(false)
    }
  }

  const handleFiltroNivel = (nivel) => {
    setFiltroNivel(prev => prev === nivel ? '' : nivel)
    setFiltroStatus('all')
  }

  const pendientes = alerts.filter(a => !a.acknowledged).length
  const camaras    = [...new Set(alerts.map(a => a.camera_id).filter(Boolean))].sort()

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span>🛡️</span> Centro de Alertas
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {stats.pending ?? 0} pendientes · actualización automática cada 15 s
          </p>
        </div>
        {pendientes > 0 && (
          <button
            onClick={handleAcknowledgeAll}
            disabled={ackAll}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600
              text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {ackAll ? '…' : '✓ Atender todas'}
          </button>
        )}
      </div>

      {/* ── Stats por nivel ── */}
      <StatsBar stats={stats} onFiltroNivel={handleFiltroNivel} />

      {/* ── Filtros ── */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* Status */}
        {['active', 'all', 'acknowledged'].map(s => (
          <button
            key={s}
            onClick={() => { setFiltroStatus(s); setFiltroNivel('') }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filtroStatus === s && !filtroNivel
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700/60 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {{ active: '⏰ Pendientes', all: '📋 Todas', acknowledged: '✓ Atendidas' }[s]}
          </button>
        ))}

        {/* Cámara */}
        {camaras.length > 0 && (
          <select
            value={filtroCam}
            onChange={e => setFiltroCam(e.target.value)}
            className="px-3 py-1.5 rounded-lg text-sm bg-slate-700 text-slate-300 border-none outline-none"
          >
            <option value="">📹 Todas las cámaras</option>
            {camaras.map(c => <option key={c} value={c}>Cam {c}</option>)}
          </select>
        )}

        {/* Score mínimo */}
        <label className="flex items-center gap-2 text-sm text-slate-400">
          Score ≥
          <input
            type="range" min={0} max={75} step={25} value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="w-20 accent-blue-500"
          />
          <span className="text-white font-medium w-5">{minScore}</span>
        </label>

        {/* Nivel activo */}
        {filtroNivel && (
          <button
            onClick={() => setFiltroNivel('')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium ${NIVELES[filtroNivel].badge}
              flex items-center gap-1`}
          >
            {NIVELES[filtroNivel].label} ✕
          </button>
        )}

        {/* Refresh manual */}
        <button
          onClick={() => { setLoading(true); fetchAlerts(); fetchStats() }}
          className="ml-auto p-2 rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300"
          title="Refrescar"
        >
          <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none"
            stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0
                 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bg-red-900/30 border border-red-500/40 rounded-xl p-4 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* ── Sin HF_URL ── */}
      {!HF_URL && (
        <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-xl p-4 text-yellow-300 text-sm">
          Configura <strong>VITE_HF_API_URL</strong> en tu archivo <code>.env</code> para
          conectar con el backend.
        </div>
      )}

      {/* ── Lista de alertas ── */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-slate-800/60 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <div className="text-5xl mb-3">🛡️</div>
          <p className="text-lg font-medium text-slate-400">Sin alertas</p>
          <p className="text-sm mt-1">
            {filtroStatus === 'active' ? 'No hay alertas pendientes — sistema tranquilo' : 'No hay alertas con los filtros actuales'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onAcknowledge={handleAcknowledge}
            />
          ))}
          <p className="text-center text-xs text-slate-600 pt-2">
            Mostrando {alerts.length} alerta{alerts.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
