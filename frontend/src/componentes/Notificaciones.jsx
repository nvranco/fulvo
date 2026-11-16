import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import Aviso from './Aviso.jsx'

function fechaCorta(texto) {
  const [fecha, hora = ''] = texto.split('T')
  const [, mes, dia] = fecha.split('-')
  return `${dia}/${mes} ${hora.slice(0, 5)}`
}

// Notificaciones dentro de la app (RQ9). Las crea el backend
// (NotificadorPartido, patrón Observer) cada vez que pasa algo en un partido.
export default function Notificaciones({ alCambiarSinLeer }) {
  const [notificaciones, setNotificaciones] = useState(null)
  const [aviso, setAviso] = useState(null)

  const cargar = useCallback(async () => {
    try {
      const datos = await api.notificaciones()
      const lista = [...datos.notificaciones].sort((a, b) =>
        b.created_at.localeCompare(a.created_at),
      )
      setNotificaciones(lista)
      alCambiarSinLeer(lista.filter((n) => !n.leida).length)
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [alCambiarSinLeer])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function marcar(ids) {
    try {
      await Promise.all(ids.map((id) => api.marcarLeida(id)))
      cargar()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }

  const sinLeer = notificaciones?.filter((n) => !n.leida) ?? []

  return (
    <section className="angosto">
      <div className="titulo-con-accion">
        <h2>Notificaciones</h2>
        {sinLeer.length > 0 && (
          <button className="secundario" onClick={() => marcar(sinLeer.map((n) => n.id))}>
            Marcar todas como leídas
          </button>
        )}
      </div>
      <Aviso aviso={aviso} />
      {notificaciones === null && <p className="cargando">Cargando…</p>}
      {notificaciones?.length === 0 && (
        <p className="suave">No tenés notificaciones.</p>
      )}
      <ul className="notificaciones">
        {notificaciones?.map((n) => (
          <li key={n.id} className={n.leida ? 'leida' : 'nueva'}>
            <div>
              <span className="suave">{fechaCorta(n.created_at)}</span>
              <p>{n.mensaje}</p>
            </div>
            {!n.leida && (
              <button className="chico secundario" onClick={() => marcar([n.id])}>
                Marcar leída
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
