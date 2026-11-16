import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { formatearFecha } from '../formato.js'
import Aviso from './Aviso.jsx'
import FormularioReclamo from './FormularioReclamo.jsx'

export const ETIQUETA_TIPO_RECLAMO = {
  no_show: 'No-show',
  votacion: 'Votación',
  usuario: 'Usuario',
  complejo: 'Complejo',
}

const ETIQUETA_ESTADO_RECLAMO = {
  abierto: 'Abierto',
  resuelto: 'Resuelto',
  rechazado: 'Rechazado',
}

export function EstadoReclamo({ estado }) {
  return (
    <span className={`estado estado-${estado}`}>
      {ETIQUETA_ESTADO_RECLAMO[estado] ?? estado}
    </span>
  )
}

// Mis reclamos y alta de reclamos contra un usuario o un complejo (RQ11).
// Los de no-show y votación se abren desde sus propias pantallas.
export default function Reclamos({ usuario }) {
  const [reclamos, setReclamos] = useState(null)
  const [complejos, setComplejos] = useState([])
  const [aviso, setAviso] = useState(null)
  const [tipo, setTipo] = useState('usuario')
  const [idTexto, setIdTexto] = useState('')
  const [denunciado, setDenunciado] = useState(null)
  const [complejoId, setComplejoId] = useState('')
  const [formularioAbierto, setFormularioAbierto] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const datos = await api.reclamos()
      setReclamos(
        [...datos.reclamos].sort((a, b) => b.created_at.localeCompare(a.created_at)),
      )
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [])

  useEffect(() => {
    cargar()
    api
      .complejos()
      .then((datos) =>
        setComplejos(
          [...datos.complejos].sort((a, b) => a.nombre.localeCompare(b.nombre)),
        ),
      )
      .catch((error) => setAviso({ tipo: 'error', texto: error.message }))
  }, [cargar])

  function cambiarTipo(nuevo) {
    setTipo(nuevo)
    setFormularioAbierto(false)
    setDenunciado(null)
    setAviso(null)
  }

  async function buscarUsuario(evento) {
    evento.preventDefault()
    setAviso(null)
    setDenunciado(null)
    setFormularioAbierto(false)
    if (Number(idTexto) === usuario.id) {
      setAviso({ tipo: 'error', texto: 'No podés denunciarte a vos mismo.' })
      return
    }
    try {
      setDenunciado(await api.perfilPublico(Number(idTexto)))
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }

  function terminar(reclamo) {
    setFormularioAbierto(false)
    if (!reclamo) return
    setDenunciado(null)
    setIdTexto('')
    setComplejoId('')
    setAviso({ tipo: 'ok', texto: 'Reclamo enviado. Un administrador lo va a revisar.' })
    cargar()
  }

  const objetivoId = tipo === 'usuario' ? denunciado?.id : Number(complejoId)

  return (
    <section className="angosto">
      <h2>Reclamos</h2>
      <p className="ayuda">
        Los reclamos por no-show se abren desde "Mis postulaciones" y los de una
        votación, desde "Votaciones". Acá podés denunciar a un usuario o a un
        complejo.
      </p>

      <div className="tarjeta">
        <h3>Nuevo reclamo</h3>
        <div className="filtros">
          <label>
            Sobre
            <select value={tipo} onChange={(e) => cambiarTipo(e.target.value)}>
              <option value="usuario">Un usuario</option>
              <option value="complejo">Un complejo</option>
            </select>
          </label>
          {tipo === 'usuario' ? (
            <form className="fila-buscar" onSubmit={buscarUsuario}>
              <label>
                Id del usuario
                <input
                  required
                  type="number"
                  min="1"
                  value={idTexto}
                  onChange={(e) => setIdTexto(e.target.value)}
                />
              </label>
              <button type="submit" className="secundario">
                Buscar
              </button>
            </form>
          ) : (
            <label>
              Complejo
              <select
                value={complejoId}
                onChange={(e) => {
                  setComplejoId(e.target.value)
                  setFormularioAbierto(false)
                }}
              >
                <option value="" disabled>
                  Elegí una cancha
                </option>
                {complejos.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        {tipo === 'usuario' && denunciado && (
          <p>
            Vas a denunciar a <strong>{denunciado.nombre}</strong> ({denunciado.posicion}).
          </p>
        )}
        {objetivoId && !formularioAbierto && (
          <button onClick={() => setFormularioAbierto(true)}>Reclamar</button>
        )}
        {objetivoId && formularioAbierto && (
          <FormularioReclamo
            tipoObjetivo={tipo}
            objetivoId={objetivoId}
            alTerminar={terminar}
          />
        )}
      </div>
      <Aviso aviso={aviso} />

      <h3 className="subtitulo">Mis reclamos</h3>
      {reclamos === null && <p className="cargando">Cargando…</p>}
      {reclamos?.length === 0 && <p className="suave">Todavía no abriste reclamos.</p>}
      <div className="lista">
        {reclamos?.map((r) => (
          <article key={r.id} className="tarjeta">
            <div className="tarjeta-cabecera">
              <span className="tipo">{ETIQUETA_TIPO_RECLAMO[r.tipo_objetivo]}</span>
              <EstadoReclamo estado={r.estado} />
              <span className="suave">{formatearFecha(r.created_at)}</span>
            </div>
            <p>{r.motivo}</p>
            {r.resolucion && (
              <p className="resolucion">
                <strong>Resolución:</strong> {r.resolucion}
                {r.resuelto_por && (
                  <span className="suave">
                    {' '}
                    · {r.resuelto_por.nombre}
                    {r.resuelto_at && `, ${formatearFecha(r.resuelto_at)}`}
                  </span>
                )}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
