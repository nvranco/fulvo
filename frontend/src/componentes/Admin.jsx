import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { formatearFecha, textoPuntuacion } from '../formato.js'
import Aviso from './Aviso.jsx'
import { ETIQUETA_TIPO_RECLAMO, EstadoReclamo } from './Reclamos.jsx'

// Botón con el nombre de un usuario: al clickearlo se carga en Sanciones.
function EnlaceUsuario({ usuario, alElegir }) {
  return (
    <button className="enlace" onClick={() => alElegir(usuario.id)}>
      {usuario.nombre} (#{usuario.id})
    </button>
  )
}

function TarjetaReclamo({ reclamo, alElegirUsuario, alCambiar }) {
  const [denunciado, setDenunciado] = useState(null)
  const [resolucion, setResolucion] = useState('')
  const [bloquear, setBloquear] = useState(false)
  const [aviso, setAviso] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const esUsuario = reclamo.tipo_objetivo === 'usuario'

  useEffect(() => {
    if (!esUsuario) return
    api
      .perfilPublico(reclamo.objetivo_id)
      .then(setDenunciado)
      .catch(() => setDenunciado(null))
  }, [esUsuario, reclamo.objetivo_id])

  async function responder(estado) {
    setEnviando(true)
    setAviso(null)
    try {
      await api.responderReclamo(
        reclamo.id,
        estado,
        resolucion.trim(),
        esUsuario && estado === 'resuelto' && bloquear,
      )
      alCambiar()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
      setEnviando(false)
    }
  }

  let objetivo = `${ETIQUETA_TIPO_RECLAMO[reclamo.tipo_objetivo].toLowerCase()} #${reclamo.objetivo_id}`
  if (esUsuario && denunciado) {
    objetivo = <EnlaceUsuario usuario={denunciado} alElegir={alElegirUsuario} />
  } else if (esUsuario) {
    objetivo = `usuario #${reclamo.objetivo_id}`
  }

  return (
    <article className="tarjeta">
      <div className="tarjeta-cabecera">
        <span className="tipo">{ETIQUETA_TIPO_RECLAMO[reclamo.tipo_objetivo]}</span>
        <EstadoReclamo estado={reclamo.estado} />
        <span className="suave">{formatearFecha(reclamo.created_at)}</span>
      </div>
      <p>
        <strong>Autor:</strong>{' '}
        <EnlaceUsuario usuario={reclamo.autor} alElegir={alElegirUsuario} />
      </p>
      <p>
        <strong>Objetivo:</strong> {objetivo}
        {reclamo.partido_id && <span className="suave"> · partido #{reclamo.partido_id}</span>}
      </p>
      <p>{reclamo.motivo}</p>

      {reclamo.estado === 'abierto' ? (
        <div className="formulario">
          <label>
            Resolución
            <textarea
              rows={2}
              value={resolucion}
              onChange={(e) => setResolucion(e.target.value)}
            />
          </label>
          {esUsuario && (
            <label className="casilla">
              <input
                type="checkbox"
                checked={bloquear}
                onChange={(e) => setBloquear(e.target.checked)}
              />
              Bloquear al denunciado
            </label>
          )}
          <Aviso aviso={aviso} />
          <div className="acciones">
            <button
              className="chico"
              disabled={enviando || !resolucion.trim()}
              onClick={() => responder('resuelto')}
            >
              Dar la razón
            </button>
            <button
              className="chico peligro"
              disabled={enviando || !resolucion.trim()}
              onClick={() => responder('rechazado')}
            >
              Rechazar
            </button>
          </div>
        </div>
      ) : (
        <p className="resolucion">
          <strong>Resolución:</strong> {reclamo.resolucion}
          {reclamo.resuelto_por && (
            <span className="suave">
              {' '}
              · {reclamo.resuelto_por.nombre}
              {reclamo.resuelto_at && `, ${formatearFecha(reclamo.resuelto_at)}`}
            </span>
          )}
        </p>
      )}
    </article>
  )
}

function SeccionReclamos({ alElegirUsuario, alCambiar }) {
  const [estado, setEstado] = useState('abierto')
  const [reclamos, setReclamos] = useState(null)
  const [aviso, setAviso] = useState(null)

  const cargar = useCallback(async () => {
    try {
      const datos = await api.reclamos({ estado })
      setReclamos(
        [...datos.reclamos].sort((a, b) => b.created_at.localeCompare(a.created_at)),
      )
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [estado])

  useEffect(() => {
    cargar()
  }, [cargar])

  function despuesDeActuar() {
    cargar()
    alCambiar()
  }

  return (
    <section>
      <div className="titulo-con-accion">
        <h2>Reclamos</h2>
        <label>
          Estado
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="abierto">Abiertos</option>
            <option value="resuelto">Resueltos</option>
            <option value="rechazado">Rechazados</option>
          </select>
        </label>
      </div>
      <Aviso aviso={aviso} />
      {reclamos === null && <p className="cargando">Cargando…</p>}
      {reclamos?.length === 0 && <p className="suave">No hay reclamos en este estado.</p>}
      <div className="lista">
        {reclamos?.map((r) => (
          <TarjetaReclamo
            key={r.id}
            reclamo={r}
            alElegirUsuario={alElegirUsuario}
            alCambiar={despuesDeActuar}
          />
        ))}
      </div>
    </section>
  )
}

function SeccionSanciones({ usuarioId, alElegirUsuario, version }) {
  const [idTexto, setIdTexto] = useState('')
  const [perfil, setPerfil] = useState(null)
  const [sanciones, setSanciones] = useState([])
  const [motivo, setMotivo] = useState('')
  const [aviso, setAviso] = useState(null)
  const [trabajando, setTrabajando] = useState(false)

  const cargar = useCallback(async (id) => {
    try {
      const [datosPerfil, datosSanciones] = await Promise.all([
        api.perfilPublico(id),
        api.sanciones(id),
      ])
      setPerfil(datosPerfil)
      setSanciones(
        [...datosSanciones.sanciones].sort((a, b) => b.desde.localeCompare(a.desde)),
      )
    } catch (error) {
      setPerfil(null)
      setSanciones([])
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [])

  // Se recarga al elegir a alguien desde Reclamos o cuando un reclamo bloquea.
  useEffect(() => {
    if (!usuarioId) return
    setIdTexto(String(usuarioId))
    setAviso(null)
    cargar(usuarioId)
  }, [usuarioId, version, cargar])

  function buscar(evento) {
    evento.preventDefault()
    const id = Number(idTexto)
    if (id === usuarioId) cargar(id)
    else alElegirUsuario(id)
  }

  async function ejecutar(accion, textoOk) {
    setTrabajando(true)
    setAviso(null)
    try {
      await accion()
      await cargar(perfil.id)
      setAviso({ tipo: 'ok', texto: textoOk })
      return true
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
      return false
    } finally {
      setTrabajando(false)
    }
  }

  async function bloquear(evento) {
    evento.preventDefault()
    const hecho = await ejecutar(
      () => api.bloquearUsuario(perfil.id, motivo.trim()),
      `${perfil.nombre} quedó bloqueado.`,
    )
    if (hecho) setMotivo('')
  }

  const activa = sanciones.find((s) => s.activa)

  return (
    <section>
      <h2>Sanciones</h2>
      <form className="fila-buscar" onSubmit={buscar}>
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
      <Aviso aviso={aviso} />

      {perfil && (
        <div className="tarjeta">
          <div className="tarjeta-cabecera">
            <h3>
              {perfil.nombre} (#{perfil.id})
            </h3>
            {activa ? (
              <span className="estado estado-cancelado">Bloqueado</span>
            ) : (
              <span className="estado estado-abierto">Sin bloqueo</span>
            )}
          </div>
          <p className="suave">
            {perfil.posicion} · {textoPuntuacion(perfil.puntuacion_promedio)} ·{' '}
            {perfil.partidos_jugados} partidos jugados
          </p>

          {!activa && (
            <form className="formulario" onSubmit={bloquear}>
              <label>
                Motivo del bloqueo
                <textarea
                  required
                  rows={2}
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                />
              </label>
              <div className="acciones">
                <button
                  type="submit"
                  className="chico peligro"
                  disabled={trabajando || !motivo.trim()}
                >
                  Bloquear
                </button>
                <span className="ayuda">
                  Cancela sus partidos futuros y retira sus postulaciones.
                </span>
              </div>
            </form>
          )}

          <h4 className="subtitulo">Historial</h4>
          {sanciones.length === 0 && <p className="suave">Sin sanciones.</p>}
          <div className="lista">
            {sanciones.map((s) => (
              <div key={s.id} className="sancion">
                <div className="tarjeta-cabecera">
                  <span className={`estado ${s.activa ? 'estado-cancelado' : ''}`}>
                    {s.activa ? 'Activa' : 'Cerrada'}
                  </span>
                  <span className="suave">
                    Desde {formatearFecha(s.desde)}
                    {s.hasta && ` hasta ${formatearFecha(s.hasta)}`}
                  </span>
                </div>
                <p>{s.motivo}</p>
                <p className="suave">
                  Aplicada por {s.aplicada_por.nombre}
                  {s.reclamo_id && ` · reclamo #${s.reclamo_id}`}
                </p>
                {s.activa && (
                  <button
                    className="chico secundario"
                    disabled={trabajando}
                    onClick={() =>
                      ejecutar(
                        () => api.desbloquearUsuario(perfil.id, s.id),
                        `${perfil.nombre} quedó desbloqueado.`,
                      )
                    }
                  >
                    Desbloquear
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

// Panel del administrador: resolver reclamos (RQ11) y sancionar (RQ10).
export default function Admin({ usuario }) {
  const [usuarioElegido, setUsuarioElegido] = useState(null)
  // Sube al resolver un reclamo, para refrescar las sanciones (puede haber bloqueo).
  const [version, setVersion] = useState(0)

  return (
    <div className="admin">
      <p className="ayuda">Sesión de administración: {usuario.nombre}.</p>
      <div className="admin-columnas">
        <SeccionReclamos
          alElegirUsuario={setUsuarioElegido}
          alCambiar={() => setVersion((v) => v + 1)}
        />
        <SeccionSanciones
          usuarioId={usuarioElegido}
          alElegirUsuario={setUsuarioElegido}
          version={version}
        />
      </div>
    </div>
  )
}
