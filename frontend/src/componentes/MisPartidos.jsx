import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { linkWhatsapp, partidosPublicados, textoPuntuacion } from '../formato.js'
import Aviso from './Aviso.jsx'
import Estado from './Estado.jsx'
import TarjetaPartido from './TarjetaPartido.jsx'

const PARTIDO_VIGENTE = ['abierto', 'completo']

// Panel del organizador (RQ6 y RQ7): lista de espera de cada partido suyo,
// aceptar, rechazar o revocar, y cancelar el partido.
//
// La API no tiene un "mis partidos": se juntan los abiertos donde el usuario
// es organizador, los jugados (salen de sus votaciones) y los que publicó
// desde este navegador (localStorage), que cubre los completos.
export default function MisPartidos({ usuario }) {
  const [items, setItems] = useState(null)
  const [aviso, setAviso] = useState(null)

  const cargar = useCallback(async () => {
    try {
      const [abiertos, votaciones] = await Promise.all([
        api.partidos(),
        api.votaciones(),
      ])
      const ids = new Set(partidosPublicados(usuario.id))
      // Los jugados no salen en /partidos: se recuperan de sus votaciones.
      const propios = [
        ...abiertos.partidos,
        ...votaciones.votaciones.map((v) => v.partido),
      ]
      for (const p of propios) {
        if (p.organizador.id === usuario.id) ids.add(p.id)
      }
      // allSettled: si un id guardado ya no existe, se saltea sin romper todo.
      const resultados = await Promise.allSettled(
        [...ids].map(async (id) => {
          const [partido, datos] = await Promise.all([
            api.partido(id),
            api.postulacionesDelPartido(id),
          ])
          return { partido, postulaciones: datos.postulaciones }
        }),
      )
      setItems(
        resultados
          .filter((r) => r.status === 'fulfilled')
          .map((r) => r.value)
          .sort((a, b) => a.partido.inicio.localeCompare(b.partido.inicio)),
      )
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [usuario.id])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function hacer(accion, mensajeOk) {
    setAviso(null)
    try {
      await accion()
      setAviso({ tipo: 'ok', texto: mensajeOk })
      cargar()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }

  function responder(partido, postulacion, estado) {
    const textos = {
      aceptada: `Aceptaste a ${postulacion.jugador.nombre}. Ya se ven el WhatsApp.`,
      rechazada: `Rechazaste a ${postulacion.jugador.nombre}.`,
      revocada: `Sacaste a ${postulacion.jugador.nombre} del partido.`,
    }
    if (estado === 'revocada' && !window.confirm('¿Sacar a este jugador del partido?')) {
      return
    }
    hacer(
      () => api.responderPostulacion(partido.id, postulacion.id, estado),
      textos[estado],
    )
  }

  function marcarNoShow(partido, postulacion) {
    if (!window.confirm(`¿Confirmás que ${postulacion.jugador.nombre} no vino?`)) {
      return
    }
    hacer(
      () => api.marcarNoShow(partido.id, postulacion.id),
      `Marcaste a ${postulacion.jugador.nombre} como no-show.`,
    )
  }

  function cancelar(partido) {
    if (!window.confirm('¿Cancelar el partido? Se avisa a todos los postulados.')) {
      return
    }
    hacer(() => api.cancelarPartido(partido.id), 'Partido cancelado.')
  }

  return (
    <section>
      <h2>Mis partidos</h2>
      <Aviso aviso={aviso} />
      {items === null && <p className="cargando">Cargando…</p>}
      {items?.length === 0 && (
        <p className="suave">Todavía no publicaste partidos.</p>
      )}

      <div className="lista">
        {items?.map(({ partido, postulaciones }) => (
          <TarjetaPartido key={partido.id} partido={partido}>
            {PARTIDO_VIGENTE.includes(partido.estado) && (
              <button className="peligro" onClick={() => cancelar(partido)}>
                Cancelar partido
              </button>
            )}
            <div className="postulantes">
              <h4>Postulantes ({postulaciones.length})</h4>
              {postulaciones.length === 0 ? (
                <p className="suave">Nadie se postuló todavía.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Jugador</th>
                      <th>Posición</th>
                      <th>Puntuación</th>
                      <th>Estado</th>
                      <th>WhatsApp</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Ya vienen en el orden de la lista de espera. */}
                    {postulaciones.map((p) => (
                      <tr key={p.id}>
                        <td>{p.jugador.nombre}</td>
                        <td>{p.jugador.posicion}</td>
                        <td>{textoPuntuacion(p.jugador.puntuacion_promedio)}</td>
                        <td>
                          <Estado estado={p.estado} />
                        </td>
                        <td>
                          {p.whatsapp_jugador ? (
                            <a
                              href={linkWhatsapp(p.whatsapp_jugador)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {p.whatsapp_jugador}
                            </a>
                          ) : (
                            <span className="suave">oculto</span>
                          )}
                        </td>
                        <td className="acciones-fila">
                          {p.estado === 'en_espera' && (
                            <>
                              <button
                                className="chico"
                                onClick={() => responder(partido, p, 'aceptada')}
                              >
                                Aceptar
                              </button>
                              <button
                                className="chico secundario"
                                onClick={() => responder(partido, p, 'rechazada')}
                              >
                                Rechazar
                              </button>
                            </>
                          )}
                          {p.estado === 'aceptada' && partido.estado === 'jugado' && (
                            p.no_show ? (
                              <span className="estado estado-no-show">No-show</span>
                            ) : (
                              <button
                                className="chico peligro"
                                onClick={() => marcarNoShow(partido, p)}
                              >
                                No vino
                              </button>
                            )
                          )}
                          {p.estado === 'aceptada' && partido.estado !== 'jugado' && (
                            <button
                              className="chico peligro"
                              onClick={() => responder(partido, p, 'revocada')}
                            >
                              Revocar
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </TarjetaPartido>
        ))}
      </div>
    </section>
  )
}
