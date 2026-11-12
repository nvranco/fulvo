# Requerimientos — Fulvo (MVP)

Objetivo del MVP: validar si la gente pide jugadores extra para completar partidos. Todo lo que no ayuda a probar eso queda fuera (ver sección 6).

## 1. Alcance

Entra:

- Registro, login y perfil (sin verificación de cuenta).
- Zonas y complejos con ubicación en mapa (carga inicial por scraping).
- Partidos con cupos faltantes.
- Postulación, aceptación y WhatsApp mutuo.
- Cancelaciones.
- Votaciones, no-show y bloqueo por deuda.
- Notificaciones in-app.
- Admin mínimo.

No entra: verificación de cuenta, monetización (comisiones, suscripciones, pagos), reservas, amigos, lobbies, chat, torneos, alta de complejos por usuarios. Ver sección 6.

Región inicial: Argentina, español, edad mínima 16.

## 2. Roles

| Rol | Qué hace |
|---|---|
| Usuario | Organiza partidos, se postula, vota, presenta reclamos. Mismo usuario puede ser organizador o jugador según el partido. |
| Admin | Bloquea usuarios, edita zonas y complejos, resuelve reclamos. |

Roles se guardan en una tabla `roles` referenciada por el usuario, no como booleano. Los permisos se validan por rol en un solo punto. Agregar un rol nuevo (dueño de complejo, organizador de torneos) no cambia el modelo de usuario. Ver sección 6.

## 3. Requerimientos funcionales

| RQ | Requerimiento | Diagrama |
|---|---|---|
| RQ1 | Registrarse e iniciar sesión. Email y contraseña, edad mínima 16. Sin verificación de cuenta en el MVP. | [01](diagramas/01-registro-y-login.md) |
| RQ2 | Perfil: nombre, apellido, WhatsApp, fecha de nacimiento, posición. Puntuación promedio y partidos jugados son calculados, solo lectura. Perfil público muestra nombre, posición, puntuación y partidos jugados. El apellido no es público. | — |
| RQ3 | Ver zonas y complejos. Cada complejo tiene ubicación (latitud y longitud) para mostrarlo en un mapa y buscar los que están dentro de un radio en km alrededor de un punto, ordenados por distancia. | — |
| RQ4 | Publicar partido: complejo, fecha, hora, tipo (F5/F7/F8/F11) y cupos faltantes. La duración es fija: 60 minutos. | [02](diagramas/02-publicar-partido-y-postularse.md) |
| RQ5 | Listar partidos abiertos con filtros por zona, complejo y tipo. Postularse a un partido. | [02](diagramas/02-publicar-partido-y-postularse.md) |
| RQ6 | Organizador ve la lista de espera, acepta, rechaza o revoca postulantes. Al aceptar, organizador y aceptado se ven el WhatsApp mutuamente. | [03](diagramas/03-aceptar-jugador-y-whatsapp.md) |
| RQ7 | Cancelar: postulante retira postulación, organizador cancela partido, aceptado se baja, organizador revoca aceptado. | [04](diagramas/04-cancelaciones.md) |
| RQ8 | Votar al terminar el partido (0 a 5 estrellas a jugadores y complejo). Organizador marca no-show. Bloqueo por deuda de votaciones. | [05](diagramas/05-votacion-post-partido.md) |
| RQ9 | Notificaciones in-app. | — |
| RQ10 | Admin: bloquear y desbloquear usuarios (queda registrada la sanción), editar zonas y complejos. | [06](diagramas/06-reclamos-y-admin.md) |
| RQ11 | Reclamos: el usuario reclama por un no-show o una votación recibida, o denuncia a un usuario o a un complejo. El admin lista los reclamos y los resuelve (resuelto o rechazado). | [06](diagramas/06-reclamos-y-admin.md) |

## 4. Reglas de negocio

**Perfil**

- Cada usuario ve y edita su perfil propio con todos sus datos.
- Se pueden editar nombre, apellido, WhatsApp, fecha de nacimiento y posición, y se cambia solo lo que se envía. Email y contraseña no se editan en el MVP.
- Una fecha de nacimiento nueva tiene que respetar la edad mínima de 16, igual que al registrarse.
- El perfil público se muestra solo a usuarios con sesión iniciada. No incluye apellido, WhatsApp, email ni fecha de nacimiento.

**Partido**

- Una sola entidad: partido con cupos. No hay "alerta" aparte.
- Datos: organizador, complejo, fecha y hora, duración en minutos (siempre 60: el organizador no la elige), tipo, cupos faltantes, estado.
- La fecha y la hora son de Argentina. Si llegan con otra zona horaria, se convierten.
- Solo se publica un partido que empieza en el futuro.
- Cupos faltantes: como mínimo 1 y como máximo los jugadores del tipo menos el organizador, que también juega. F5 hasta 9, F7 hasta 13, F8 hasta 15 y F11 hasta 21.
- El listado de partidos abiertos muestra solo los que todavía no empezaron, del más próximo al más lejano. El listado y el detalle piden sesión iniciada, porque muestran el perfil público del organizador.
- El grupo del organizador no son usuarios del sistema. Solo se guarda cuántos faltan.
- Un partido publicado no se edita: se cancela y se crea otro.
- El pase a jugado se revisa cada vez que se consulta el partido. No hay tarea periódica. También se revisan los partidos de un usuario que ya terminaron antes de listar sus votaciones o de calcular su deuda: si nadie los consultó, todavía no tienen votaciones.
- Se permite postularse a partidos que se solapan en horario.
- No se puede postular a un partido que ya empezó.
- Organizador no puede postularse a su propio partido.
- Usuario no puede postularse dos veces al mismo partido, aunque se haya retirado, lo hayan rechazado o revocado, o el partido se reabra.
- Estados:

| Estado | Cómo se llega |
|---|---|
| abierto | Al publicar, o al liberarse un cupo. |
| completo | Cupos faltantes llega a 0. Postulaciones en espera pasan a rechazadas y se notifica. |
| jugado | Termina el partido: pasan su fecha y hora de inicio más su duración (automático). |
| cancelado | Organizador cancela. |

**Postulación**

- Estados: en espera, aceptada, rechazada, retirada, revocada.
- Guarda cuándo se creó y cuándo respondió el organizador (al aceptar, rechazar o revocar).
- Orden de la lista de espera: puntuación promedio descendente. Sin puntuación al final. Desempate por orden de llegada.
- Aceptar resta 1 cupo. Baja o revocación suma 1 cupo y reabre el partido.

**WhatsApp**

- Solo se expone mientras la postulación está aceptada, y solo entre organizador y aceptado. Si se revoca, el aceptado se baja o el partido se cancela, se deja de exponer.
- Ningún listado público ni endpoint ajeno devuelve el número. Cada usuario ve el suyo en su perfil propio.

**Votación**

- Participantes del partido: organizador y aceptados.
- Cada participante vota a los demás participantes y al complejo, de 0 a 5 estrellas. Las votaciones se crean pendientes al pasar el partido a jugado.
- Un voto emitido no se cambia.
- Solo el organizador puede marcar no-show a un aceptado, y solo con el partido ya jugado: antes no hay votaciones ni partido jugado que deshacer (decisión del 2026-11-11). El no-show cuenta como un voto de 0 estrellas en la puntuación del ausente y no suma partido jugado. El organizador no lo puede desmarcar: eso se pide con un reclamo (RQ11).
- Sin ventana de votación: se puede votar en cualquier momento. El no-show tampoco tiene límite de tiempo.
- Partidos jugados: al pasar el partido a jugado se suma 1 a cada participante. Si el organizador marca no-show, se resta 1 al ausente y se eliminan sus votaciones pendientes y también las que los demás tenían hacia él: no jugó, y el no-show ya cuenta como su voto (decisión del 2026-11-11). Las votaciones ya emitidas quedan.
- Puntuación promedio se recalcula con cada voto, tanto la del usuario como la del complejo.
- Cada votación guarda cuándo se emitió.
- Cada usuario ve los votos que recibió (emitidos o anulados), con las estrellas y el partido, pero sin saber quién votó (decisión del 2026-11-12). Los necesita para reclamar uno (RQ11).
- Si el admin le da la razón a un reclamo por una votación, el voto queda anulado: deja de contar en la puntuación, pero no se borra (decisión del 2026-11-12).

**Bloqueo por deuda**

- Deuda = cantidad de partidos jugados con votaciones sin completar. Cuenta por partido: un partido con varios votos pendientes suma 1.
- Si deuda es mayor que X, el usuario no puede publicar partidos ni postularse. La API responde 409, como las demás reglas del dominio, con un mensaje que dice en cuántos partidos debe votos, en cuántos tiene que completarlos para volver a estar habilitado y cuántas votaciones le faltan en total (decisión del 2026-11-11). Por ejemplo: "Tenés votaciones pendientes en 4 partidos y el máximo es 3: completá las de al menos 1 partido para publicar o postularte (te faltan 9 votaciones)."
- El perfil propio muestra la deuda y si el usuario está habilitado para publicar y postularse.
- X = 3. Valor fijo en configuración (`LIMITE_DEUDA`, en `fulvo/settings.py`), no editable desde admin en el MVP.

**Notificación**

- Se guardan en la app, con destinatario, tipo, mensaje, referencia a lo que las originó y marca de leída.
- Tipos:
  - Postulación recibida (al organizador).
  - Postulación aceptada y postulación rechazada (al jugador).
  - Partido completo (a cada postulante en espera, que pasa a rechazado).
  - Postulación retirada, incluida la baja de un aceptado (un solo tipo, al organizador).
  - Revocación (al jugador).
  - Partido cancelado (a postulantes y aceptados).
  - Votaciones pendientes.
  - Votaciones repuestas (a los presentes, cuando un reclamo anula un no-show).
  - Reclamo resuelto (al autor).
- Cada usuario ve solo sus notificaciones, de la más nueva a la más vieja, y las marca como leídas de a una.
- El texto nunca incluye el WhatsApp: si después se revoca al jugador o se cancela el partido, el número no queda guardado en la notificación (decisión del 2026-11-11). El aviso de aceptación dice dónde verlo.
- "Votaciones pendientes" se crea al pasar el partido a jugado, para cada participante (RQ8).
- "Votaciones repuestas" se crea cuando un reclamo anula un no-show, para los participantes que vinieron, incluido el que había quedado como ausente: vuelven a deber votos de ese partido (decisión del 2026-11-12). No dice quién era el ausente.
- "Reclamo resuelto" le avisa al autor que el admin respondió, tanto si lo resolvió como si lo rechazó (como en el diagrama 06): dice cómo terminó y la respuesta del admin.

**Reclamo**

- Lo crea un usuario sobre un no-show recibido, una votación recibida, otro usuario (denuncia) o un complejo (denuncia).
- El no-show tiene que ser del autor y estar marcado. La votación tiene que haberla recibido el autor y estar emitida: una pendiente todavía no tiene estrellas.
- No se puede denunciar a uno mismo.
- No se puede abrir un reclamo sobre un objetivo que ya tiene un reclamo abierto del mismo autor. Uno resuelto o rechazado no cuenta: se puede volver a reclamar.
- Datos: autor, objetivo (tipo y referencia: no-show, votación, usuario o complejo), motivo, estado, resolución, admin que resolvió. El partido se obtiene desde el objetivo.
- Estados: abierto, resuelto, rechazado.
- Cada usuario ve sus reclamos. El admin ve los de todos y los puede filtrar por estado (decisión del 2026-11-12).
- El admin no recibe aviso por un reclamo nuevo: ve los reclamos abiertos en su listado.
- Resolver como resuelto aplica una medida según el objetivo:
  - No-show: suma 1 partido jugado, quita la marca, quita el voto de 0 estrellas y recalcula la puntuación. Además se reponen las votaciones que se habían borrado al marcarlo: él vuelve a deber las suyas y los demás presentes pueden votarlo, como si el no-show no hubiera existido (decisión del 2026-11-12).
  - Votación: queda anulada y deja de contar en la puntuación. No se borra: el reclamo sigue apuntando a ella (decisión del 2026-11-12).
  - Usuario: al resolver, el admin elige si lo bloquea. Si lo bloquea, la sanción queda unida al reclamo, con la respuesta del admin como motivo, y pasa lo mismo que en cualquier bloqueo (decisión del 2026-11-12).
  - Complejo: ninguna medida automática; el admin puede editar sus datos.
- Rechazar no aplica ninguna medida. Un reclamo resuelto o rechazado no se vuelve a responder.
- Solo el admin resuelve.

**Sanción**

- Cada bloqueo de usuario queda registrado: usuario, admin que lo aplicó, motivo, fecha de inicio y reclamo de origen (opcional).
- Bloquear crea la sanción y marca al usuario como bloqueado. Desbloquear cierra la sanción con su fecha de fin.
- Un usuario bloqueado no puede iniciar sesión, y el token que ya tenía deja de servir en ese momento: la API vuelve a leer al usuario en cada pedido.
- Solo el admin bloquea y desbloquea, y solo a usuarios comunes: bloquear a un admin, incluido uno mismo, da 409, porque la app podría quedarse sin nadie que desbloquee (decisión del 2026-11-12).
- Un usuario tiene una sola sanción activa: bloquearlo de nuevo da 409. Si se lo desbloquea y después se lo vuelve a bloquear, se crea otra sanción, así cada bloqueo queda registrado aparte. El admin ve el historial de cada usuario, de la sanción más nueva a la más vieja.
- Al bloquear se cancelan los partidos que organiza y se retiran sus postulaciones en espera o aceptadas, solo en partidos que todavía no empezaron: un bloqueado ya no puede aceptar jugadores ni coordinar. Los afectados reciben las notificaciones de siempre (partido cancelado y postulación retirada). Los partidos que ya empezaron o se jugaron no cambian, y desbloquear no restaura nada (decisión del 2026-11-12).

**Roles**

- Todo usuario tiene un rol. Por defecto `usuario`.
- Primer admin y roles base se crean con el script de carga inicial. Credenciales del admin por variables de entorno.
- Ningún endpoint público asigna el rol admin.

**Zonas y complejos**

- Una zona tiene nombre y provincia. Es un partido o un barrio; la localidad se guarda en cada complejo.
- Un complejo pertenece a una zona.
- Datos del complejo: nombre, dirección, localidad, latitud, longitud, teléfono, WhatsApp y email de contacto, tipo, si tiene reserva online, sitio web, link a Google Maps y calificación de Maps. Ubicación y contactos salen de la carga inicial. La provincia del complejo es la de su zona.
- El complejo tiene puntuación promedio y cantidad de puntuaciones, calculadas por las votaciones.
- La búsqueda de cercanos recibe un punto (latitud y longitud) y un radio en km. Devuelve los complejos dentro del radio, ordenados por distancia.
- Los datos iniciales salen de un CSV (`fulvo/datos/complejos.csv`, armado a mano desde Google Maps) que la API carga al arrancar. También se pueden agregar zonas y complejos con la API.
- Usuarios no crean ni editan complejos. Solo el admin edita. Las altas, ediciones y bajas exigen rol admin; las lecturas son públicas.
- Un complejo con partidos no se puede borrar. La API responde 409 con el mensaje "Error al borrar el complejo: aún tiene partidos agendados". Cuenta cualquier partido del complejo, también los jugados y los cancelados, porque siguen apuntando a él.

## 5. Requerimientos no funcionales

- Contraseñas hasheadas con argon2. Login con JWT.
- Edad mínima 16 validada al registrar.
- WhatsApp protegido según la sección 4.
- Errores por excepciones con mensajes claros. Una acción que las reglas no permiten (por ejemplo, aceptar una postulación ya rechazada) responde 409 con el motivo.
- API RESTful.
- Al menos 10 tests unitarios y GitHub Action que los corre.

## 6. Post-MVP

Ideas en alto nivel. La columna de impacto marca por qué se pensó el MVP para que esto entre después sin reescribir.

| Idea | Qué es | Impacto en el diseño del MVP |
|---|---|---|
| Monetización | Cobro de comisiones y suscripciones, con pasarela de pagos. Quién paga, cuánto y por qué evento queda sin definir. | Los hechos de negocio (partido publicado, postulación aceptada, partido jugado) pasan por un solo punto y quedan registrados, para poder asociarles un cobro sin tocar la lógica existente. Usuario y complejo no asumen ser gratuitos. |
| Reservas de canchas | Disponibilidad horaria, precio, reserva con pago por transferencia, retención atómica del horario. | Complejo hoy es un registro simple. Debe poder ganar canchas, precios y turnos. |
| Notificaciones multicanal | Email, push, WhatsApp. | Notificar pasa por un solo punto. Hoy escribe en tabla in-app. |
| Alta de complejos por usuarios | Usuario carga complejo faltante y admin aprueba. | Complejo necesita campo de estado de aprobación. |
| Scraping automático | Actualización periódica de complejos. | Carga hoy es un script aislado, no código de la API. |
| Reputación avanzada | Otros algoritmos de puntuación, pesos, penalizaciones por no-show. | Cálculo de puntuación en un solo lugar. |
| Amigos y lobbies | Red de amigos, invitaciones, grupo previo al partido. | Partido no asume que todos entran por postulación. |
| Chat | Chat por partido o entre amigos. | Sin impacto directo. |
| Moderación avanzada | Denuncias sobre contenido (chat, comentarios) y soporte. | Reclamo y sanción ya existen con estados. Se generalizan. |
| Ligas y torneos | Fixture automático, tabla de posiciones. | Sin impacto directo. |
| Roles extra | Dueño de complejo, organizador de torneos. | Tabla `roles` y permisos por rol en un solo punto, para sumar roles sin tocar usuario. |

## 7. Archivos relacionados

- Diagramas de secuencia: [`diagramas/`](diagramas/)
- Clases y patrones de diseño: [`clases.md`](clases.md)
- Consigna: [`consigna.pdf`](consigna.pdf)
