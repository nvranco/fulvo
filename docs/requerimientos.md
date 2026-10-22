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
| RQ2 | Perfil: nombre, apellido, WhatsApp, fecha de nacimiento, posición. Puntuación promedio y partidos jugados son calculados, solo lectura. Perfil público muestra nombre, posición, puntuación y partidos jugados. | — |
| RQ3 | Ver zonas y complejos. Cada complejo tiene ubicación (latitud y longitud) para mostrarlo en un mapa y buscar los que están dentro de un radio en km alrededor de un punto, ordenados por distancia. | — |
| RQ4 | Publicar partido: complejo, fecha, hora, duración, tipo (F5/F7/F8/F11), cupos faltantes. | [02](diagramas/02-publicar-partido-y-postularse.md) |
| RQ5 | Listar partidos abiertos con filtros por zona, complejo y tipo. Postularse a un partido. | [02](diagramas/02-publicar-partido-y-postularse.md) |
| RQ6 | Organizador ve la lista de espera, acepta, rechaza o revoca postulantes. Al aceptar, organizador y aceptado se ven el WhatsApp mutuamente. | [03](diagramas/03-aceptar-jugador-y-whatsapp.md) |
| RQ7 | Cancelar: postulante retira postulación, organizador cancela partido, aceptado se baja, organizador revoca aceptado. | [04](diagramas/04-cancelaciones.md) |
| RQ8 | Votar al terminar el partido (0 a 5 estrellas a jugadores y complejo). Organizador marca no-show. Bloqueo por deuda de votaciones. | [05](diagramas/05-votacion-post-partido.md) |
| RQ9 | Notificaciones in-app. | — |
| RQ10 | Admin: bloquear y desbloquear usuarios (queda registrada la sanción), editar zonas y complejos. | [06](diagramas/06-reclamos-y-admin.md) |
| RQ11 | Reclamos: el usuario reclama por un no-show o una votación recibida, o denuncia a un usuario o a un complejo. El admin lista los reclamos y los resuelve (resuelto o rechazado). | [06](diagramas/06-reclamos-y-admin.md) |

## 4. Reglas de negocio

**Partido**

- Una sola entidad: partido con cupos. No hay "alerta" aparte.
- Datos: organizador, complejo, fecha y hora, duración en minutos (60 por defecto), tipo, cupos faltantes, estado.
- El grupo del organizador no son usuarios del sistema. Solo se guarda cuántos faltan.
- Un partido publicado no se edita: se cancela y se crea otro.
- El pase a jugado se revisa cada vez que se consulta el partido. No hay tarea periódica.
- Se permite postularse a partidos que se solapan en horario.
- Organizador no puede postularse a su propio partido.
- Usuario no puede postularse dos veces al mismo partido.
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

- Solo se expone mientras la postulación está aceptada, y solo entre organizador y aceptado. Si se revoca o el aceptado se baja, se deja de exponer.
- Ningún listado público ni endpoint ajeno devuelve el número.

**Votación**

- Participantes del partido: organizador y aceptados.
- Cada participante vota a los demás participantes y al complejo, de 0 a 5 estrellas.
- Solo el organizador puede marcar no-show a un aceptado. El no-show cuenta como un voto de 0 estrellas en la puntuación del ausente y no suma partido jugado.
- Sin ventana de votación: se puede votar en cualquier momento.
- Partidos jugados: al pasar el partido a jugado se suma 1 a cada participante. Si el organizador marca no-show, se resta 1 al ausente y se eliminan sus votaciones pendientes.
- Puntuación promedio se recalcula con cada voto, tanto la del usuario como la del complejo.
- Cada votación guarda cuándo se emitió.

**Bloqueo por deuda**

- Deuda = cantidad de partidos jugados con votaciones sin completar.
- Si deuda es mayor que X, el usuario no puede publicar partidos ni postularse. La respuesta informa cuántas votaciones debe completar.
- X = 3. Valor fijo en configuración, no editable desde admin en el MVP.

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
  - Reclamo nuevo (al admin) y reclamo resuelto (al autor).

**Reclamo**

- Lo crea un usuario sobre un no-show recibido, una votación recibida, otro usuario (denuncia) o un complejo (denuncia).
- Datos: autor, objetivo (tipo y referencia: no-show, votación, usuario o complejo), motivo, estado, resolución, admin que resolvió. El partido se obtiene desde el objetivo.
- Estados: abierto, resuelto, rechazado.
- Resolver como resuelto aplica una medida según el objetivo:
  - No-show: suma 1 partido jugado, quita la marca, quita el voto de 0 estrellas y recalcula la puntuación.
  - Votación: la elimina y recalcula la puntuación.
  - Usuario: el admin puede bloquearlo (queda una sanción).
  - Complejo: el admin puede editar sus datos.
- Solo el admin resuelve.

**Sanción**

- Cada bloqueo de usuario queda registrado: usuario, admin que lo aplicó, motivo, fecha de inicio y reclamo de origen (opcional).
- Bloquear crea la sanción y marca al usuario como bloqueado. Desbloquear cierra la sanción con su fecha de fin.
- Un usuario bloqueado no puede iniciar sesión.

**Roles**

- Todo usuario tiene un rol. Por defecto `usuario`.
- Primer admin y roles base se crean con el script de carga inicial. Credenciales del admin por variables de entorno.
- Ningún endpoint público asigna el rol admin.

**Zonas y complejos**

- Una zona tiene nombre, localidad y provincia.
- Un complejo pertenece a una zona.
- Datos del complejo: nombre, dirección, latitud, longitud, teléfono, WhatsApp y email de contacto. Ubicación y contactos los carga el script de scraping.
- El complejo tiene puntuación promedio y cantidad de puntuaciones, calculadas por las votaciones.
- El complejo tiene un campo de dueño reservado para el rol de dueño de complejo (post-MVP). En el MVP queda vacío.
- La búsqueda de cercanos recibe un punto (latitud y longitud) y un radio en km. Devuelve los complejos dentro del radio, ordenados por distancia.
- Se cargan con un script de scraping, fuera de la API.
- Usuarios no crean ni editan complejos. Solo el admin edita.

## 5. Requerimientos no funcionales

- Contraseñas hasheadas con argon2. Login con JWT.
- Edad mínima 16 validada al registrar.
- WhatsApp protegido según la sección 4.
- Errores por excepciones con mensajes claros.
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
