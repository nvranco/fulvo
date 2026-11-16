import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { linkWhatsapp } from '../formato.js'
import Aviso from './Aviso.jsx'
import Estado from './Estado.jsx'
import FormularioReclamo from './FormularioReclamo.jsx'
import TarjetaPartido from './TarjetaPartido.jsx'

// Estados desde los que el jugador todavía puede retirarse o bajarse (RQ7).
const RETIRABLES = ['en_espera', 'aceptada']
const PARTIDO_VIGENTE = ['abierto', 'completo']

// Postulaciones del usuario (RQ5 a RQ7). Si lo aceptaron, la API manda el
// WhatsApp del organizador; si no, viene vacío.
export default function MisPostulaciones() {
  const [postulaciones, setPostulaciones] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [reclamando, setReclamando] = useState(null)

  const cargar = useCallback(async () => {
    try {
      const datos = await api.misPostulaciones()
      // Las más nuevas primero.
      setPostulaciones(
        [...datos.postulaciones].sort((a, b) =>
          b.created_at.localeCompare(a.created_at),
        ),
      )
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function retirar(postulacion) {
    const pregunta =
      postulacion.estado === 'aceptada'
        ? '¿Bajarte del partido? El organizador va a recibir un aviso.'
        : '¿Retirar tu postulación?'
    if (!window.confirm(pregunta)) return
    setAviso(null)
    try {
      await api.retirarPostulacion(postulacion.id)
      setAviso({ tipo: 'ok', texto: 'Listo, ya no estás en ese partido.' })
      cargar()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }

  function terminarReclamo(reclamo) {
    setReclamando(null)
    if (reclamo) setAviso({ tipo: 'ok', texto: 'Reclamo enviado.' })
  }

  return (
    <section>
      <h2>Mis postulaciones</h2>
      <Aviso aviso={aviso} />
      {postulaciones === null && <p className="cargando">Cargando…</p>}
      {postulaciones?.length === 0 && (
        <p className="suave">
          Todavía no te postulaste a ningún partido. Buscá uno en el mapa o en
          Partidos abiertos.
        </p>
      )}
      <div className="lista">
        {postulaciones?.map((p) => (
          <TarjetaPartido key={p.id} partido={p.partido}>
            <span>
              Tu postulación: <Estado estado={p.estado} />
            </span>
            {p.whatsapp_organizador && (
              <a
                className="boton-whatsapp"
                href={linkWhatsapp(p.whatsapp_organizador)}
                target="_blank"
                rel="noreferrer"
              >
                WhatsApp de {p.partido.organizador.nombre}:{' '}
                {p.whatsapp_organizador}
              </a>
            )}
            {p.no_show && (
              <>
                <span className="estado estado-no-show">
                  Marcado como no-show
                </span>
                {reclamando !== p.id && (
                  <button className="peligro" onClick={() => setReclamando(p.id)}>
                    Reclamar
                  </button>
                )}
              </>
            )}
            {reclamando === p.id && (
              <div className="reclamo-en-linea">
                <FormularioReclamo
                  tipoObjetivo="no_show"
                  objetivoId={p.id}
                  alTerminar={terminarReclamo}
                />
              </div>
            )}
            {RETIRABLES.includes(p.estado) &&
              PARTIDO_VIGENTE.includes(p.partido.estado) && (
                <button className="peligro" onClick={() => retirar(p)}>
                  {p.estado === 'aceptada' ? 'Bajarme' : 'Retirar postulación'}
                </button>
              )}
          </TarjetaPartido>
        ))}
      </div>
    </section>
  )
}
