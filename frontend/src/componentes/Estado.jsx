import { ETIQUETA_ESTADO } from '../formato.js'

// Etiqueta de color para el estado de un partido o de una postulación.
export default function Estado({ estado }) {
  return (
    <span className={`estado estado-${estado}`}>
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  )
}
