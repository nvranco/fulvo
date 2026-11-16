import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { TIPOS } from '../formato.js'
import Aviso from './Aviso.jsx'
import Estado from './Estado.jsx'
import TarjetaPartido from './TarjetaPartido.jsx'

// Partidos abiertos con filtros y botón para postularse (RQ5).
export default function Partidos({ usuario, complejo, alQuitarComplejo }) {
  const [zonas, setZonas] = useState([])
  const [zona, setZona] = useState('')
  const [tipo, setTipo] = useState('')
  const [partidos, setPartidos] = useState(null)
  // partido_id -> estado de mi postulación, para no ofrecer postularse dos veces.
  const [misEstados, setMisEstados] = useState({})
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    api
      .zonas()
      .then((datos) => setZonas(datos.zonas))
      .catch(() => {})
  }, [])

  const cargar = useCallback(async () => {
    try {
      const [datos, mias] = await Promise.all([
        api.partidos({ zona, tipo, complejo_id: complejo?.id }),
        api.misPostulaciones(),
      ])
      setPartidos(datos.partidos)
      const estados = {}
      for (const p of mias.postulaciones) estados[p.partido.id] = p.estado
      setMisEstados(estados)
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
    }
  }, [zona, tipo, complejo])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function postularme(partido) {
    setAviso(null)
    try {
      await api.postularse(partido.id)
      setAviso({
        tipo: 'ok',
        texto: `Te postulaste al partido en ${partido.complejo.nombre}. Quedás en espera hasta que el organizador responda.`,
      })
      cargar()
    } catch (error) {
      // Los 409 de reglas de negocio traen el motivo en español.
      setAviso({ tipo: 'error', texto: error.message })
    }
  }

  return (
    <section>
      <h2>Partidos abiertos</h2>
      <div className="filtros">
        <label>
          Zona
          <select value={zona} onChange={(e) => setZona(e.target.value)}>
            <option value="">Todas</option>
            {zonas.map((z) => (
              <option key={z.id} value={z.nombre}>
                {z.nombre}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tipo
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        {complejo && (
          <span className="chip">
            {complejo.nombre}
            <button className="chip-cerrar" onClick={alQuitarComplejo}>
              ×
            </button>
          </span>
        )}
      </div>

      <Aviso aviso={aviso} />

      {partidos === null && <p className="cargando">Cargando partidos…</p>}
      {partidos?.length === 0 && (
        <p className="suave">No hay partidos abiertos con esos filtros.</p>
      )}

      <div className="lista">
        {partidos?.map((partido) => {
          const esMio = partido.organizador.id === usuario.id
          const miEstado = misEstados[partido.id]
          return (
            <TarjetaPartido key={partido.id} partido={partido}>
              {esMio && <span className="suave">Lo organizás vos</span>}
              {!esMio && miEstado && (
                <span>
                  Tu postulación: <Estado estado={miEstado} />
                </span>
              )}
              {!esMio && !miEstado && (
                <button onClick={() => postularme(partido)}>Postularme</button>
              )}
            </TarjetaPartido>
          )
        })}
      </div>
    </section>
  )
}
