import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Galeria from './pages/Galeria'
import Placas from './pages/Placas'
import Camaras from './pages/Camaras'
import Personas from './pages/Personas'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="galeria" element={<Galeria />} />
          <Route path="placas" element={<Placas />} />
          <Route path="camaras" element={<Camaras />} />
          <Route path="personas" element={<Personas />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
