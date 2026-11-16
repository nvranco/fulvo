// Ayudas de presentación compartidas por las pantallas.

// Copia de JUGADORES_POR_TIPO en fulvo/models.py: el máximo de cupos
// faltantes es el total menos uno (el organizador juega). La API lo vuelve a
// controlar; acá solo sirve para limitar el formulario.
export const JUGADORES_POR_TIPO = { F5: 10, F7: 14, F8: 16, F11: 22 }
export const TIPOS = Object.keys(JUGADORES_POR_TIPO)

export const POSICIONES = ['Arquero', 'Defensor', 'Mediocampista', 'Delantero']

export const ETIQUETA_ESTADO = {
  abierto: 'Abierto',
  completo: 'Completo',
  jugado: 'Jugado',
  cancelado: 'Cancelado',
  en_espera: 'En espera',
  aceptada: 'Aceptada',
  rechazada: 'Rechazada',
  retirada: 'Retirada',
  revocada: 'Revocada',
}

// La API devuelve las fechas en hora de Argentina y sin zona horaria
// ("2026-11-18T20:00:00"). Se formatean partiendo el texto, sin pasar por
// `Date`, para que el navegador no les aplique su propia zona horaria.
export function formatearFecha(texto) {
  const [fecha, hora = ''] = texto.split('T')
  const [anio, mes, dia] = fecha.split('-')
  return `${dia}/${mes}/${anio} ${hora.slice(0, 5)}`.trim()
}

// Valor mínimo para un <input type="datetime-local">: ahora, en hora local.
export function ahoraParaInput() {
  const ahora = new Date()
  ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset())
  return ahora.toISOString().slice(0, 16)
}

export function linkWhatsapp(numero) {
  return `https://wa.me/${numero.replace(/\D/g, '')}`
}

export function textoPuntuacion(puntuacion) {
  return puntuacion == null ? 'sin votos' : `${puntuacion.toFixed(1)} ★`
}

// La API no tiene un listado de "mis partidos" para el organizador, y
// GET /partidos trae solo los abiertos. Por eso el front recuerda los ids
// de los partidos que el usuario publicó desde este navegador.
function clavePublicados(usuarioId) {
  return `fulvo_partidos_publicados_${usuarioId}`
}

export function partidosPublicados(usuarioId) {
  return JSON.parse(localStorage.getItem(clavePublicados(usuarioId)) ?? '[]')
}

export function recordarPartidoPublicado(usuarioId, partidoId) {
  const ids = new Set(partidosPublicados(usuarioId))
  ids.add(partidoId)
  localStorage.setItem(clavePublicados(usuarioId), JSON.stringify([...ids]))
}
