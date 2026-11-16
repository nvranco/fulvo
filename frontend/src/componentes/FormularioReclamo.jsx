import { useState } from 'react'
import { api } from '../api.js'
import Aviso from './Aviso.jsx'

// Formulario compacto para abrir un reclamo (RQ11) sobre algo puntual:
// una postulación (no_show), una votación, un usuario o un complejo.
export default function FormularioReclamo({ tipoObjetivo, objetivoId, alTerminar }) {
  const [motivo, setMotivo] = useState('')
  const [aviso, setAviso] = useState(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setAviso(null)
    try {
      const reclamo = await api.abrirReclamo(tipoObjetivo, objetivoId, motivo.trim())
      alTerminar(reclamo)
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
      setEnviando(false)
    }
  }

  return (
    <form className="formulario formulario-reclamo" onSubmit={enviar}>
      <label>
        Motivo
        <textarea
          required
          rows={3}
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
        />
      </label>
      <Aviso aviso={aviso} />
      <div className="acciones">
        <button type="submit" className="chico" disabled={enviando || !motivo.trim()}>
          Enviar reclamo
        </button>
        <button
          type="button"
          className="chico secundario"
          disabled={enviando}
          onClick={() => alTerminar(null)}
        >
          Cancelar
        </button>
      </div>
    </form>
  )
}
