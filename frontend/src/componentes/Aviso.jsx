// Mensaje de error o de éxito. `aviso` es { tipo: 'error' | 'ok', texto }.
export default function Aviso({ aviso }) {
  if (!aviso) return null
  return <div className={`aviso aviso-${aviso.tipo}`}>{aviso.texto}</div>
}
