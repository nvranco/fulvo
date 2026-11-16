import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { formatearFecha } from '../formato.js'
import Aviso from './Aviso.jsx'
import FormularioReclamo from './FormularioReclamo.jsx'

const SECCIONES = [
  { id: 'pendientes', texto: 'Pendientes' },
  { id: 'emitidas', texto: 'Emitidas' },
  { id: 'recibidas', texto: 'Recibidas' },
]

const FILTROS = {
  pendientes: { estado: 'pendiente' },
  emitidas: { estado: 'emitida' },
  recibidas: { recibidas: true },
}

const VACIO = {
  pendientes:
    'No tenés votaciones pendientes. Aparecen cuando termina un partido en el que jugaste.',
  emitidas: 'Todavía no votaste a nadie. Tus votos emitidos aparecen acá.',
  recibidas:
    'Todavía nadie te votó. Los votos que recibís aparecen cuando termina un partido en el que jugaste.',
}

const ETIQUETA_VOTACION = {
  pendiente: 'Pendiente',
  emitida: 'Emitida',
  anulada: 'Anulada',
}

function nombreReceptor(v) {
  return v.receptor_usuario
    ? v.receptor_usuario.nombre
    : `${v.receptor_complejo.nombre} (complejo)`
}

function Estrellas({ cantidad }) {
  if (cantidad == null) return <span className="suave">sin estrellas</span>
  return (
    <span className="estrellas-fijas" aria-label={`${cantidad} de 5 estrellas`}>
      {'★'.repeat(cantidad)}
      {'☆'.repeat(5 - cantidad)}
    </span>
  )
}

// Selector de 0 a 5 estrellas: botones, así se maneja con teclado.
function SelectorEstrellas({ valor, alElegir }) {
  return (
    <div className="selector-estrellas" role="group" aria-label="Estrellas">
      {[0, 1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`estrella${valor === n ? ' elegida' : ''}`}
          aria-label={`${n} ${n === 1 ? 'estrella' : 'estrellas'}`}
          aria-pressed={valor === n}
          onClick={() => alElegir(n)}
        >
          {n === 0 ? '0' : `${n}★`}
        </button>
      ))}
    </div>
  )
}

// Votaciones post-partido (RQ8): votar a los demás jugadores y al complejo,
// ver el historial y los votos recibidos (sin mostrar quién votó).
export default function Votaciones({ alCambiarPerfil }) {
  const [seccion, setSeccion] = useState('pendientes')
  const [votaciones, setVotaciones] = useState(null)
  const [elegidas, setElegidas] = useState({})
  const [reclamando, setReclamando] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [enviando, setEnviando] = useState(null)

  const cargar = useCallback(async () => {
    try {
      const datos = await api.votaciones(FILTROS[seccion])
      setVotaciones(datos.votaciones)
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [seccion])

  useEffect(() => {
    cargar()
  }, [cargar])

  function cambiarSeccion(id) {
    setSeccion(id)
    setVotaciones(null)
    setReclamando(null)
    setAviso(null)
  }

  // Se envían todos los votos de un partido juntos: la deuda se cuenta por
  // partido, así que votar a medias no la reduce. allSettled evita que un
  // error frene a los demás.
  async function enviarVotos(partidoId, lista) {
    setAviso(null)
    setEnviando(partidoId)
    const resultados = await Promise.allSettled(
      lista.map((v) => api.emitirVotacion(v.id, elegidas[v.id])),
    )
    const fallos = []
    const restantes = { ...elegidas }
    resultados.forEach((r, i) => {
      if (r.status === 'rejected') {
        fallos.push(`${nombreReceptor(lista[i])} (${r.reason.message})`)
      } else {
        delete restantes[lista[i].id]
      }
    })
    setElegidas(restantes)
    if (fallos.length > 0) {
      setAviso({
        tipo: 'error',
        texto: `No se pudo votar a: ${fallos.join(', ')}.`,
      })
    } else {
      setAviso({ tipo: 'ok', texto: 'Votos enviados.' })
    }
    await cargar()
    alCambiarPerfil()
    setEnviando(null)
  }

  function terminarReclamo(reclamo) {
    setReclamando(null)
    if (reclamo) setAviso({ tipo: 'ok', texto: 'Reclamo enviado.' })
  }

  // Las pendientes se agrupan por partido.
  const grupos = []
  if (seccion === 'pendientes' && votaciones) {
    for (const v of votaciones) {
      let grupo = grupos.find((g) => g.partido.id === v.partido.id)
      if (!grupo) {
        grupo = { partido: v.partido, votaciones: [] }
        grupos.push(grupo)
      }
      grupo.votaciones.push(v)
    }
  }

  return (
    <section>
      <h2>Votaciones</h2>
      <div className="pestanas sub-pestanas">
        {SECCIONES.map((s) => (
          <button
            key={s.id}
            className={`pestana${seccion === s.id ? ' activa' : ''}`}
            onClick={() => cambiarSeccion(s.id)}
          >
            {s.texto}
          </button>
        ))}
      </div>
      <Aviso aviso={aviso} />
      {votaciones === null && <p className="cargando">Cargando…</p>}
      {votaciones?.length === 0 && <p className="suave">{VACIO[seccion]}</p>}

      {seccion === 'pendientes' && (
        <div className="lista">
          {grupos.map(({ partido, votaciones: lista }) => {
            const faltan = lista.filter((v) => elegidas[v.id] == null).length
            return (
              <article key={partido.id} className="tarjeta">
                <div className="tarjeta-cabecera">
                  <span className="tipo">{partido.tipo}</span>
                  <strong>{formatearFecha(partido.inicio)}</strong>
                  <span className="suave">{partido.complejo.nombre}</span>
                </div>
                <ul className="votos votos-pendientes">
                  {lista.map((v) => (
                    <li key={v.id}>
                      <strong>{nombreReceptor(v)}</strong>
                      <SelectorEstrellas
                        valor={elegidas[v.id] ?? null}
                        alElegir={(n) =>
                          setElegidas({ ...elegidas, [v.id]: n })
                        }
                      />
                    </li>
                  ))}
                </ul>
                <div className="acciones">
                  <button
                    disabled={faltan > 0 || enviando !== null}
                    onClick={() => enviarVotos(partido.id, lista)}
                  >
                    {enviando === partido.id ? 'Enviando…' : 'Enviar votos'}
                  </button>
                  {faltan > 0 && (
                    <span className="suave">Falta elegir {faltan}</span>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {seccion === 'emitidas' && votaciones?.length > 0 && (
        <ul className="votos tarjeta">
          {votaciones.map((v) => (
            <li key={v.id}>
              <span>
                <strong>{nombreReceptor(v)}</strong>
                <span className="suave">
                  {' '}
                  · {v.partido.complejo.nombre}, {formatearFecha(v.partido.inicio)}
                </span>
              </span>
              <Estrellas cantidad={v.estrellas} />
            </li>
          ))}
        </ul>
      )}

      {seccion === 'recibidas' && votaciones?.length > 0 && (
        <ul className="votos tarjeta">
          {votaciones.map((v) => (
            <li key={v.id}>
              <span className={v.estado === 'anulada' ? 'anulada' : ''}>
                <span className="suave">
                  {v.partido.complejo.nombre}, {formatearFecha(v.partido.inicio)}
                </span>{' '}
                <span className={`estado estado-${v.estado}`}>
                  {ETIQUETA_VOTACION[v.estado] ?? v.estado}
                </span>
              </span>
              <Estrellas cantidad={v.estrellas} />
              {v.estado === 'emitida' && reclamando !== v.id && (
                <button
                  className="chico peligro"
                  onClick={() => setReclamando(v.id)}
                >
                  Reclamar
                </button>
              )}
              {reclamando === v.id && (
                <div className="reclamo-en-linea">
                  <FormularioReclamo
                    tipoObjetivo="votacion"
                    objetivoId={v.id}
                    alTerminar={terminarReclamo}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
