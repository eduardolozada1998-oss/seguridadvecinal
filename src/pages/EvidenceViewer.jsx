/**
 * EvidenceViewer — Vista forense de una sesión de detección
 * Muestra evidencia, metadata y hash SHA-256 para cadena de custodia.
 * Se usa como modal o página independiente pasando sessionId o alertId por query param.
 */
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

const HF_URL = import.meta.env.VITE_HF_API_URL || ''

const NIVELES = {
  red:    { label: 'CRÍTICO',   color: 'text-red-400',    bg: 'bg-red-500/20',    border: 'border-red-500/50' },
  orange: { label: 'ALERTA',    color: 'text-orange-400', bg: 'bg-orange-500/20', border: 'border-orange-500/50' },
  yellow: { label: 'ATENCIÓN',  color: 'text-yellow-400', bg: 'bg-yellow-500/20', border: 'border-yellow-500/50' },
  green:  { label: 'MONITOREO', color: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/30' },
}

function formatFecha(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'long', timeStyle: 'medium' })
}

function MetaRow({ label, value, mono }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between gap-1 py-2.5 border-b border-slate-700/50">
      <span className="text-slate-500 text-xs uppercase tracking-wide flex-shrink-0">{label}</span>
      <span className={`text-slate-200 text-sm text-right break-all ${mono ? 'font-mono text-xs text-slate-400' : ''}`}>
        {value}
      </span>
    </div>
  )
}

export default function EvidenceViewer() {
  const [searchParams] = useSearchParams()
  const alertId  = searchParams.get('alertId')

  const [alert,   setAlert]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [copied,  setCopied]  = useState(false)
  const [downloaded, setDownloaded] = useState(false)

  useEffect(() => {
    if (!HF_URL || !alertId) { setLoading(false); return }
    fetch(`${HF_URL}/alerts?status=all&limit=100`)
      .then(r => r.json())
      .then(data => {
        const found = Array.isArray(data) ? data.find(a => a.id === alertId) : null
        setAlert(found || null)
        if (!found) setError('Alerta no encontrada')
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [alertId])

  const handleCopyHash = () => {
    if (!alert?.evidence_hash) return
    navigator.clipboard.writeText(alert.evidence_hash)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownloadJson = () => {
    if (!alert) return
    const blob = new Blob([JSON.stringify(alert, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `evidencia_${alert.id?.slice(0, 8)}_cam${alert.camera_id}.json`
    a.click()
    URL.revokeObjectURL(url)
    setDownloaded(true)
    setTimeout(() => setDownloaded(false), 2000)
  }

  // ── Sin alertId en URL ────────────────────────────────────────────────────
  if (!alertId) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-2">🔍 Visor de Evidencia</h1>
        <p className="text-slate-400 text-sm mb-6">
          Accede a una alerta específica desde el{' '}
          <a href="/alertas" className="text-blue-400 hover:underline">Centro de Alertas</a>,
          expande la tarjeta y haz clic en «Ver evidencia».
        </p>
        <div className="bg-slate-800/60 rounded-xl p-8 text-center">
          <div className="text-5xl mb-3">📂</div>
          <p className="text-slate-500 text-sm">Ninguna alerta seleccionada</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-10 bg-slate-800/60 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (error || !alert) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="bg-red-900/30 border border-red-500/40 rounded-xl p-4 text-red-300 text-sm">
          {error || 'Alerta no encontrada'}
        </div>
      </div>
    )
  }

  const n = NIVELES[alert.threat_level] || NIVELES.green

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${n.bg} ${n.border} border ${n.color}`}>
            {n.label} — Score {alert.threat_score}
          </span>
          {alert.acknowledged && (
            <span className="text-xs bg-slate-700 text-slate-400 px-2.5 py-1 rounded-full">✓ Atendida</span>
          )}
        </div>
        <h1 className="text-xl font-bold text-white mt-2">
          Evidencia forense · Cam {alert.camera_id}
        </h1>
        <p className="text-slate-400 text-sm">{formatFecha(alert.triggered_at)}</p>
      </div>

      {/* Imagen de evidencia */}
      {alert.foto_url && (
        <div className={`rounded-xl overflow-hidden border ${n.border}`}>
          <img
            src={alert.foto_url}
            alt="Evidencia"
            className="w-full object-contain bg-slate-900 max-h-72"
          />
          <div className="px-3 py-2 bg-slate-800/60 flex justify-between items-center">
            <span className="text-xs text-slate-500">Snapshot del evento</span>
            <a
              href={alert.foto_url}
              download
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              ↓ Descargar imagen
            </a>
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="bg-slate-800/60 rounded-xl p-4 space-y-0">
        <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-2">Metadata del evento</h2>
        <MetaRow label="ID de alerta"     value={alert.id}            mono />
        <MetaRow label="ID de sesión"     value={alert.session_id}    mono />
        <MetaRow label="Cámara"           value={`Cam ${alert.camera_id}`} />
        <MetaRow label="Tipo"             value={alert.tipo} />
        <MetaRow label="Identidad"        value={alert.identity_name || '—'} />
        <MetaRow label="Razón"            value={alert.reason?.replace(/_/g, ' ')} />
        <MetaRow label="Score de amenaza" value={`${alert.threat_score} / 100 (${n.label})`} />
        <MetaRow label="Detectado"        value={formatFecha(alert.triggered_at)} />
        {alert.acknowledged && <>
          <MetaRow label="Atendida"         value={formatFecha(alert.acknowledged_at)} />
          <MetaRow label="Atendida por"     value={alert.acknowledged_by} />
        </>}
      </div>

      {/* Hash SHA-256 */}
      {alert.evidence_hash && (
        <div className="bg-slate-800/60 rounded-xl p-4">
          <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-2">
            Cadena de custodia · SHA-256
          </h2>
          <div className="font-mono text-xs text-slate-400 break-all bg-slate-900/60 rounded-lg p-3">
            {alert.evidence_hash}
          </div>
          <p className="text-xs text-slate-600 mt-2">
            Este hash permite verificar la integridad de la imagen. Si el hash del archivo
            descargado no coincide, la evidencia fue alterada.
          </p>
          <button
            onClick={handleCopyHash}
            className="mt-2 text-xs text-blue-400 hover:text-blue-300"
          >
            {copied ? '✓ Copiado' : '📋 Copiar hash'}
          </button>
        </div>
      )}

      {/* Acciones */}
      <div className="flex gap-3">
        <button
          onClick={handleDownloadJson}
          className="flex-1 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-white text-sm
            font-medium transition-colors flex items-center justify-center gap-2"
        >
          {downloaded ? '✓ Descargado' : '⬇ Exportar JSON'}
        </button>
        <a
          href="/alertas"
          className="flex-1 py-3 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 text-sm
            font-medium transition-colors flex items-center justify-center gap-2 border border-blue-600/30"
        >
          ← Volver a alertas
        </a>
      </div>
    </div>
  )
}
