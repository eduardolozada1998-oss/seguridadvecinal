import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../config/supabase'

/**
 * Hook para obtener eventos con filtros opcionales
 * @param {Object} filtros - { tipo, camara, fecha, limite }
 */
export function useEventos(filtros = {}) {
  const [eventos, setEventos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [totalDisponible, setTotalDisponible] = useState(0)

  const { tipo, camara, fecha, limite = 20 } = filtros

  const cargarEventos = useCallback(async (offset = 0, reemplazar = true) => {
    try {
      setCargando(true)
      setError(null)

      let query = supabase
        .from('eventos')
        .select('*', { count: 'exact' })
        .order('created_at', { ascending: false })
        .range(offset, offset + limite - 1)

      if (tipo && tipo !== 'todos') {
        query = query.eq('tipo', tipo)
      }

      if (camara && camara !== 'todas') {
        query = query.eq('camara', camara)
      }

      if (fecha) {
        query = query
          .gte('created_at', `${fecha}T00:00:00`)
          .lte('created_at', `${fecha}T23:59:59`)
      }

      const { data, error: err, count } = await query

      if (err) throw err

      setTotalDisponible(count || 0)
      setEventos(prev => reemplazar ? (data || []) : [...prev, ...(data || [])])
    } catch (err) {
      console.error('Error cargando eventos:', err)
      setError(err.message || 'Error al cargar eventos')
    } finally {
      setCargando(false)
    }
  }, [tipo, camara, fecha, limite])

  useEffect(() => {
    cargarEventos(0, true)
  }, [cargarEventos])

  // Suscripción en tiempo real
  useEffect(() => {
    let canal = null
    try {
      canal = supabase
        .channel('eventos-realtime')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'eventos' }, () => {
          cargarEventos(0, true)
        })
        .subscribe((status, err) => {
          if (err) console.warn('Realtime suscripción error:', err)
        })
    } catch (err) {
      console.warn('Realtime no disponible:', err)
    }
    return () => {
      if (canal) supabase.removeChannel(canal).catch(() => {})
    }
  }, [cargarEventos])

  const cargarMas = useCallback(() => {
    cargarEventos(eventos.length, false)
  }, [cargarEventos, eventos.length])

  const hayMas = eventos.length < totalDisponible

  return { eventos, cargando, error, totalDisponible, cargarMas, hayMas, recargar: () => cargarEventos(0, true) }
}
