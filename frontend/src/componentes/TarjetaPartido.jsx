import { formatearFecha, textoPuntuacion } from '../formato.js'
import Estado from './Estado.jsx'

// Datos de un partido (PartidoPublico de la API). `children` son las
// acciones que cada pantalla le agrega abajo (postularse, cancelar, etc.).
export default function TarjetaPartido({ partido, children }) {
  const { complejo, organizador } = partido
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
        Faltan <strong>{partido.cupos_faltantes}</strong> jugador
        {partido.cupos_faltantes === 1 ? '' : 'es'} · Organiza{' '}
        {organizador.nombre} ({textoPuntuacion(organizador.puntuacion_promedio)})
      </p>
      {children && <div className="acciones">{children}</div>}
    </article>
  )
}
