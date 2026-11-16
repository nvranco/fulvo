import { formatearFecha, textoPuntuacion } from '../formato.js'
import Estado from './Estado.jsx'

// Datos de un partido (PartidoPublico de la API). `children` son las
// acciones que cada pantalla le agrega abajo (postularse, cancelar, etc.).
export default function TarjetaPartido({ partido, children }) {
  const { complejo, organizador } = partido
  // Singular o plural según los cupos: "Falta 1 jugador", "Faltan 2 jugadores".
  const unSoloCupo = partido.cupos_faltantes === 1
  return (
    <article className="tarjeta">
      <div className="tarjeta-cabecera">
        <span className="tipo">{partido.tipo}</span>
        <strong>{formatearFecha(partido.inicio)}</strong>
        <span className="suave">({partido.duracion_minutos} min)</span>
        <Estado estado={partido.estado} />
      </div>
      <p>
        <strong>{complejo.nombre}</strong> · {complejo.direccion},{' '}
        {complejo.localidad} ({complejo.zona})
      </p>
      <p>
        {unSoloCupo ? 'Falta' : 'Faltan'}{' '}
        <strong>{partido.cupos_faltantes}</strong> jugador
        {unSoloCupo ? '' : 'es'} · Organiza{' '}
        {organizador.nombre} ({textoPuntuacion(organizador.puntuacion_promedio)})
      </p>
      {children && <div className="acciones">{children}</div>}
    </article>
  )
}
