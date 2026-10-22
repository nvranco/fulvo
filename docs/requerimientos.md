# Requerimientos — Fulvo (MVP)

Objetivo del MVP: validar si la gente pide jugadores extra para completar partidos. Todo lo que no ayuda a probar eso queda fuera (ver sección 7).

## 1. Alcance

Entra:

- Registro, login y perfil (sin verificación de cuenta).
- Zonas y complejos (carga inicial por scraping).
- Partidos con cupos faltantes.
- Postulación, aceptación y WhatsApp mutuo.
- Cancelaciones.
- Votaciones, no-show y bloqueo por deuda.
- Notificaciones in-app.
- Admin mínimo.

No entra: verificación de cuenta, pagos, comisión, reservas, canchas suscriptas, mapa, amigos, lobbies, chat, torneos, alta de complejos por usuarios. Ver sección 7.

Región inicial: Argentina, español, edad mínima 16.

## 2. Roles

| Rol | Qué hace |
|---|---|
| Usuario | Organiza partidos, se postula, vota, presenta reclamos. Mismo usuario puede ser organizador o jugador según el partido. |
| Admin | Bloquea usuarios, edita zonas y complejos, resuelve reclamos. |

Roles se guardan en una tabla `roles` referenciada por el usuario, no como booleano. Los permisos se validan por rol en un solo punto. Agregar un rol nuevo (dueño de complejo, organizador de torneos) no cambia el modelo de usuario. Ver sección 7.

## 3. Requerimientos funcionales

| RQ | Requerimiento |
|---|---|
| RQ1 | Registrarse e iniciar sesión. Email y contraseña, edad mínima 16. Sin verificación de cuenta en el MVP. |
| RQ2 | Perfil: nombre, WhatsApp, fecha de nacimiento, posición. Puntuación promedio y partidos jugados son calculados, solo lectura. Perfil público muestra nombre, posición, puntuación y partidos jugados. |
| RQ3 | Ver zonas y complejos. |
| RQ4 | Publicar partido: complejo, fecha, hora, tipo (F5/F7/F11), cupos faltantes. |
| RQ5 | Listar partidos abiertos con filtros por zona, complejo y tipo. Postularse a un partido. |
| RQ6 | Organizador ve la lista de espera, acepta, rechaza o revoca postulantes. Al aceptar, organizador y aceptado se ven el WhatsApp mutuamente. |
| RQ7 | Cancelar: postulante retira postulación, organizador cancela partido, aceptado se baja, organizador revoca aceptado. |
| RQ8 | Votar al terminar el partido (0 a 5 estrellas a jugadores y complejo). Organizador marca no-show. Bloqueo por deuda de votaciones. |
| RQ9 | Notificaciones in-app. |
| RQ10 | Admin: bloquear y desbloquear usuarios, editar zonas y complejos. |
| RQ11 | Reclamos: el usuario reclama por un no-show o una votación. El admin lista los reclamos y los resuelve (anula o rechaza). |

## 4. Reglas de negocio

**Partido**

- Una sola entidad: partido con cupos. No hay "alerta" aparte.
- Datos: organizador, complejo, fecha y hora, tipo, cupos faltantes, estado.
- El grupo del organizador no son usuarios del sistema. Solo se guarda cuántos faltan.
- Un partido publicado no se edita: se cancela y se crea otro.
- Se permite postularse a partidos que se solapan en horario.
- Organizador no puede postularse a su propio partido.
- Usuario no puede postularse dos veces al mismo partido.
- Estados:

| Estado | Cómo se llega |
|---|---|
| abierto | Al publicar, o al liberarse un cupo. |
| completo | Cupos faltantes llega a 0. Postulaciones en espera pasan a rechazadas y se notifica. |
| jugado | Pasa la fecha y hora del partido (automático). |
| cancelado | Organizador cancela. |

**Postulación**

- Estados: en espera, aceptada, rechazada, retirada, revocada.
- Orden de la lista de espera: puntuación promedio descendente. Sin puntuación al final. Desempate por orden de llegada.
- Aceptar resta 1 cupo. Baja o revocación suma 1 cupo y reabre el partido.

**WhatsApp**

- Solo se expone mientras la postulación está aceptada, y solo entre organizador y aceptado. Si se revoca o el aceptado se baja, se deja de exponer.
- Ningún listado público ni endpoint ajeno devuelve el número.

**Votación**

- Participantes del partido: organizador y aceptados.
- Cada participante vota a los demás participantes y al complejo, de 0 a 5 estrellas.
- Solo el organizador puede marcar no-show a un aceptado. El no-show baja la puntuación del ausente y no suma partido jugado.
- Sin ventana de votación: se puede votar en cualquier momento.
- Partidos jugados: al pasar el partido a jugado se suma 1 a cada participante. Si el organizador marca no-show, se resta 1 al ausente y se eliminan sus votaciones pendientes.
- Puntuación promedio se recalcula con cada voto.

**Bloqueo por deuda**

- Deuda = cantidad de partidos jugados con votaciones sin completar.
- Si deuda es mayor que X, el usuario no puede publicar partidos ni postularse. La respuesta informa cuántas votaciones debe completar.
- X = 3. Valor fijo en configuración, no editable desde admin en el MVP.

**Reclamo**

- Lo crea un usuario sobre un no-show recibido o una votación recibida.
- Datos: autor, partido, objetivo (no-show o votación), motivo, estado, resolución.
- Estados: abierto, resuelto (anulado), rechazado.
- Anular un no-show suma 1 partido jugado, quita la marca y recalcula la puntuación. Anular una votación la elimina y recalcula la puntuación.
- Solo el admin resuelve.

**Roles**

- Todo usuario tiene un rol. Por defecto `usuario`.
- Primer admin y roles base se crean con el script de carga inicial. Credenciales del admin por variables de entorno.
- Ningún endpoint público asigna el rol admin.

**Zonas y complejos**

- Un complejo pertenece a una zona.
- Se cargan con un script de scraping, fuera de la API.
- Usuarios no crean ni editan complejos. Solo el admin edita.

## 5. Requerimientos no funcionales

- Contraseñas hasheadas con argon2. Login con JWT.
- Edad mínima 16 validada al registrar.
- WhatsApp protegido según la sección 4.
- Errores por excepciones con mensajes claros.
- API RESTful.
- Al menos 10 tests unitarios y GitHub Action que los corre.

## 6. Preguntas abiertas

Ninguna por ahora.

## 7. Post-MVP

Ideas en alto nivel. La columna de diseño marca por qué se pensó el MVP para que esto entre después sin reescribir. Patrones son candidatos, se eligen al armar el UML.

| Idea | Qué es | Impacto en el diseño del MVP | Patrón candidato |
|---|---|---|---|
| Pagos y comisión | Pasarela de pagos. Comisión del 5% del valor de la cancha, dividida entre organizador y jugador. | Aceptar postulación debe ser un paso aislado donde se pueda enganchar un cobro. | Strategy / Adapter (pasarela intercambiable) |
| Reservas y canchas suscriptas | Disponibilidad horaria, precio, reserva con pago por transferencia, retención atómica del horario. | Complejo hoy es un registro simple. Debe poder ganar canchas, precios y turnos. | State (ciclo de vida de reserva) |
| Notificaciones multicanal | Email, push, WhatsApp. | Notificar pasa por un solo punto. Hoy escribe en tabla in-app. | Observer + Adapter por canal |
| Mapa y geolocalización | Canchas cercanas por ubicación. | Acceso a complejos detrás de una capa propia, para cambiar el criterio de búsqueda. | Repository |
| Alta de complejos por usuarios | Usuario carga complejo faltante y admin aprueba. | Complejo necesita campo de estado de aprobación. | State |
| Scraping automático | Actualización periódica de complejos. | Carga hoy es un script aislado, no código de la API. | Adapter / Factory por fuente |
| Reputación avanzada | Otros algoritmos de puntuación, pesos, penalizaciones por no-show. | Cálculo de puntuación en un solo lugar. | Strategy |
| Amigos y lobbies | Red de amigos, invitaciones, grupo previo al partido. | Partido no asume que todos entran por postulación. | Mediator / Composite |
| Chat | Chat por partido o entre amigos. | Sin impacto directo. | Observer / Pub-Sub |
| Moderación | Denuncias a usuarios y contenido, bloqueos, soporte. | Reclamo ya existe con estados. Se generaliza a denuncia. | Command (acciones auditables) |
| Ligas y torneos | Fixture automático, tabla de posiciones. | Sin impacto directo. | Strategy (formatos de fixture) / Builder |
| Roles extra | Dueño de complejo, organizador de torneos. | Tabla `roles` y permisos por rol en un solo punto, para sumar roles sin tocar usuario. | Strategy (política de permisos por rol) / Factory (alta de usuario según rol) |

## 8. Archivos relacionados

- Diagramas de secuencia: [`diagramas/`](diagramas/)
- Consigna: [`consigna.pdf`](consigna.pdf)
