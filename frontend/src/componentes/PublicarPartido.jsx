import { useEffect, useState } from 'react'
import { api } from '../api.js'
import {
  JUGADORES_POR_TIPO,
  TIPOS,
  ahoraParaInput,
  recordarPartidoPublicado,
} from '../formato.js'
import Aviso from './Aviso.jsx'

// Formulario para publicar un partido (RQ4). La duración es fija (60 min)
// y el organizador sale del token, así que no se piden.
export default function PublicarPartido({ usuario, complejoInicial, alPublicar }) {
  const [complejos, setComplejos] = useState([])
  const [complejoId, setComplejoId] = useState(complejoInicial?.id ?? '')
  const [inicio, setInicio] = useState('')
  const [tipo, setTipo] = useState('F5')
  const [cupos, setCupos] = useState(1)
  const [aviso, setAviso] = useState(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    api
      .complejos()
      .then((datos) =>
        setComplejos(
          [...datos.complejos].sort((a, b) => a.nombre.localeCompare(b.nombre)),
        ),
      )
      .catch((error) => setAviso({ tipo: 'error', texto: error.message }))
  }, [])

  const maximo = JUGADORES_POR_TIPO[tipo] - 1

  function cambiarTipo(nuevo) {
    setTipo(nuevo)
    setCupos((actual) => Math.min(actual, JUGADORES_POR_TIPO[nuevo] - 1))
  }

  async function publicar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setAviso(null)
    try {
      // `inicio` va sin zona horaria: la API lo toma como hora de Argentina.
      const partido = await api.publicarPartido({
        complejo_id: Number(complejoId),
        inicio,
        tipo,
        cupos_faltantes: Number(cupos),
      })
      recordarPartidoPublicado(usuario.id, partido.id)
      alPublicar()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
      setEnviando(false)
    }
  }

  return (
    <section className="angosto">
      <h2>Publicar partido</h2>
      <p className="suave">
        Contá dónde y cuándo juegan y cuántos les faltan. Los partidos duran
        60 minutos.
      </p>
      <Aviso aviso={aviso} />
      <form className="formulario" onSubmit={publicar}>
        <label>
          Complejo
          <select
            required
            value={complejoId}
            onChange={(e) => setComplejoId(e.target.value)}
          >
            <option value="" disabled>
              Elegí una cancha
            </option>
            {complejos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre} ({c.zona})
              </option>
            ))}
          </select>
        </label>
        <label>
          Fecha y hora (hora de Argentina)
          <input
            type="datetime-local"
            required
            min={ahoraParaInput()}
            value={inicio}
            onChange={(e) => setInicio(e.target.value)}
          />
        </label>
        <div className="fila">
          <label>
            Tipo
            <select value={tipo} onChange={(e) => cambiarTipo(e.target.value)}>
              {TIPOS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Cupos faltantes (máx. {maximo})
            <input
              type="number"
              required
              min={1}
              max={maximo}
              value={cupos}
              onChange={(e) => setCupos(e.target.value)}
            />
          </label>
        </div>
        <button type="submit" disabled={enviando}>
          Publicar
        </button>
      </form>
    </section>
  )
}
