import { Component } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Galeria from './pages/Galeria'
import Placas from './pages/Placas'
import Camaras from './pages/Camaras'
import Personas from './pages/Personas'
import Desconocidos from './pages/Desconocidos'
import AlertDashboard from './pages/AlertDashboard'
import EvidenceViewer from './pages/EvidenceViewer'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  componentDidCatch(error, info) {
    console.error('ErrorBoundary:', error, info)
  }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
          <div className="text-center max-w-md">
            <p className="text-4xl mb-4">⚠️</p>
            <h2 className="text-white font-bold text-xl mb-2">Error al cargar la página</h2>
            <p className="text-slate-400 text-sm mb-4">{this.state.error.message}</p>
            <button
              onClick={() => this.setState({ error: null })}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm"
            >
              Reintentar
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="galeria" element={<Galeria />} />
            <Route path="placas" element={<Placas />} />
            <Route path="camaras" element={<Camaras />} />
            <Route path="personas" element={<Personas />} />
            <Route path="desconocidos" element={<Desconocidos />} />
            <Route path="alertas" element={<AlertDashboard />} />
            <Route path="evidencia" element={<EvidenceViewer />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
