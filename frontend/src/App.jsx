import { useEffect, useState } from 'react'
import { api, borrarToken, leerToken } from './api.js'
import { textoPuntuacion } from './formato.js'
import Acceso from './componentes/Acceso.jsx'
import Mapa from './componentes/Mapa.jsx'
import Partidos from './componentes/Partidos.jsx'
import PublicarPartido from './componentes/PublicarPartido.jsx'
import MisPostulaciones from './componentes/MisPostulaciones.jsx'
import MisPartidos from './componentes/MisPartidos.jsx'
import Votaciones from './componentes/Votaciones.jsx'
import Reclamos from './componentes/Reclamos.jsx'
import Notificaciones from './componentes/Notificaciones.jsx'
import Admin from './componentes/Admin.jsx'

// Pestañas con useState en vez de un router: para una demo alcanza y es una
// dependencia menos que explicar.
const PESTANAS = [
  { id: 'mapa', nombre: 'Mapa de canchas' },
  { id: 'partidos', nombre: 'Partidos abiertos' },
  { id: 'publicar', nombre: 'Publicar partido' },
  { id: 'postulaciones', nombre: 'Mis postulaciones' },
  { id: 'mis-partidos', nombre: 'Mis partidos' },
  { id: 'votaciones', nombre: 'Votaciones' },
  { id: 'reclamos', nombre: 'Reclamos' },
  { id: 'notificaciones', nombre: 'Notificaciones' },
]

export default function App() {
  const [usuario, setUsuario] = useState(null)
  // Si hay token guardado, se valida pidiendo el perfil antes de mostrar nada.
  const [verificando, setVerificando] = useState(Boolean(leerToken()))
  const [pestana, setPestana] = useState('mapa')
  // Complejo elegido en el mapa, para filtrar partidos o publicar ahí.
  const [complejoElegido, setComplejoElegido] = useState(null)
  const [sinLeer, setSinLeer] = useState(0)
  // La pestaña Admin solo aparece si la API confirma que el usuario es admin.
  const [esAdmin, setEsAdmin] = useState(false)

  useEffect(() => {
    if (!leerToken()) return
    api
      .miPerfil()
      .then(setUsuario)
      .catch(() => borrarToken())
      .finally(() => setVerificando(false))
  }, [])

  // api.js avisa cuando la API responde 401 (token vencido).
  useEffect(() => {
    const alVencer = () => setUsuario(null)
    window.addEventListener('fulvo:sesion-vencida', alVencer)
    return () => window.removeEventListener('fulvo:sesion-vencida', alVencer)
  }, [])

  // Se recuenta lo no leído al cambiar de pestaña: sin polling, alcanza.
  // No depende del objeto usuario completo: refrescarPerfil lo reemplaza y
  // eso no debe volver a disparar el recuento.
  useEffect(() => {
    if (!usuario) return
    api
      .notificaciones({ leida: false })
      .then((datos) => setSinLeer(datos.notificaciones.length))
      .catch(() => {})
  }, [usuario?.id, pestana])

  // Un solo chequeo por usuario: si no es admin, la API responde false.
  useEffect(() => {
    if (!usuario?.id) return
    api.esAdmin(usuario.id).then(setEsAdmin)
  }, [usuario?.id])

  // Deuda al día: se vuelve a pedir el perfil al cambiar de pestaña.
  useEffect(() => {
    if (!usuario) return
    refrescarPerfil()
  }, [pestana])

  if (verificando) return <p className="cargando">Cargando…</p>
  if (!usuario) return <Acceso alEntrar={setUsuario} />

  function salir() {
    borrarToken()
    setUsuario(null)
    setEsAdmin(false)
    setPestana('mapa')
  }

  function irA(id, complejo = null) {
    setComplejoElegido(complejo)
    setPestana(id)
  }

  function refrescarPerfil() {
    api
      .miPerfil()
      .then(setUsuario)
      .catch(() => {})
  }

  // Admin va al final: es la única pestaña que depende de un permiso.
  const pestanas = esAdmin
    ? [...PESTANAS, { id: 'admin', nombre: 'Admin' }]
    : PESTANAS

  return (
    <div className="app">
      <header className="encabezado">
        <h1 className="logo">⚽ Fulvo</h1>
        <div className="perfil">
          <span>
            <strong>{usuario.nombre}</strong> · {usuario.posicion} ·{' '}
            {textoPuntuacion(usuario.puntuacion_promedio)} ·{' '}
            {usuario.partidos_jugados} jugados
          </span>
          <button className="secundario" onClick={salir}>
            Salir
          </button>
        </div>
      </header>

      <nav className="pestanas">
        {pestanas.map((p) => (
          <button
            key={p.id}
            className={p.id === pestana ? 'pestana activa' : 'pestana'}
            onClick={() => irA(p.id)}
          >
            {p.nombre}
            {p.id === 'notificaciones' && sinLeer > 0 && (
              <span className="contador">{sinLeer}</span>
            )}
            {p.id === 'votaciones' && usuario.deuda > 0 && (
              <span className="contador">{usuario.deuda}</span>
            )}
          </button>
        ))}
      </nav>

      {usuario.deuda > 0 && (
        <div className={usuario.habilitado ? 'banner-deuda' : 'banner-deuda bloqueado'}>
          {usuario.habilitado ? (
            <span>
              Debés votaciones en {usuario.deuda} partido(s). Con más de 3 no
              vas a poder publicar ni postularte.
            </span>
          ) : (
            <>
              <span>
                Debés votaciones en {usuario.deuda} partidos: no podés publicar
                ni postularte hasta completarlas.
              </span>
              <button className="secundario" onClick={() => irA('votaciones')}>
                Ir a votar
              </button>
            </>
          )}
        </div>
      )}

      <main className="contenido">
        {pestana === 'mapa' && (
          <Mapa
            alVerPartidos={(c) => irA('partidos', c)}
            alPublicar={(c) => irA('publicar', c)}
          />
        )}
        {pestana === 'partidos' && (
          <Partidos
            usuario={usuario}
            complejo={complejoElegido}
            alQuitarComplejo={() => setComplejoElegido(null)}
          />
        )}
        {pestana === 'publicar' && (
          <PublicarPartido
            usuario={usuario}
            complejoInicial={complejoElegido}
            alPublicar={() => irA('mis-partidos')}
          />
        )}
        {pestana === 'postulaciones' && <MisPostulaciones />}
        {pestana === 'mis-partidos' && <MisPartidos usuario={usuario} />}
        {pestana === 'votaciones' && (
          <Votaciones alCambiarPerfil={refrescarPerfil} />
        )}
        {pestana === 'reclamos' && <Reclamos usuario={usuario} />}
        {pestana === 'notificaciones' && (
          <Notificaciones alCambiarSinLeer={setSinLeer} />
        )}
        {pestana === 'admin' && esAdmin && <Admin usuario={usuario} />}
      </main>
    </div>
  )
}
