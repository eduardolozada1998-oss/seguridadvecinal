import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

// Iconos SVG inline para no depender de librerías externas
const IconDashboard = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
)

const IconGaleria = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
)

const IconPlacas = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
  </svg>
)

const IconCamaras = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
)

const IconMenu = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
  </svg>
)

const IconShield = () => (
  <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" />
  </svg>
)

const navLinks = [
  { to: '/', label: 'Dashboard', Icon: IconDashboard, end: true },
  { to: '/galeria', label: 'Galería', Icon: IconGaleria },
  { to: '/placas', label: 'Placas', Icon: IconPlacas },
  { to: '/camaras', label: 'Cámaras', Icon: IconCamaras },
]

export default function Layout() {
  const [sidebarAbierto, setSidebarAbierto] = useState(false)

  const claseNavLink = ({ isActive }) =>
    `flex items-center gap-3 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-200 ${
      isActive
        ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
        : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-200'
    }`

  return (
    <div className="min-h-screen bg-slate-900 flex">
      {/* ──── OVERLAY móvil ──── */}
      {sidebarAbierto && (
        <div
          className="fixed inset-0 bg-black/60 z-20 lg:hidden"
          onClick={() => setSidebarAbierto(false)}
        />
      )}

      {/* ──── SIDEBAR ──── */}
      <aside
        className={`
          fixed top-0 left-0 h-full w-64 bg-slate-800 border-r border-slate-700 z-30
          flex flex-col transition-transform duration-300
          ${sidebarAbierto ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0 lg:static lg:flex
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-700">
          <div className="text-blue-400">
            <IconShield />
          </div>
          <div>
            <h1 className="text-white font-bold text-base leading-tight">Seguridad</h1>
            <p className="text-slate-400 text-xs">Vecinal 🔒</p>
          </div>
        </div>

        {/* Navegación */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navLinks.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={claseNavLink}
              onClick={() => setSidebarAbierto(false)}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer sidebar */}
        <div className="px-4 py-4 border-t border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-slate-400 text-xs">Sistema activo</span>
          </div>
          <p className="text-slate-500 text-xs mt-1">DVR Meriva N9000 · 4 cámaras</p>
        </div>
      </aside>

      {/* ──── CONTENIDO PRINCIPAL ──── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar móvil */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-4 bg-slate-800 border-b border-slate-700 sticky top-0 z-10">
          <button
            onClick={() => setSidebarAbierto(true)}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Abrir menú"
          >
            <IconMenu />
          </button>
          <div className="flex items-center gap-2">
            <div className="text-blue-400">
              <IconShield />
            </div>
            <span className="text-white font-bold text-sm">Seguridad Vecinal</span>
          </div>
        </header>

        {/* Página actual */}
        <main className="flex-1 overflow-auto pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/* ──── BOTTOM NAV móvil ──── */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 z-10">
        <div className="flex">
          {navLinks.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center gap-1 py-3 text-xs font-medium transition-colors ${
                  isActive ? 'text-blue-400' : 'text-slate-500'
                }`
              }
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
