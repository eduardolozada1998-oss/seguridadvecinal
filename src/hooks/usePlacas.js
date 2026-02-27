import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../config/supabase'

/**
 * Hook para obtener detecciones de placas vehiculares
 */
export function usePlacas(busqueda = '') {
  const [placas, setPlacas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [ordenPor, setOrdenPor] = useState('created_at')
  const [ordenAsc, setOrdenAsc] = useState(false)

  const cargarPlacas = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)

      let query = supabase
        .from('eventos')
        .select('*')
        .not('valor', 'is', null)
        .neq('valor', '')
        .order(ordenPor, { ascending: ordenAsc })

      if (busqueda && busqueda.trim()) {
        query = query.ilike('valor', `%${busqueda.trim()}%`)
      }

      const { data, error: err } = await query

      if (err) throw err
      setPlacas(data || [])
    } catch (err) {
      console.error('Error cargando placas:', err)
      setError(err.message || 'Error al cargar registros de placas')
    } finally {
      setCargando(false)
    }
  }, [busqueda, ordenPor, ordenAsc])

  useEffect(() => {
    cargarPlacas()
  }, [cargarPlacas])

  const cambiarOrden = useCallback((campo) => {
    if (campo === ordenPor) {
      setOrdenAsc(prev => !prev)
    } else {
      setOrdenPor(campo)
      setOrdenAsc(false)
    }
  }, [ordenPor])

  return { placas, cargando, error, ordenPor, ordenAsc, cambiarOrden, recargar: cargarPlacas }
}
