# Clases y patrones de diseño — Fulvo (MVP)

Documento de trabajo del diagrama UML. Se arma clase por clase, y cada decisión queda anotada acá. El alcance sale de [`requerimientos.md`](requerimientos.md). Si algo no está en ese documento, no entra en las clases.

## 1. Clases del MVP

Los identificadores van en español sin tildes ni ñ, como indica `CLAUDE.md`.

### Usuarios y notificaciones

**Usuario** (absorbe el perfil de jugador)

- `id`, `email`, `whatsapp`, `contrasena_hash`, `nombre`, `apellido`, `fecha_nacimiento`
- `posicion`
- `puntuacion_promedio`, `cantidad_puntuaciones`, `partidos_jugados` (calculados, solo lectura)
- `bloqueado`
- `rol` (referencia a `Rol`)

Métodos:

| Método | Qué hace | Regla de la doc |
|---|---|---|
| `edad(hoy)` | Devuelve los años cumplidos. | Edad mínima 16 al registrar. |
| `registrar_puntuacion(estrellas)` | Suma un voto y recalcula `puntuacion_promedio` y `cantidad_puntuaciones`. | El promedio se recalcula con cada voto. |
| `quitar_puntuacion(estrellas)` | Deshace un voto y recalcula. | Anular una votación o un no-show recalcula el promedio. |
| `sumar_partido_jugado()` | Suma 1 a `partidos_jugados`. | Al pasar el partido a jugado, o al anular un no-show. |
| `restar_partido_jugado()` | Resta 1 a `partidos_jugados`. | No-show. |
| `deuda()` | Cuenta los partidos en los que tiene votaciones pendientes. | La deuda cuenta por partido. |
| `habilitado()` | Verdadero si `deuda()` no supera X (3, en `settings.py`). | Bloqueo por deuda: no puede publicar ni postularse. |
| `bloquear(admin, motivo, reclamo)` | Marca `bloqueado` y crea la `Sancion`. | RQ10. |
| `desbloquear()` | Quita `bloqueado` y cierra la `Sancion`. | RQ10. |
| `tiene_rol(nombre)` | Compara su `Rol` con el nombre. | Los permisos se validan por rol en un solo punto. |

Decisiones:

- El no-show cuenta como un voto de 0 estrellas: `registrar_puntuacion(0)`. Anularlo usa `quitar_puntuacion(0)`.
- La deuda se calcula en `Usuario`, no en un servicio aparte. `Partido.postular` solo pregunta `jugador.habilitado()`.
- El bloqueo lo hace `Usuario.bloquear(...)`, que crea la `Sancion`. `Sancion.cerrar()` pone la fecha de fin.
- El contacto del usuario se llama `whatsapp`.
- El `apellido` no se muestra en el perfil público.

**Rol**

- `id`, `nombre`
- Todo usuario tiene un rol, por defecto `usuario`. Roles base: `usuario` y `admin`.
- Sin métodos: es solo un dato. La validación de permisos está en `Usuario.tiene_rol()`.

**Notificacion**

- `id`, `usuario` (destinatario), `tipo`, `mensaje`
- `referencia_tipo`, `referencia_id` (qué la originó, sin clave foránea)
- `leida`, `created_at`
- Tipos: ver sección "Notificación" de `requerimientos.md`. Retirada y baja de un aceptado comparten un solo tipo.

Métodos:

| Método | Qué hace |
|---|---|
| `marcar_leida()` | Pone `leida` en verdadero. |

La `Notificacion` no se construye a mano: la crea `FabricaNotificaciones` (ver sección 3).

### Zonas y complejos

**Zona**

- `id`, `nombre`, `localidad`, `provincia`
- Sin métodos: es solo un dato. Una zona tiene muchos complejos y un complejo pertenece a una zona.

**Complejo**

- `id`, `zona`, `nombre`, `direccion`
- `latitud`, `longitud`
- `telefono_contacto`, `whatsapp_contacto`, `email_contacto`
- `puntuacion_promedio`, `cantidad_puntuaciones`
- `duenio`: reservado para el rol de dueño de complejo (post-MVP). Vacío en el MVP.

Métodos:

| Método | Qué hace | Regla de la doc |
|---|---|---|
| `registrar_puntuacion(estrellas)` | Suma un voto y recalcula el promedio y la cantidad. | Se vota al complejo (RQ8). |
| `quitar_puntuacion(estrellas)` | Deshace un voto y recalcula. | Anular una votación recalcula el promedio. |
| `distancia_a(latitud, longitud)` | Devuelve la distancia en km hasta un punto. | RQ3: buscar complejos cercanos. |

Decisiones:

- **Cercanos con radio.** La búsqueda recibe latitud, longitud y `radio_km`, y devuelve los complejos dentro del radio, ordenados por distancia. La distancia se calcula en Python con `distancia_a`, que funciona igual en SQLite y PostgreSQL. Alcanza para el volumen del MVP.
- **Puntuación repetida a propósito.** `registrar_puntuacion` y `quitar_puntuacion` existen en `Usuario` y en `Complejo`. Son dos métodos cortos y cada clase se lee sola. No se arma una clase base `Puntuable`.
- **Sin método para editar datos.** El admin los modifica por el endpoint (RQ10) y no hay regla propia que proteger.

### Partidos

**Partido**

- `id`, `organizador`, `complejo`
- `inicio`, `duracion_minutos` (60 por defecto)
- `tipo` (F5, F7, F8, F11)
- `cupos_faltantes`
- `estado` (abierto, completo, jugado, cancelado)

Métodos:

| Método | Qué hace | Evento que emite |
|---|---|---|
| `fin()` | Devuelve `inicio` + duración. | — |
| `postular(jugador)` | Crea la postulación. Rechaza con excepción si el partido no está abierto, si el jugador es el organizador, si ya se postuló o si tiene deuda mayor que X. | `postulacion_recibida` |
| `aceptar(postulacion)` | Resta 1 cupo. Si llega a 0, el partido pasa a completo y las postulaciones en espera pasan a rechazadas. | `postulacion_aceptada`, `partido_completo` |
| `rechazar(postulacion)` | Marca la postulación rechazada. | `postulacion_rechazada` |
| `revocar(postulacion)` | Suma 1 cupo y reabre el partido si estaba completo. | `revocacion` |
| `retirar(postulacion)` | El jugador se baja. Si estaba aceptado, suma 1 cupo y reabre el partido. | `postulacion_retirada` |
| `marcar_no_show(postulacion)` | Solo el organizador, sobre un aceptado. Llama a `postulacion.marcar_no_show()`. | `no_show_marcado` |
| `cancelar()` | Pasa a cancelado. | `partido_cancelado` |
| `actualizar_estado(ahora)` | Si ya pasó `fin()`, pasa a jugado. Se llama al consultar el partido. | `partido_jugado` |
| `agregar_observador(o)`, `quitar_observador(o)`, `notificar(evento)` | Mecánica del Observer. | — |

**Postulacion**

- `id`, `partido`, `jugador`
- `estado` (en espera, aceptada, rechazada, retirada, revocada)
- `no_show` (falso por defecto)
- `created_at`, `respondida_at`
- Un usuario no se postula dos veces al mismo partido.

Métodos. `Postulacion` es dueña de sus propias transiciones de estado, y `Partido` las llama:

| Método | Qué hace |
|---|---|
| `aceptar()` | Pasa de en espera a aceptada y guarda `respondida_at`. |
| `rechazar()` | Pasa de en espera a rechazada y guarda `respondida_at`. |
| `revocar()` | Pasa de aceptada a revocada y guarda `respondida_at`. |
| `retirar()` | Pasa de en espera o aceptada a retirada. |
| `marcar_no_show()` | Solo si está aceptada y no está marcada. Pone `no_show` en verdadero. |
| `quitar_no_show()` | Solo si está marcada. Pone `no_show` en falso. |
| `whatsapp_visible()` | Verdadero solo si el estado es aceptada. Es la regla de exposición del WhatsApp. |

Una transición inválida levanta una excepción (por ejemplo, aceptar una postulación ya rechazada). La regla de estados queda en un solo lugar. `Postulacion` no emite eventos.

### Gestión post-partido

**Votacion**

- `id`, `partido`, `emisor`
- `receptor_usuario` o `receptor_complejo`: exactamente uno tiene valor
- `estado` (pendiente, emitida), `estrellas` (0 a 5, vacío mientras está pendiente)
- `emitida_at`, `created_at`

Métodos:

| Método | Qué hace |
|---|---|
| `emitir(estrellas)` | Valida 0 a 5 y que esté pendiente, guarda `emitida_at` y le suma el voto al receptor con `registrar_puntuacion`. |
| `anular()` | Quita el voto de la puntuación del receptor con `quitar_puntuacion`. Lo usa el reclamo resuelto. |
| `receptor()` | Devuelve el receptor que tenga valor (usuario o complejo). Los dos responden a `registrar_puntuacion`. |

Decisión: el receptor se modela con dos referencias opcionales, de las que exactamente una tiene valor. No se arman subclases `VotacionUsuario` y `VotacionComplejo`.

**Reclamo**

- Cubre los reclamos por no-show y votación, y las denuncias a usuarios y complejos.
- Objetivo: no-show, votación, usuario o complejo.
- Estados: abierto, resuelto, rechazado.
- Atributos: `id`, `autor`, `tipo_objetivo`, `objetivo_id`, `motivo`, `estado`, `resolucion`, `resuelto_por`, `created_at`, `resuelto_at`.
- El partido no se guarda: se obtiene desde el objetivo.

Métodos:

| Método | Qué hace |
|---|---|
| `abrir(autor, tipo_objetivo, objetivo, motivo)` | Método de clase que crea el reclamo en estado abierto. Valida según el tipo: un no-show tiene que estar marcado y ser del autor, y una votación tiene que tener al autor como receptor. Rechaza denunciarse a uno mismo. Levanta una excepción si no se cumple. |
| `resolver(admin, resolucion)` | Pasa a resuelto y aplica la medida según `tipo_objetivo`. |
| `rechazar(admin, resolucion)` | Pasa a rechazado. No aplica ninguna medida. |

Medida al resolver:

| `tipo_objetivo` | Qué es `objetivo_id` | Medida |
|---|---|---|
| no-show | Postulación marcada | Quita la marca con `Postulacion.quitar_no_show()`, suma 1 partido jugado y quita el voto de 0 estrellas. |
| votación | Votación | La anula con `Votacion.anular()`. |
| usuario | Usuario denunciado | El admin puede bloquearlo con `Usuario.bloquear()`. |
| complejo | Complejo denunciado | Ninguna automática. El admin edita sus datos por el endpoint. |

Decisiones:

- **Objetivo genérico.** `Reclamo` guarda `tipo_objetivo` y `objetivo_id`, sin clave foránea, igual que `Notificacion`. El diagrama queda más simple. El costo es que la base no verifica el id y el código decide dónde buscarlo según el tipo.
- **Validación al crear.** El endpoint busca el objetivo según `tipo_objetivo` y `objetivo_id`, y responde 404 si no existe. Después le pasa el objeto cargado a `Reclamo.abrir`, que valida que el no-show o la votación afecten al autor. La regla vive en la clase, se prueba con tests unitarios sin base de datos y no suma métodos a otras clases.
- **Reclamo duplicado.** No se acepta un reclamo si el mismo autor ya tiene uno abierto sobre el mismo objetivo. Esta regla necesita consultar la base, que las clases de dominio no hacen, así que la comprueba el endpoint antes de llamar a `Reclamo.abrir`.
- **Notificación de reclamos.** Solo se notifica el reclamo resuelto (al autor), y se pide directamente a `FabricaNotificaciones` desde la lógica del reclamo. El admin no recibe aviso por un reclamo nuevo: ve los abiertos en su listado. `Reclamo` no es sujeto del Observer, que queda solo para `Partido`.

**Sancion**

- `id`, `usuario`, `aplicada_por`, `reclamo` (opcional), `motivo`
- `desde`, `hasta` (se completa al desbloquear)

Métodos:

| Método | Qué hace |
|---|---|
| `cerrar()` | Guarda `hasta` con la fecha actual. Lo llama `Usuario.desbloquear()`. |
| `activa()` | Verdadero si `hasta` está vacío. |

## 2. Decisiones de modelado

| Concepto | Decisión | Motivo |
|---|---|---|
| Pagos, comisiones, suscripciones, turnos, canchas | No se modelan | Post-MVP. Se vota al complejo, no a la cancha. |
| Participante de partido | No es clase | Participantes = organizador + postulaciones aceptadas. El no-show vive en la postulación. |
| Alerta de "busco jugador" | No es clase | Una sola entidad: partido con cupos. Tampoco se guarda la posición buscada. |
| Solicitud de contacto | No es clase | El WhatsApp se habilita con la postulación aceptada. |
| Configuración editable | No es clase | X = 3 vive en `settings.py`. |
| Denuncia | Es un tipo de `Reclamo` | Un solo mecanismo para no-show, votación, usuario y complejo. |
| Perfil de jugador | Vive en `Usuario` | Es 1 a 1 con el usuario. Una clase menos que explicar. |
| Varios roles por usuario | Un rol por usuario | Clase `Rol`. Agregar un rol no cambia `Usuario`. |
| Sanción | Clase propia | Registro de bloqueos con motivo, admin y fechas. |

Datos que no se guardan: verificación de email y teléfono, cantidad de no-shows (se deriva de las postulaciones), valor de la cancha, zona en el partido, ventana de votación y votación fuera de término.

## 3. Patrones de diseño previstos

Solo se piden uno o dos. Previstos:

- **Observer.** `Partido` es el sujeto. Cuando cambia de estado (se completa, se cancela, se libera un cupo, pasa a jugado), avisa a sus observadores.
- **Factory.** Una fábrica arma la `Notificacion` según el tipo de evento. El observador la usa para crear el aviso del destinatario correcto.

Cómo se conectan: el partido cambia, el observador recibe el evento, y la fábrica arma la notificación.

Decisiones sobre el Observer:

- **Un solo sujeto: `Partido`.** Las acciones sobre postulaciones (postular, aceptar, rechazar, revocar, retirar) pasan por métodos de `Partido`. Motivo: `Partido` ya maneja los cupos y el estado, así que esas acciones lo modifican igual. `Postulacion` no emite eventos.
- **Eventos de `Partido`:** `postulacion_recibida`, `postulacion_aceptada`, `postulacion_rechazada`, `partido_completo`, `revocacion`, `postulacion_retirada`, `partido_cancelado`, `partido_jugado`, `no_show_marcado`.
- **Dos observadores**, que implementan la interfaz `ObservadorPartido` (método `actualizar(evento)`):
  - `NotificadorPartido`: crea la notificación de cada evento usando la Factory. Con `partido_jugado` crea el aviso de votaciones pendientes.
  - `ProcesadorPostPartido`: reacciona a dos eventos.
    - `partido_jugado`: suma 1 partido jugado a cada participante y crea las votaciones pendientes.
    - `no_show_marcado`: resta 1 partido jugado al ausente, le suma un voto de 0 estrellas a su puntuación y elimina sus votaciones pendientes.
- Motivo de usar un segundo observador: los efectos de pasar a jugado y de marcar un no-show no viven dentro de `Partido`. `Partido` solo avisa y no sabe quién reacciona. Agregar otra reacción no lo modifica.
- **`EventoPartido`:** lo que recibe `actualizar(evento)`. Lleva `tipo` (uno de los 9 eventos), `partido` y `postulacion` (opcional, solo en los eventos que nacen de una postulación). `Partido` lo crea al emitir. Así cada observador sabe qué partido y qué postulación originaron el aviso, sin buscarlos.

Decisiones sobre la Factory:

- **Fábrica simple:** `FabricaNotificaciones.crear(tipo, destinatario, referencia)` elige la plantilla del mensaje según el tipo y devuelve la `Notificacion`. No hay una subclase por tipo: sería mucho para explicar y no aporta nada en este alcance.
- `NotificadorPartido` decide el destinatario de cada evento y le pide la notificación a la fábrica:

| Evento | Destinatario | Tipo de notificación |
|---|---|---|
| `postulacion_recibida` | Organizador | postulación recibida |
| `postulacion_aceptada` | Jugador de la postulación | postulación aceptada |
| `postulacion_rechazada` | Jugador de la postulación | postulación rechazada |
| `partido_completo` | Cada postulante en espera que pasó a rechazado | partido completo |
| `revocacion` | Jugador de la postulación | revocación |
| `postulacion_retirada` | Organizador | postulación retirada |
| `partido_cancelado` | Postulantes y aceptados | partido cancelado |
| `partido_jugado` | Participantes | votaciones pendientes |
| `no_show_marcado` | — | No se notifica |

- La notificación de reclamo resuelto la pide la lógica del reclamo a la misma fábrica, sin pasar por el Observer.

## 4. Decisiones ya tomadas que afectan a las clases

- El pase a `jugado` se revisa cada vez que se consulta el partido, no con una tarea periódica. Ahí se dispara el aviso del Observer.
- El orden de la lista de espera (puntuación descendente, sin puntuación al final, desempate por llegada) se calcula al consultar. No se guarda.
- La deuda del usuario se calcula por partido con votaciones pendientes. Si supera X (3, en `settings.py`), no puede publicar ni postularse.
- El WhatsApp solo se expone mientras la postulación está aceptada.

## 6. Diagrama

[`diagramas/clases.drawio`](diagramas/clases.drawio). Tiene las 15 clases (10 del dominio y 5 de los patrones Observer y Factory). Se abre en https://app.diagrams.net (Open Existing Diagram) o con la extensión Draw.io Integration de VS Code. Hay una copia en imagen, [`diagramas/clases.svg`](diagramas/clases.svg), para verlo directo en GitHub o usarlo en la presentación. Se exporta desde el `.drawio`: si se cambia uno, hay que regenerar el otro.

### Cómo leerlo

**Una clase**

Cada caja tiene tres partes: nombre, atributos y métodos.

```
Partido
- cupos_faltantes: int      atributo (el - es privado)
+ aceptar(postulacion)      método (el + es público)
```

- Un atributo se lee `nombre: Tipo`. Si el tipo es otra clase del diagrama (`organizador: Usuario`), es una relación.
- `[0..1]` en un atributo significa que es opcional y puede estar vacío.
- Los métodos con `(): Tipo` devuelven ese tipo.

**Líneas**

| Línea | Qué significa | Ejemplo |
|---|---|---|
| Línea simple con nombre | Asociación: una clase conoce a otra. El nombre es el rol. | `Partido` ─ `postulaciones` ─ `Postulacion` |
| Línea con rombo vacío | Agregación: el sujeto guarda una lista de otros. | `Partido` ◇─ `observadores` ─ `ObservadorPartido` |
| Punteada con flecha abierta | Dependencia: una clase usa o crea a otra. Lleva «crea» o «usa». | `FabricaNotificaciones` ┄«crea»┄> `Notificacion` |
| Punteada con triángulo vacío | Realización: la clase implementa la interfaz. | `NotificadorPartido` ┄▷ `ObservadorPartido` |
| Línea punteada gris | Une una nota con su clase. No es una relación. | Notas amarillas |

**Multiplicidad** (los números en los extremos de una línea)

| Valor | Se lee |
|---|---|
| `1` | Exactamente uno |
| `0..1` | Cero o uno |
| `0..*` | Cero o muchos |

Se lee desde una clase hacia la otra. Ejemplo: entre `Partido` y `Postulacion`, `1` del lado de `Partido` y `0..*` del lado de `Postulacion` significa que un partido tiene cero o muchas postulaciones, y cada postulación es de un solo partido.

**Colores, marcos y notas**

- Azul: clases del dominio.
- Amarillo con `«interface»`: interfaz. Define qué métodos deben tener los que la implementan, pero no tiene código propio.
- Verde: clases que existen por un patrón (los observadores y la fábrica).
- Marco punteado con título (`Patrón Observer`, `Patrón Factory`): agrupa las clases que forman ese patrón.
- Nota amarilla: aclaración de una clase o de una regla.

**Tips**

1. Leelo por zonas. A la izquierda, zonas y complejos. Al centro, `Partido` con el Observer arriba (observadores, interfaz y evento) y `Votacion` abajo. A la derecha, `Postulacion` y `Usuario`, con `Rol`, `Sancion` y `Reclamo` debajo, y la Factory con `Notificacion` arriba.
2. Seguí un caso real. Por ejemplo: un partido pasa a jugado, `Partido` crea un `EventoPartido` y llama a `notificar`, los dos observadores reciben `actualizar(evento)`, el `NotificadorPartido` le pide la notificación a la fábrica y el `ProcesadorPostPartido` crea las votaciones.
3. `Votacion`, `Sancion` y `Reclamo` se unen a `Usuario` con una sola línea que lleva los dos roles en el nombre (por ejemplo `emisor / receptor_usuario`). Son dos relaciones dibujadas como una para no llenar el diagrama, y la multiplicidad que se ve es la del primer rol (`emisor`, `usuario`, `autor`, que son siempre uno). El segundo rol puede ser opcional: `receptor_usuario` y `resuelto_por` son `0..1`. El dueño de `Complejo` no tiene línea: se ve solo como atributo reservado.
4. `Reclamo` no tiene línea hacia su objetivo. Guarda `tipo_objetivo` y `objetivo_id`, y la nota al lado explica qué clase corresponde a cada tipo.
5. Los tipos que no son clases del diagrama (`EstadoPartido`, `TipoPartido`, `TipoNotificacion` y similares) son enumeraciones: listas fijas de valores, como los estados de la sección 4 de `requerimientos.md`.
