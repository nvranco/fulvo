import { useState } from 'react'
import { api, guardarToken } from '../api.js'
import { POSICIONES } from '../formato.js'
import Aviso from './Aviso.jsx'

const REGISTRO_VACIO = {
  email: '',
  contrasena: '',
  nombre: '',
  apellido: '',
  whatsapp: '',
  fecha_nacimiento: '',
  posicion: POSICIONES[0],
}

// Login y registro (RQ1). Después de registrarse se inicia sesión solo.
export default function Acceso({ alEntrar }) {
  const [modo, setModo] = useState('login')
  const [email, setEmail] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [registro, setRegistro] = useState(REGISTRO_VACIO)
  const [aviso, setAviso] = useState(null)
  const [enviando, setEnviando] = useState(false)

  async function entrar(emailLogin, contrasenaLogin) {
    const { access_token } = await api.login(emailLogin, contrasenaLogin)
    guardarToken(access_token)
    alEntrar(await api.miPerfil())
  }

  // Envuelve cada envío: deshabilita el botón y muestra el error de la API.
  async function enviar(evento, accion) {
    evento.preventDefault()
    setEnviando(true)
    setAviso(null)
    try {
      await accion()
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.message })
      setEnviando(false)
    }
  }

  function cambiarCampo(evento) {
    setRegistro({ ...registro, [evento.target.name]: evento.target.value })
  }

  return (
    <div className="acceso">
      <div className="acceso-tarjeta">
        <h1 className="logo">⚽ Fulvo</h1>
        <p className="suave">¿Te falta gente para el partido? Completalo acá.</p>

        <div className="pestanas">
          <button
            className={modo === 'login' ? 'pestana activa' : 'pestana'}
            onClick={() => setModo('login')}
          >
            Ingresar
          </button>
          <button
            className={modo === 'registro' ? 'pestana activa' : 'pestana'}
            onClick={() => setModo('registro')}
          >
            Registrarme
          </button>
        </div>

        <Aviso aviso={aviso} />

        {modo === 'login' ? (
          <form
            className="formulario"
            onSubmit={(e) => enviar(e, () => entrar(email, contrasena))}
          >
            <label>
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Contraseña
              <input
                type="password"
                required
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
              />
            </label>
            <button type="submit" disabled={enviando}>
              Ingresar
            </button>
          </form>
        ) : (
          <form
            className="formulario"
            onSubmit={(e) =>
              enviar(e, async () => {
                await api.registrarse(registro)
                await entrar(registro.email, registro.contrasena)
              })
            }
          >
            <div className="fila">
              <label>
                Nombre
                <input name="nombre" required value={registro.nombre} onChange={cambiarCampo} />
              </label>
              <label>
                Apellido
                <input name="apellido" required value={registro.apellido} onChange={cambiarCampo} />
              </label>
            </div>
            <label>
              Email
              <input name="email" type="email" required value={registro.email} onChange={cambiarCampo} />
            </label>
            <label>
              Contraseña (mínimo 8)
              <input
                name="contrasena"
                type="password"
                required
                minLength={8}
                value={registro.contrasena}
                onChange={cambiarCampo}
              />
            </label>
            <div className="fila">
              <label>
                WhatsApp
                <input
                  name="whatsapp"
                  required
                  placeholder="+5491112345678"
                  value={registro.whatsapp}
                  onChange={cambiarCampo}
                />
              </label>
              <label>
                Fecha de nacimiento
                <input
                  name="fecha_nacimiento"
                  type="date"
                  required
                  value={registro.fecha_nacimiento}
                  onChange={cambiarCampo}
                />
              </label>
            </div>
            <label>
              Posición
              <select name="posicion" value={registro.posicion} onChange={cambiarCampo}>
                {POSICIONES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <p className="ayuda">
              Tu WhatsApp solo lo ve el organizador cuando te acepta en un
              partido (y vos el suyo).
            </p>
            <button type="submit" disabled={enviando}>
              Crear cuenta
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
