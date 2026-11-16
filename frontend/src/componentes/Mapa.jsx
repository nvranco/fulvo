import { useEffect, useMemo, useState } from 'react'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMapEvents,
} from 'react-leaflet'
import { api } from '../api.js'
import Aviso from './Aviso.jsx'

// Componente sin dibujo: escucha los clicks sobre el mapa.
function ClickEnMapa({ alClick }) {
  useMapEvents({ click: (e) => alClick([e.latlng.lat, e.latlng.lng]) })
  return null
}

// Mapa de complejos (RQ3). Verde: tiene partidos abiertos. Con un click se
// marca un punto y se buscan las canchas cercanas con /complejos/cercanos.
// Se usan CircleMarker y no Marker: los íconos de Leaflet necesitan
// configuración extra con Vite, y los círculos permiten pintar por estado.
export default function Mapa({ alVerPartidos, alPublicar }) {
  const [complejos, setComplejos] = useState([])
  const [partidosPorComplejo, setPartidosPorComplejo] = useState({})
  const [punto, setPunto] = useState(null)
  const [radio, setRadio] = useState(3)
  const [cercanos, setCercanos] = useState([])
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    Promise.all([api.complejos(), api.partidos()])
      .then(([datosComplejos, datosPartidos]) => {
        setComplejos(datosComplejos.complejos)
        const conteo = {}
        for (const partido of datosPartidos.partidos) {
          const id = partido.complejo.id
          conteo[id] = (conteo[id] ?? 0) + 1
        }
        setPartidosPorComplejo(conteo)
      })
      .catch((error) => setAviso({ tipo: 'error', texto: error.message }))
  }, [])

  useEffect(() => {
    if (!punto) return
    api
      .cercanos(punto[0], punto[1], radio)
      .then(setCercanos)
      .catch((error) => setAviso({ tipo: 'error', texto: error.message }))
  }, [punto, radio])

  const idsCercanos = useMemo(
    () => new Set(cercanos.map((c) => c.id)),
    [cercanos],
  )

  // El mapa arranca centrado en el promedio de los complejos.
  const centro = useMemo(() => {
    if (complejos.length === 0) return null
    const suma = complejos.reduce(
      (acc, c) => [acc[0] + c.latitud, acc[1] + c.longitud],
      [0, 0],
    )
    return [suma[0] / complejos.length, suma[1] / complejos.length]
  }, [complejos])

  function limpiarBusqueda() {
    setPunto(null)
    setCercanos([])
  }

  if (!centro) {
    return (
      <>
        <Aviso aviso={aviso} />
        {!aviso && <p className="cargando">Cargando canchas…</p>}
      </>
    )
  }

  return (
    <div className="mapa-layout">
      <aside className="panel">
        <h2>Canchas</h2>
        <p>
          {complejos.length} complejos.{' '}
          <span className="punto punto-verde" /> con partidos abiertos,{' '}
          <span className="punto punto-gris" /> sin partidos.
        </p>
        <Aviso aviso={aviso} />

        <h3>Buscar cercanas</h3>
        <p className="ayuda">Hacé click en el mapa para marcar un punto.</p>
        <label>
          Radio: <strong>{radio} km</strong>
          <input
            type="range"
            min="1"
            max="20"
            value={radio}
            onChange={(e) => setRadio(Number(e.target.value))}
          />
        </label>

        {punto && (
          <>
            {cercanos.length === 0 ? (
              <p className="suave">No hay canchas en ese radio.</p>
            ) : (
              <ul className="lista-cercanos">
                {cercanos.map((c) => (
                  <li key={c.id}>
                    <div>
                      <strong>{c.nombre}</strong>
                      <span className="suave"> · {c.distancia_km} km</span>
                    </div>
                    <button className="chico" onClick={() => alVerPartidos(c)}>
                      Partidos ({partidosPorComplejo[c.id] ?? 0})
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button className="secundario" onClick={limpiarBusqueda}>
              Limpiar búsqueda
            </button>
          </>
        )}
      </aside>

      <MapContainer center={centro} zoom={12} className="mapa">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickEnMapa alClick={setPunto} />

        {punto && (
          <Circle
            center={punto}
            radius={radio * 1000}
            interactive={false}
            pathOptions={{ color: '#2563eb', fillOpacity: 0.08 }}
          />
        )}

        {complejos.map((c) => {
          const cantidad = partidosPorComplejo[c.id] ?? 0
          const cerca = idsCercanos.has(c.id)
          return (
            <CircleMarker
              key={c.id}
              center={[c.latitud, c.longitud]}
              radius={cerca ? 11 : 8}
              // Que el click en una cancha no mueva el punto de búsqueda.
              bubblingMouseEvents={false}
              pathOptions={{
                color: cerca ? '#1d4ed8' : '#14532d',
                weight: cerca ? 3 : 1.5,
                fillColor: cantidad > 0 ? '#22c55e' : '#9ca3af',
                fillOpacity: 0.9,
              }}
            >
              <Popup>
                <div className="popup">
                  <strong>{c.nombre}</strong>
                  <div>
                    {c.direccion}, {c.localidad}
                  </div>
                  <div className="suave">
                    {c.zona} · {c.tipo}
                    {c.calificacion_maps != null && ` · ⭐ ${c.calificacion_maps}`}
                  </div>
                  <p>
                    <strong>{cantidad}</strong> partido
                    {cantidad === 1 ? '' : 's'} abierto{cantidad === 1 ? '' : 's'}
                  </p>
                  <div className="acciones">
                    <button className="chico" onClick={() => alVerPartidos(c)}>
                      Ver partidos
                    </button>
                    <button
                      className="chico secundario"
                      onClick={() => alPublicar(c)}
                    >
                      Publicar acá
                    </button>
                  </div>
                  {c.link_maps && (
                    <a href={c.link_maps} target="_blank" rel="noreferrer">
                      Abrir en Google Maps
                    </a>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  )
}
