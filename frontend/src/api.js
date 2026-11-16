// Único lugar que habla con la API. Cada pantalla usa las funciones de `api`
// y no arma URLs ni encabezados por su cuenta.

// Vite reenvía /api a FastAPI (ver vite.config.js).
const BASE = '/api'
const CLAVE_TOKEN = 'fulvo_token'

export function leerToken() {
  return localStorage.getItem(CLAVE_TOKEN)
}

export function guardarToken(token) {
  localStorage.setItem(CLAVE_TOKEN, token)
}

export function borrarToken() {
  localStorage.removeItem(CLAVE_TOKEN)
}

export class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje)
    this.status = status
  }
}

// La API responde los errores con `detail`: un texto (HTTPException y los
// 409 de reglas de negocio) o una lista (los 422 de validación de Pydantic).
function mensajeDeError(cuerpo, status) {
  const detail = cuerpo?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((error) => `${error.loc?.slice(1).join('.')}: ${error.msg}`)
      .join(' · ')
  }
  if (status >= 500) {
    return 'La API no responde. ¿Está corriendo `poetry serve`?'
  }
  return `Error ${status}`
}

// Arma la query string salteando los filtros vacíos.
function query(parametros) {
  const limpios = Object.entries(parametros).filter(
    ([, valor]) => valor !== undefined && valor !== null && valor !== '',
  )
  return new URLSearchParams(limpios).toString()
}

async function pedir(ruta, { metodo = 'GET', cuerpo, formulario } = {}) {
  const headers = {}
  const token = leerToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let body
  if (formulario) {
    // El login es OAuth2: va como formulario, no como JSON.
    body = new URLSearchParams(formulario)
  } else if (cuerpo !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(cuerpo)
  }

  let respuesta
  try {
    respuesta = await fetch(BASE + ruta, { method: metodo, headers, body })
  } catch {
    throw new ErrorApi('No se pudo conectar con la API.', 0)
  }

  let datos = null
  try {
    datos = await respuesta.json()
  } catch {
    // Respuesta sin cuerpo JSON (por ejemplo, la API apagada).
  }

  if (!respuesta.ok) {
    // Token vencido o inválido: se cierra la sesión (App escucha el evento).
    if (respuesta.status === 401 && token) {
      borrarToken()
      window.dispatchEvent(new Event('fulvo:sesion-vencida'))
    }
    throw new ErrorApi(mensajeDeError(datos, respuesta.status), respuesta.status)
  }
  return datos
}

// Una función por endpoint, con el RQ que cubre.
export const api = {
  // RQ1
  login: (email, contrasena) =>
    pedir('/auth/token', {
      metodo: 'POST',
      formulario: { username: email, password: contrasena },
    }),
  registrarse: (datos) => pedir('/usuarios', { metodo: 'POST', cuerpo: datos }),
  // RQ2
  miPerfil: () => pedir('/usuarios/yo'),
  // RQ3
  zonas: () => pedir('/zonas'),
  complejos: () => pedir('/complejos?limit=100'),
  cercanos: (latitud, longitud, radio_km) =>
    pedir(`/complejos/cercanos?${query({ latitud, longitud, radio_km })}`),
  // RQ4, RQ5 y RQ7
  partidos: (filtros = {}) =>
    pedir(`/partidos?${query({ limit: 100, ...filtros })}`),
  partido: (id) => pedir(`/partidos/${id}`),
  publicarPartido: (datos) =>
    pedir('/partidos', { metodo: 'POST', cuerpo: datos }),
  cancelarPartido: (id) =>
    pedir(`/partidos/${id}`, { metodo: 'PATCH', cuerpo: { estado: 'cancelado' } }),
  // RQ5 a RQ7
  postularse: (partidoId) =>
    pedir(`/partidos/${partidoId}/postulaciones`, { metodo: 'POST' }),
  postulacionesDelPartido: (partidoId) =>
    pedir(`/partidos/${partidoId}/postulaciones`),
  responderPostulacion: (partidoId, postulacionId, estado) =>
    pedir(`/partidos/${partidoId}/postulaciones/${postulacionId}`, {
      metodo: 'PATCH',
      cuerpo: { estado },
    }),
  // RQ8: solo con el partido jugado.
  marcarNoShow: (partidoId, postulacionId) =>
    pedir(`/partidos/${partidoId}/postulaciones/${postulacionId}`, {
      metodo: 'PATCH',
      cuerpo: { no_show: true },
    }),
  misPostulaciones: () => pedir('/postulaciones?limit=100'),
  retirarPostulacion: (id) =>
    pedir(`/postulaciones/${id}`, {
      metodo: 'PATCH',
      cuerpo: { estado: 'retirada' },
    }),
  // RQ9
  notificaciones: (filtros = {}) =>
    pedir(`/notificaciones?${query({ limit: 100, ...filtros })}`),
  marcarLeida: (id) =>
    pedir(`/notificaciones/${id}`, { metodo: 'PATCH', cuerpo: { leida: true } }),
  // RQ8
  votaciones: (filtros = {}) =>
    pedir(`/votaciones?${query({ limit: 100, ...filtros })}`),
  emitirVotacion: (id, estrellas) =>
    pedir(`/votaciones/${id}`, { metodo: 'PATCH', cuerpo: { estrellas } }),
  // RQ11
  abrirReclamo: (tipo_objetivo, objetivo_id, motivo) =>
    pedir('/reclamos', {
      metodo: 'POST',
      cuerpo: { tipo_objetivo, objetivo_id, motivo },
    }),
  reclamos: (filtros = {}) =>
    pedir(`/reclamos?${query({ limit: 100, ...filtros })}`),
  responderReclamo: (id, estado, resolucion, bloquear = false) =>
    pedir(`/reclamos/${id}`, {
      metodo: 'PATCH',
      cuerpo: { estado, resolucion, bloquear },
    }),
  // RQ10, solo admin
  perfilPublico: (id) => pedir(`/usuarios/${id}`),
  sanciones: (usuarioId) =>
    pedir(`/usuarios/${usuarioId}/sanciones?limit=100`),
  bloquearUsuario: (usuarioId, motivo) =>
    pedir(`/usuarios/${usuarioId}/sanciones`, {
      metodo: 'POST',
      cuerpo: { motivo },
    }),
  desbloquearUsuario: (usuarioId, sancionId) =>
    pedir(`/usuarios/${usuarioId}/sanciones/${sancionId}`, {
      metodo: 'PATCH',
      cuerpo: { activa: false },
    }),
  // El perfil no trae el rol: se prueba una ruta solo de admin (403 si no).
  esAdmin: (usuarioId) =>
    pedir(`/usuarios/${usuarioId}/sanciones?limit=1`).then(
      () => true,
      () => false,
    ),
}
