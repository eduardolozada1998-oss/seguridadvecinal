import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../config/supabase'

/**
 * Hook para estadísticas del dashboard
 */
export function useEstadisticas() {
  const [stats, setStats] = useState({
    totalHoy: 0,
    personasHoy: 0,
    vehiculosHoy: 0,
    placasHoy: 0,
  })
  const [grafica, setGrafica] = useState([])
  const [ultimosEventos, setUltimosEventos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const cargarEstadisticas = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)

      const hoy = new Date().toISOString().split('T')[0]
      const hace24h = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

      // Cargar eventos de hoy y últimos 6 simultáneamente
      const [{ data: eventosHoy, error: e1 }, { data: ultimos, error: e2 }] = await Promise.all([
        supabase
          .from('eventos')
          .select('*')
          .gte('created_at', `${hoy}T00:00:00`)
          .order('created_at', { ascending: false }),
        supabase
          .from('eventos')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(6),
      ])

      if (e1) throw e1
      if (e2) throw e2

      const eventos = eventosHoy || []

      // Calcular estadísticas del día
      const personasHoy = eventos.filter(e => e.tipo === 'persona').length
      const vehiculosHoy = eventos.filter(e => e.tipo === 'vehiculo').length
      const placasHoy = eventos.filter(e => e.valor && e.valor.trim() !== '').length

      setStats({
        totalHoy: eventos.length,
        personasHoy,
        vehiculosHoy,
        placasHoy,
      })

      setUltimosEventos(ultimos || [])

      // Construir datos de gráfica: eventos por hora en las últimas 24h
      const agrupadosPorHora = {}
      for (let i = 0; i < 24; i++) {
        const hora = new Date(Date.now() - (23 - i) * 60 * 60 * 1000)
        const horaKey = hora.getHours()
        const horaLabel = `${String(horaKey).padStart(2, '0')}:00`
        agrupadosPorHora[horaLabel] = { hora: horaLabel, personas: 0, vehiculos: 0, total: 0 }
      }

      // Cargar eventos últimas 24h para la gráfica
      const { data: eventos24h } = await supabase
        .from('eventos')
        .select('tipo, created_at')
        .gte('created_at', hace24h)
        .order('created_at', { ascending: true })

      if (eventos24h) {
        eventos24h.forEach(evento => {
          const hora = new Date(evento.created_at).getHours()
          const horaLabel = `${String(hora).padStart(2, '0')}:00`
          if (agrupadosPorHora[horaLabel]) {
            agrupadosPorHora[horaLabel].total++
            if (evento.tipo === 'persona') agrupadosPorHora[horaLabel].personas++
            if (evento.tipo === 'vehiculo') agrupadosPorHora[horaLabel].vehiculos++
          }
        })
      }

      setGrafica(Object.values(agrupadosPorHora))
    } catch (err) {
      console.error('Error cargando estadísticas:', err)
      setError(err.message || 'Error al cargar estadísticas')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargarEstadisticas()

    // Recargar estadísticas cada 30 segundos
    const intervalo = setInterval(cargarEstadisticas, 30000)
    return () => clearInterval(intervalo)
  }, [cargarEstadisticas])

  return { stats, grafica, ultimosEventos, cargando, error, recargar: cargarEstadisticas }
}

/**
 * Hook para estadísticas por cámara
 */
export function useEstadisticasCamaras() {
  const [camaras, setCamaras] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const cargarCamaras = useCallback(async () => {
    try {
      setCargando(true)
      setError(null)

      const hoy = new Date().toISOString().split('T')[0]
      const hace1h = new Date(Date.now() - 60 * 60 * 1000).toISOString()

      const listaCamaras = ['01', '02', '03', '04']

      const datos = await Promise.all(
        listaCamaras.map(async (numCamara) => {
          const [{ data: eventosHoy }, { data: ultimoEvento }, { data: eventosUltimaHora }] =
            await Promise.all([
              supabase
                .from('eventos')
                .select('id')
                .eq('camara', numCamara)
                .gte('created_at', `${hoy}T00:00:00`),
              supabase
                .from('eventos')
                .select('*')
                .eq('camara', numCamara)
                .order('created_at', { ascending: false })
                .limit(1),
              supabase
                .from('eventos')
                .select('id')
                .eq('camara', numCamara)
                .gte('created_at', hace1h),
            ])

          const ultimo = ultimoEvento && ultimoEvento[0]
          const activa = eventosUltimaHora && eventosUltimaHora.length > 0

          return {
            id: numCamara,
            nombre: `Cámara ${numCamara}`,
            totalHoy: eventosHoy?.length || 0,
            ultimoEvento: ultimo || null,
            activa,
          }
        })
      )

      setCamaras(datos)
    } catch (err) {
      console.error('Error cargando cámaras:', err)
      setError(err.message || 'Error al cargar datos de cámaras')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargarCamaras()
    const intervalo = setInterval(cargarCamaras, 30000)
    return () => clearInterval(intervalo)
  }, [cargarCamaras])

  return { camaras, cargando, error, recargar: cargarCamaras }
}
