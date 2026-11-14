# CLAUDE.md — fulvo

Guía para Claude Code en este repositorio. Todo lo que está acá es de lectura obligatoria antes de tocar código.

> Secciones marcadas con `TODO(proyecto)` quedan pendientes hasta que el grupo describa el dominio y lo planificado.

## 1. Proyecto

- **Nombre:** fulvo
- **Contexto:** trabajo práctico final de *Programación 2 (LCD)*, UNSAM. Entrega grupal.
- **Idea general:** MVP para validar la hipótesis de si las personas están dispuestas a solicitar jugadores extra para completar partidos de fútbol. Los usuarios se registran y arman partidos; otros usuarios se postulan a los lugares libres; el organizador acepta y ambos se ven el WhatsApp para coordinar por fuera de la app. El alcance es chico a propósito: solo lo necesario para probar esa hipótesis.
- **Repositorio:** https://github.com/nvranco/fulvo
- **Compartir el repo con:** `matuk` y `santiagoblaslaguzza`.

### Prioridad del proyecto: explicabilidad

El 40% de la nota es **exposición y defensa**. Cada decisión de código tiene que poder explicarse en voz alta. Por eso:

- Preferir la solución simple y legible sobre la ingeniosa.
- No agregar librerías, capas ni abstracciones que la cátedra no haya visto, salvo que se justifiquen y se documenten.
- Cada decisión de diseño no obvia lleva un comentario con el **porqué**, no solo el qué.
- Al proponer un cambio, explicar brevemente qué hace y por qué se eligió así.

## 2. Consigna (resumen, original en `docs/consigna.pdf`)

**Objetivo:** demostrar lo visto en la materia sobre desarrollo de web APIs, manejo de bases de datos, seguridad, autenticación y buenas prácticas en Python.

**Caso de ejemplo de la cátedra:** API de reservas de un gimnasio (RQ1 registrarse, RQ2 ver horarios, RQ3 reservar clases, RQ4 cancelar reservas, RQ5 recibir notificaciones ante cambios de fecha u horario).

**Consigna:** plantear casos de uso similares para el proyecto elegido, con **al menos 5 requerimientos de alto nivel** que estén cubiertos por los endpoints de la API.

**Stack mínimo a entregar:**

1. Framework para la API: FastAPI.
2. Autenticación: registro y autenticación segura de usuarios.
3. Base de datos manejada con SQLAlchemy.
4. Documentación del proyecto: idea general, requerimientos funcionales y casos de uso.
5. Contenedor Docker de la API.
6. Funciones de testing.
7. Deploy.

**Requisitos adicionales:**

- La API sigue principios RESTful.
- Manejo de errores mediante excepciones.
- Código bien documentado.
- Al menos **un patrón de diseño** con sentido y utilidad real.
- Al menos **10 tests unitarios** que validen el funcionamiento de la API.
- Una **GitHub Action** que automatice los tests.
- `README.md` con las librerías necesarias e instrucciones claras para desplegar y probar la API.
- Presentación con al menos **1 diagrama UML** y la explicación de dónde, por qué y qué patrones de diseño se usaron.

**Evaluación:**

| Criterio | Peso |
|---|---|
| Funcionalidad (cumple los requerimientos y maneja bien los errores) | 20% |
| Calidad del código (claridad y uso adecuado de lo visto en la materia) | 20% |
| Documentación y pruebas (calidad y cobertura) | 20% |
| Exposición y defensa (claridad de conceptos y justificación) | 40% |

## 3. Requerimientos del proyecto

Detalle completo en `docs/requerimientos.md`, diagramas de secuencia en `docs/diagramas/` diseño de clases en `docs/clases.md` y esquema de la base de datos en `docs/base-de-datos.md` (se amplía con cada tabla nueva). Esa es la fuente de verdad del alcance del MVP: lo que está en su sección Post-MVP no se implementa. Todo endpoint debe poder rastrearse a un RQ.

| RQ | Descripción | Endpoint(s) | Tests | Estado |
|---|---|---|---|---|
| RQ1 | Registrarse e iniciar sesión (edad mínima 16). | `POST /usuarios`, `POST /auth/token`. La dependencia `UsuarioActual` (en `security.py`) protege las rutas. | `tests/test_usuarios.py`, `tests/test_auth.py`, `tests/test_security.py` | hecho |
| RQ2 | Perfil de usuario con puntuación promedio y partidos jugados. | `GET /usuarios/yo`, `PATCH /usuarios/yo`, `GET /usuarios/{id}` | `tests/test_perfil.py` | hecho |
| RQ3 | Ver zonas y complejos, con ubicación en mapa y búsqueda de cercanos por radio. | `GET /zonas`, `GET /complejos`, `GET /complejos/cercanos`, `GET /complejos/{id}` | `tests/test_complejos.py` | hecho (con base de datos) |
| RQ4 | Publicar partidos indicando complejo, fecha, hora, tipo y cupos faltantes (la duración es fija: 60 minutos). | `POST /partidos`, `GET /partidos/{id}` | `tests/test_partidos.py`, `tests/test_models.py`, `tests/test_votaciones.py` (bloqueo por deuda) | hecho, con el bloqueo por deuda de RQ8 |
| RQ5 | Listar partidos abiertos con filtros y postularse. | `GET /partidos` (filtros `zona`, `complejo_id` y `tipo`), `POST /partidos/{id}/postulaciones`, `GET /postulaciones` (las propias) | `tests/test_partidos.py`, `tests/test_postulaciones.py`, `tests/test_postulaciones_modelo.py`, `tests/test_eventos.py`, `tests/test_votaciones.py` (bloqueo por deuda) | hecho, con el bloqueo por deuda de RQ8 |
| RQ6 | El organizador acepta, rechaza o revoca postulantes. Al aceptar, ambos se ven el WhatsApp. | `GET /partidos/{id}/postulaciones` (lista de espera), `PATCH /partidos/{id}/postulaciones/{id}` (aceptar o rechazar) | `tests/test_postulaciones.py`, `tests/test_postulaciones_modelo.py` | hecho; solo antes del inicio del partido (409 "El partido ya empezó") |
| RQ7 | Cancelar postulación, baja de un aceptado, revocación y cancelación del partido. | `PATCH /postulaciones/{id}` (retirarse o bajarse), `PATCH /partidos/{id}/postulaciones/{id}` (revocar), `PATCH /partidos/{id}` (cancelar) | `tests/test_postulaciones.py`, `tests/test_postulaciones_modelo.py`, `tests/test_eventos.py` | hecho; solo antes del inicio del partido: con el partido empezado nada cambia (409 "El partido ya empezó"), así un aceptado no se baja para esquivar el no-show |
| RQ8 | Votar después del partido, no-show y bloqueo por votaciones pendientes. | `GET /votaciones` (las propias, filtro `estado`), `PATCH /votaciones/{id}` (emitir, de 0 a 5 estrellas), `PATCH /partidos/{id}/postulaciones/{id}` con `{"no_show": true}` (el organizador, con el partido jugado). Las votaciones las crea `ProcesadorPostPartido` al pasar a jugado un partido con aceptados: uno que termina sin aceptados pasa a jugado sin votaciones, partidos jugados ni deuda. La deuda se ve en `GET /usuarios/yo` y bloquea publicar y postularse (409) | `tests/test_votaciones.py`, `tests/test_votaciones_modelo.py`, `tests/test_procesador.py`, `tests/test_eventos.py` | hecho |
| RQ9 | Notificaciones dentro de la app. | `GET /notificaciones` (las propias, filtro `leida`), `PATCH /notificaciones/{id}` (marcar como leída). Las crea `NotificadorPartido` al pasar algo en un partido | `tests/test_notificaciones.py`, `tests/test_observadores.py` | hecho; con RQ11 suma el aviso de votaciones repuestas y la respuesta a un reclamo |
| RQ10 | Admin: bloquear usuarios (con sanción registrada) y editar zonas y complejos. | Zonas y complejos: `POST /zonas`, `PUT /zonas/{id}`, `POST /complejos`, `PUT /complejos/{id}`, `DELETE /complejos/{id}` (409 si el complejo tiene partidos). Bloqueo: `POST /usuarios/{id}/sanciones` (bloquear), `PATCH /usuarios/{id}/sanciones/{id}` con `{"activa": false}` (desbloquear) y `GET /usuarios/{id}/sanciones` (historial). Al bloquear se cancelan sus partidos y se retiran sus postulaciones, solo en partidos que no empezaron | `tests/test_complejos.py`, `tests/test_permisos_admin.py`, `tests/test_partidos.py`, `tests/test_sanciones.py`, `tests/test_sanciones_modelo.py` | hecho: todo solo para admin (`exigir_admin`), y no se bloquea a un admin |
| RQ11 | Reclamos por no-show, votación, usuario o complejo, resueltos por el admin. | `POST /reclamos` (abrir), `GET /reclamos` (los propios; el admin ve todos, filtro `estado`), `PATCH /reclamos/{id}` (el admin resuelve o rechaza; con `"bloquear": true` bloquea al denunciado) y `GET /votaciones?recibidas=true` (los votos recibidos, sin el emisor). Resolver aplica la medida del objetivo: anular el no-show y reponer sus votaciones, anular la votación o bloquear | `tests/test_reclamos.py`, `tests/test_reclamos_modelo.py`, `tests/test_procesador.py`, `tests/test_observadores.py`, `tests/test_eventos.py` | hecho |

Datos sensibles: el WhatsApp solo se expone entre organizador y aceptado mientras la postulación está aceptada y el partido no se canceló (`Postulacion.whatsapp_visible()`). No debe aparecer en listados públicos ni en otros endpoints; la única excepción es el perfil propio (`GET /usuarios/yo`), donde cada usuario ve su propio número. Monetización (comisiones, suscripciones, pagos), reservas, amigos, chat y torneos están fuera del MVP.

## 4. Stack técnico

Se sigue el stack de la cátedra, con **un desvío: SQLAlchemy síncrono** (ver subsección "Desvío" más abajo). Referencia: sitio https://rmatuk.github.io/prog2 y repo https://github.com/rmatuk/prog2. Ante cualquier duda de cómo hacer algo, mirar primero ahí, pero tomando como referencia de base de datos, rutas y tests la carpeta `codigo_aulas/07` (sync) y no la 13 (async). Para Docker, CI, factories y testcontainers sirven `codigo_aulas/11` y `12`, traducidos a sync.

| Rol | Herramienta |
|---|---|
| Gestor de dependencias y entorno | Poetry (`pyproject.toml` formato PEP 621) |
| Framework web | `fastapi[standard]` |
| ORM | `sqlalchemy` 2.x **síncrono** (sin `[asyncio]`), modelos con `mapped_as_dataclass` |
| Migraciones | `alembic` |
| Validación y esquemas | `pydantic` y `pydantic-settings` |
| Auth | JWT con `pyjwt`, hash de contraseñas con `pwdlib[argon2]` |
| BD en desarrollo local (`poetry serve`) | SQLite con el módulo `sqlite3` de Python (sin `aiosqlite`), valor por defecto de `DATABASE_URL` |
| BD en tests | PostgreSQL 16 real en un contenedor, levantado por `testcontainers` (ya no SQLite en memoria) |
| BD en contenedor, CI y producción | PostgreSQL con `psycopg[binary]` |
| Tests | `pytest`, `pytest-cov`, `pytest-random-order`, `factory-boy`, `freezegun`, `testcontainers`, `httpx2` |
| Lint y formato | `ruff` |
| Ortografía del código | `typos` |
| Ejecutor de tareas | `poethepoet` (plugin de Poetry) |
| Contenedores | Docker y `compose.yaml` |
| CI | GitHub Actions |
| Deploy | Fly.io (`fly.toml`), como la cátedra |

Python: **3.13**, una sola versión en todos lados (`.python-version`, `requires-python = ">=3.13,<4.0"` en `pyproject.toml`, `Dockerfile` y workflow de CI). Decidido porque ya estaba instalada en las máquinas del grupo y evita diferencias entre local, contenedor y CI (la cátedra usa 3.12 en CI y 3.14 en Docker).

Entorno: `pipx` instala Poetry; Poetry crea el venv en `.venv/` (`poetry config virtualenvs.in-project true`, configuración global por máquina). `package-mode = false` porque es una app: `fulvo` no se instala como paquete. El `Dockerfile` instala las dependencias con Poetry desde `poetry.lock`, en dos etapas (decisión del 2026-11-13): la primera arma `/app/.venv` y la imagen final copia solo ese entorno, sin Poetry. Así la imagen tiene las mismas versiones que se testean. Antes se instalaba con `pip install .`, como la cátedra, pero pip resolvía con los rangos de `pyproject.toml` y 28 de 68 paquetes salían con otra versión. **Docker es obligatorio** para desarrollar y testear: `poetry test` levanta un PostgreSQL en un contenedor, y sin Docker Desktop corriendo de fondo los tests fallan al arrancar. Pasos completos para replicar en otra máquina: `docs/entorno.md`. Mantener ese archivo al día si cambia algo del entorno.

Las versiones exactas de dependencias salen del `pyproject.toml` y `poetry.lock` de `codigo_aulas/13`, sin `aiosqlite`, sin `pytest-asyncio` y con `sqlalchemy` en vez de `sqlalchemy[asyncio]`. No actualizar dependencias sin avisar.

### Desvío: SQLAlchemy síncrono

**Decisión:** el proyecto usa SQLAlchemy síncrono. La cátedra enseña sync en las lecciones 05 a 07 y pasa a async desde la carpeta `codigo_aulas/08` hasta la 13, sin explicarlo en el sitio. Elegimos sync porque es más simple de escribir, probar y explicar en la defensa, y para el volumen del MVP no hay diferencia práctica.

**Qué implica para cada cambio de código:**

- `database.py`: `create_engine(Settings().DATABASE_URL)` y `get_session` con `with Session(engine) as session: yield session`. Nada de `create_async_engine` ni `AsyncSession`.
- Rutas: siempre `def`. **Nunca `async def` con una session sync**: bloquearía el event loop. FastAPI corre las rutas `def` en un pool de hilos.
- Alias de la dependencia: como en `codigo_aulas/07`, cada archivo de `routes/` que usa la base define `Session = Annotated[Session, Depends(get_session)]` debajo de sus imports (importando `Session` de `sqlalchemy.orm` y `get_session` de `fulvo.database`). El alias reutiliza el nombre `Session` a propósito, igual que la cátedra: en las rutas se escribe `session: Session`. No se define en `database.py`.
- Tests: la fixture `engine` (`scope='session'`) levanta `PostgresContainer('postgres:16', driver='psycopg')` de `testcontainers.community.postgres` una sola vez por corrida y crea un engine síncrono con `create_engine`. La fixture `session(engine)` hace `create_all` antes de cada test y `drop_all` después, con la sesión ya cerrada (una transacción abierta bloquearía el borrado en PostgreSQL). `client` reemplaza `get_session` con `app.dependency_overrides`. Se usa `TestClient`, sin `pytest-asyncio` ni `pytest_asyncio.fixture`.
- Relaciones: el lazy loading funciona, no hace falta `selectinload` ni `joinedload` (en async sí, o falla con `MissingGreenlet`).
- Código copiado de `codigo_aulas/08` a `13`: se **traduce a sync** (quitar `async` y `await`, `AsyncSession` pasa a `Session`, `pytest_asyncio.fixture` pasa a `pytest.fixture`, `expire_on_commit=False` no hace falta). Nunca se copia tal cual.
- Docker y CI: el driver de PostgreSQL es `psycopg[binary]` en modo sync, la URL es `postgresql+psycopg://...`.
- Alembic corre igual en sync y async: `migrations/env.py` y los modelos no cambian.

**Costo asumido:** si más adelante se pasa a async hay que reescribir `database.py`, todas las rutas y los tests. Los modelos y las migraciones se mantienen. Mientras tanto el rendimiento bajo muchas conexiones simultáneas es menor, y no importa para el MVP.

## 5. Estructura del repositorio

Se mantiene la estructura de la cátedra, cambiando el nombre del paquete `fast_zero` por `fulvo`.

```
fulvo/
├── CLAUDE.md
├── README.md                  # librerías, cómo desplegar y probar (entregable)
├── pyproject.toml
├── poetry.lock
├── alembic.ini
├── Dockerfile
├── compose.yaml
├── entrypoint.sh              # alembic upgrade head + uvicorn
├── fly.toml
├── .env                       # NO se commitea (usar .env.example)
├── .github/workflows/pipeline.yaml
├── docs/
│   ├── consigna.pdf
│   └── ...                    # requerimientos, casos de uso, UML
├── migrations/                # excluido de ruff
├── fulvo/
│   ├── app.py                 # instancia FastAPI y registro de las rutas
│   ├── settings.py            # configuración desde variables de entorno
│   ├── database.py            # engine y get_session
│   ├── models.py              # modelos SQLAlchemy
│   ├── schemas.py             # esquemas Pydantic
│   ├── security.py            # JWT y hash de contraseñas
│   ├── eventos.py             # patrón Observer: evento e interfaz (ver sección 8)
│   ├── observadores.py        # observadores concretos y fábrica de notificaciones (Factory)
│   ├── errores.py             # errores del dominio, que la API responde como 409
│   ├── carga_inicial.py       # roles, admin y complejos.csv (el CSV, solo en una base sin zonas)
│   ├── datos/                 # complejos.csv: carga inicial, viaja con el código
│   └── routes/                # un archivo por recurso (como la cátedra, aula 12)
└── tests/
    ├── conftest.py
    ├── factories.py
    └── test_*.py
```

Las lecciones 03 a 11 de la cátedra ponen todas las rutas en `app.py`; la división en `fast_zero/routes/` (con `app.include_router`) aparece en la lección 12 y en `codigo_aulas/13`. Acá se adoptó antes porque cada recurso (`complejos`, `zonas`) tiene su archivo y `app.py` no crece.

Los patrones de diseño tienen sus propios módulos: `fulvo/eventos.py` (la parte genérica del Observer) y `fulvo/observadores.py` (los observadores concretos y la Factory). Decisión del 2026-11-11, ver sección 8.

## 6. Comandos

```bash
poetry install                 # instalar dependencias
poetry serve                   # levantar la API en modo desarrollo (poe serve)
poetry lint                    # typos + ruff check
poetry format                  # ruff check --fix + ruff format
poetry test                    # lint + pytest con cobertura + reporte html
alembic revision --autogenerate -m "descripción"   # crear migración
alembic upgrade head           # aplicar migraciones
docker compose up --build      # API + PostgreSQL en contenedores
```

Antes de cada commit: `poetry format` y `poetry test` tienen que pasar.

Requisito por máquina: el plugin de tareas, `pipx inject poetry 'poethepoet[poetry_plugin]'` (ver `docs/entorno.md`). Las tareas están en `[tool.poe.tasks]` de `pyproject.toml`; `poetry_command = ''` permite `poetry serve` en vez de `poetry poe serve`. Typos excluye `*.md`, `docs`, `poetry.lock` y `migrations` (español).

## 7. Convenciones de código

### Idioma

- **Todo en español:** nombres de variables, funciones, clases, modelos, tablas, columnas, campos de esquemas, rutas, mensajes de error (`detail`), comentarios y docstrings.
- **Excepciones al idioma:** lo que impone una librería o un estándar queda como está (`router`, `session`, `Depends`, `status_code`, `Authorization`, `Bearer`, `access_token`, `token_type`, nombres de métodos HTTP, claims de JWT como `sub` y `exp`, `__tablename__`, etc.).
- Usar identificadores en español **sin tildes ni ñ** (`reserva`, `contrasena`, `anio`) para evitar problemas con herramientas, y tildes normales en comentarios y mensajes de texto.
- `typos` revisa en inglés: si marca palabras en español como error, agregar la excepción en `[tool.typos.default]` en vez de renombrar.

### Estilo (lo fija Ruff, no discutir)

- Línea de 79 caracteres, **comillas simples**.
- Reglas activas: `I F E W PL PT FAST`.
- Imports ordenados, sin imports sin usar.

### Prácticas

- Tipado en firmas de funciones.
- Docstring corto en español en cada función pública y clase: qué hace y por qué existe.
- Comentarios para el **porqué**. No narrar lo que el código ya dice.
- Códigos de estado con `http.HTTPStatus`, nunca números sueltos.
- Dependencias de FastAPI con alias `Annotated` (`Session`, `UsuarioActual`), como en la cátedra.
- Lógica de acceso a datos y reglas de negocio fuera de las rutas cuando crezcan (ver patrón de diseño).

### RESTful

- Recursos en plural y sustantivos: `/usuarios`, `/reservas`.
- Verbo HTTP según la acción: `GET` leer, `POST` crear, `PUT` reemplazar, `PATCH` modificar parcial, `DELETE` borrar.
- Códigos correctos: `201` al crear, `200` al leer o modificar, `401` sin credenciales válidas, `403` sin permisos, `404` no existe, `409` conflicto (duplicados), `422` validación.
- Paginación con `offset` y `limit` en los listados.

### Manejo de errores

- Se usan **excepciones**, no valores de retorno especiales.
- Errores de la API con `HTTPException` y `detail` en español, claro y específico.
- Las reglas del dominio levantan `ReglaDeNegocioError` (`fulvo/errores.py`) sin saber nada de HTTP, y `app.py` la traduce a 409 en un solo lugar, con el mensaje como `detail`.

## 8. Arquitectura y patrón de diseño

Decidido. Es entregable (va en la presentación con el UML) y tema central de la defensa. El detalle está en `docs/clases.md` (clases, métodos y decisiones) y el diagrama en `docs/diagramas/clases.drawio`. Leerlos antes de tocar modelos.

Se aplican dos patrones:

- **Observer.** `Partido` es el sujeto y emite eventos (`postulacion_recibida`, `postulacion_aceptada`, `postulacion_rechazada`, `partido_completo`, `revocacion`, `postulacion_retirada`, `partido_cancelado`, `partido_jugado`, `no_show_marcado` y `no_show_anulado`). Los observadores implementan `ObservadorPartido`: `NotificadorPartido` crea las notificaciones y `ProcesadorPostPartido` suma partidos jugados, crea votaciones pendientes, aplica el no-show y lo deshace cuando un reclamo lo anula. El evento es un objeto `EventoPartido`.
- **Factory.** `FabricaNotificaciones` (fábrica simple) arma cada `Notificacion` según su tipo. La usa `NotificadorPartido` y también la lógica de reclamos.

Por qué: `Partido` solo avisa y no sabe quién reacciona, así que agregar una consecuencia nueva no lo modifica. La fábrica concentra los mensajes de notificación en un solo lugar.

Dónde viven (decisiones del 2026-11-11):

- `fulvo/eventos.py`: la parte genérica del Observer, `TipoEvento`, `EventoPartido` y la interfaz `ObservadorPartido`. No importa ningún modelo.
- `fulvo/observadores.py`: los observadores concretos y la fábrica: `NotificadorPartido` y `FabricaNotificaciones` (RQ9) y `ProcesadorPostPartido` (RQ8).
- `fulvo/models.py`: el sujeto (`Partido`), `Postulacion`, `Notificacion` y `Votacion`.

Van separados porque `models.py` importa `eventos.py` (para emitir eventos) y los observadores necesitan los modelos (por ejemplo, la fábrica crea `Notificacion`). En un solo archivo, `models.py` y `eventos.py` se importarían mutuamente y Python no podría cargarlos. Así las dependencias van en un solo sentido: `observadores.py` → `models.py` → `eventos.py`.

La lista de observadores no es una columna: la arma `__post_init__` en los partidos nuevos y un método `@reconstructor` en los que se leen de la base, porque SQLAlchemy no llama a `__init__` al leer. Cada pedido suma los observadores en `preparar_partido` (`fulvo/routes/partidos.py`), una sola vez por partido, antes de cualquier acción. Antes de sumarlos, `preparar_partido` vuelve a leer el partido con `SELECT ... FOR UPDATE`, y su fila queda bloqueada hasta el commit del pedido: si dos pedidos tocan el mismo partido a la vez, el segundo espera y lo lee ya cambiado, así el pase a jugado y sus votaciones se hacen una sola vez y dos aceptaciones no se pisan los cupos (decisión del 2026-11-13; antes el segundo pedido respondía 500). Los que preparan varios partidos lo hacen en orden de id, para que dos pedidos no se queden esperando uno al otro. Los dos observadores suman sus cambios (notificaciones, partidos jugados, votaciones) a la sesión del pedido, y el commit de la ruta los guarda junto con el cambio que los originó. Antes de listar las votaciones de un usuario o de calcular su deuda, `poner_al_dia_partidos_de` prepara sus partidos que ya terminaron: si nadie los consultó, todavía no tienen votaciones.

Un partido que termina sin aceptados pasa a jugado sin emitir `partido_jugado`: nadie se sumó por la app, así que los observadores no tienen nada que hacer y el organizador no queda debiendo votos (decisión del 2026-11-14). Desde el inicio el partido no cambia: sus métodos de postulación, respuesta, baja y cancelación reciben `ahora` y levantan "El partido ya empezó", así ningún evento sale de un partido en curso.

El bloqueo de un usuario (RQ10) usa el Observer sin modificarlo: `sacar_de_partidos_por_jugar` (`fulvo/routes/partidos.py`) cancela sus partidos y retira sus postulaciones con los métodos de `Partido`, así los avisos salen igual que si lo hubiera hecho una persona.

Los reclamos (RQ11) también usan los dos patrones sin cambiarlos. Anular un no-show es un evento más del partido (`no_show_anulado`): `ProcesadorPostPartido` le devuelve el partido jugado al jugador y repone las votaciones, y `NotificadorPartido` avisa a los presentes. La respuesta al autor la arma la misma `FabricaNotificaciones`, pedida directo por la ruta: `Reclamo` no es sujeto del Observer.

## 9. Testing

- Mínimo exigido: **10 tests unitarios**. Objetivo real: cubrir cada endpoint, sus caminos felices y sus errores.
- Estructura **AAA** (Organizar, Actuar, Afirmar) en cada test.
- Nombres de tests en español y descriptivos: `test_crear_usuario_con_email_repetido_devuelve_conflicto`.
- Fixtures compartidas en `tests/conftest.py`: `client`, `session`, `user`, `token`, etc. Datos de prueba con `factory-boy` en `tests/factories.py`.
- Cada test se aísla: las tablas se crean y se borran por test.
- **Los tests corren contra PostgreSQL real, no SQLite en memoria** (decisión del 2026-11-12). `testcontainers` levanta un `postgres:16`, la misma versión de `compose.yaml`, una vez por corrida, y lo apaga al terminar. Así las diferencias entre bases (mensajes de error, restricciones, tipos) aparecen en los tests y no en el deploy. Requisito: **Docker corriendo de fondo**. Costo: la suite tarda unos 5 minutos en vez de 2.
- Cobertura de ramas activada (`--cov-branch`). Revisar el reporte html para ver qué falta.
- Los tests corren en orden aleatorio (`pytest-random-order`): no pueden depender unos de otros.

## 10. Git y CI/CD

### Commits

- **Conventional Commits**, con el tipo en inglés y el mensaje en español: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `ci:`.
- Ejemplo: `feat: agrego endpoint para cancelar reservas`.
- Commits chicos, uno por cambio lógico.
- Claude no hace commit ni push sin que se lo pidan.

### Ramas

`TODO(proyecto)` — acordar flujo del grupo (por ejemplo `main` protegida y ramas `feat/...` con PR).

### CI

- Workflow en `.github/workflows/pipeline.yaml`, se dispara con `push` y `pull_request`.
- Pasos: checkout, instalar Python 3.13, instalar Poetry, `pipx inject poetry 'poethepoet[poetry_plugin]'`, `poetry install`, `poetry test`. El paso del plugin no está en la lección 12: es el mismo que hace cada máquina del grupo (`docs/entorno.md`), y sin él `poetry test` no existe.
- Las variables de entorno van como **GitHub Secrets**, nunca en el workflow. Hoy no hace falta ninguna: `DATABASE_URL` tiene valor por defecto. Cuando el login (RQ1) agregue `SECRET_KEY` y compañía, se cargan como secrets y se mapean en un bloque `env` del job. Solo se mapean secrets que existan: uno que falta llega como texto vacío y pisa el valor por defecto de `Settings`.

### Deploy

- Fly.io con `fly.toml`, siguiendo la lección de la cátedra. `entrypoint.sh` corre las migraciones antes de iniciar la API.

## 11. Seguridad y configuración

- Variables en `.env` (local) leídas con `pydantic-settings`: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Valores propios del dominio: límite de deuda X (`LIMITE_DEUDA = 3`, constante fija en `settings.py`, fuera de `Settings` porque no es una variable de entorno) y credenciales del primer admin (`ADMIN_EMAIL` y `ADMIN_PASSWORD`, opcionales en `Settings`, que lee solo `carga_inicial`).
- **Nunca** commitear `.env` ni secretos. Mantener un `.env.example` sin valores reales.
- Contraseñas siempre hasheadas (argon2 vía `pwdlib`), nunca guardadas ni logueadas en claro.
- Las rutas protegidas usan la dependencia de usuario actual. Un usuario solo puede tocar sus propios recursos (`403` si no).
- Las rutas de admin usan `exigir_admin`: en el decorador o en el router si solo necesitan el permiso, o con el alias `AdminActual` si necesitan al admin (por ejemplo, para guardar quién bloqueó a un usuario).
- Un usuario bloqueado no puede iniciar sesión, y el token que ya tenía deja de servir en el pedido siguiente (`403`), porque el usuario se vuelve a leer de la base en cada pedido.
- Mensajes de login genéricos (no revelar si falló el usuario o la contraseña).

## 12. Entregables (checklist)

- [ ] Requerimientos RQ1..RQ11 definidos y cubiertos por endpoints
- [ ] API FastAPI funcionando y RESTful
- [ ] Registro y login con JWT
- [ ] Base de datos con SQLAlchemy y migraciones Alembic
- [ ] Manejo de errores con excepciones
- [ ] Patrón de diseño aplicado y justificado
- [ ] 10 o más tests unitarios pasando
- [ ] GitHub Action corriendo los tests
- [ ] `Dockerfile` y `compose.yaml`
- [ ] Deploy publicado
- [ ] `README.md` con librerías, despliegue y pruebas
- [ ] Documentación: idea general, requerimientos funcionales y casos de uso (`docs/`)
- [ ] Presentación con al menos 1 diagrama UML y explicación de patrones
- [ ] Repo compartido con `matuk` y `santiagoblaslaguzza`

## 13. Reglas para Claude

- Responder y escribir **en español**. Código, comentarios, docstrings y commits también (ver sección 7).
- Priorizar **explicabilidad** por encima de elegancia o brevedad.
- Seguir el stack de la cátedra. **Preguntar antes** de agregar una dependencia, cambiar de herramienta o salirse de su estructura.
- SQLAlchemy es **síncrono** (ver "Desvío" en la sección 4). No escribir `async def`, `await`, `AsyncSession` ni `pytest_asyncio`, ni copiar código async de `codigo_aulas/08` a `13` sin traducirlo a sync.
- No modificar `docs/consigna.pdf`.
- No commitear ni hacer push sin pedido explícito. No tocar `.env`.
- Antes de dar algo por terminado: correr `poetry test` y reportar el resultado real, incluso si falla.
- Si un cambio no se puede rastrear a un RQ de la sección 3, preguntar por qué hace falta.
- Mantener este archivo al día cuando se tomen decisiones (patrón, ramas, versión de Python, requerimientos).
