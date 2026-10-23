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

Detalle completo en `docs/requerimientos.md`, diagramas de secuencia en `docs/diagramas/` y diseño de clases en `docs/clases.md`. Esa es la fuente de verdad del alcance del MVP: lo que está en su sección Post-MVP no se implementa. Todo endpoint debe poder rastrearse a un RQ.

| RQ | Descripción | Endpoint(s) | Tests | Estado |
|---|---|---|---|---|
| RQ1 | Registrarse e iniciar sesión (edad mínima 16). | `TODO` | | pendiente |
| RQ2 | Perfil de usuario con puntuación promedio y partidos jugados. | `TODO` | | pendiente |
| RQ3 | Ver zonas y complejos, con ubicación en mapa y búsqueda de cercanos por radio. | `TODO` | | pendiente |
| RQ4 | Publicar partidos indicando complejo, fecha, hora, duración, tipo y cupos faltantes. | `TODO` | | pendiente |
| RQ5 | Listar partidos abiertos con filtros y postularse. | `TODO` | | pendiente |
| RQ6 | El organizador acepta, rechaza o revoca postulantes. Al aceptar, ambos se ven el WhatsApp. | `TODO` | | pendiente |
| RQ7 | Cancelar postulación, baja de un aceptado, revocación y cancelación del partido. | `TODO` | | pendiente |
| RQ8 | Votar después del partido, no-show y bloqueo por votaciones pendientes. | `TODO` | | pendiente |
| RQ9 | Notificaciones dentro de la app. | `TODO` | | pendiente |
| RQ10 | Admin: bloquear usuarios (con sanción registrada) y editar zonas y complejos. | `TODO` | | pendiente |
| RQ11 | Reclamos por no-show, votación, usuario o complejo, resueltos por el admin. | `TODO` | | pendiente |

Datos sensibles: el WhatsApp solo se expone entre organizador y aceptado mientras la postulación está aceptada. No debe aparecer en listados públicos ni en otros endpoints. Monetización (comisiones, suscripciones, pagos), reservas, amigos, chat y torneos están fuera del MVP.

## 4. Stack técnico

Se sigue **al pie de la letra** el stack de la cátedra. Referencia: sitio https://rmatuk.github.io/prog2 y repo https://github.com/rmatuk/prog2 (carpeta `codigo_aulas/13` es la app completa y final). Ante cualquier duda de cómo hacer algo, mirar primero ahí.

| Rol | Herramienta |
|---|---|
| Gestor de dependencias y entorno | Poetry (`pyproject.toml` formato PEP 621) |
| Framework web | `fastapi[standard]` |
| ORM | `sqlalchemy[asyncio]` 2.x, modelos con `mapped_as_dataclass` |
| Migraciones | `alembic` |
| Validación y esquemas | `pydantic` y `pydantic-settings` |
| Auth | JWT con `pyjwt`, hash de contraseñas con `pwdlib[argon2]` |
| BD en desarrollo y tests locales | SQLite con `aiosqlite` |
| BD en contenedor, CI y producción | PostgreSQL con `psycopg[binary]` |
| Tests | `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-random-order`, `factory-boy`, `freezegun`, `testcontainers`, `httpx2` |
| Lint y formato | `ruff` |
| Ortografía del código | `typos` |
| Ejecutor de tareas | `poethepoet` (plugin de Poetry) |
| Contenedores | Docker y `compose.yaml` |
| CI | GitHub Actions |
| Deploy | Fly.io (`fly.toml`), como la cátedra |

Python: **3.13**, una sola versión en todos lados (`.python-version`, `requires-python = ">=3.13,<4.0"` en `pyproject.toml`, `Dockerfile` y workflow de CI). Decidido porque ya estaba instalada en las máquinas del grupo y evita diferencias entre local, contenedor y CI (la cátedra usa 3.12 en CI y 3.14 en Docker).

Entorno: `pipx` instala Poetry; Poetry crea el venv en `.venv/` (`poetry config virtualenvs.in-project true`, configuración global por máquina). `package-mode = false` porque es una app. Pasos completos para replicar en otra máquina: `docs/entorno.md`. Mantener ese archivo al día si cambia algo del entorno.

Las versiones exactas de dependencias salen del `pyproject.toml` y `poetry.lock` de `codigo_aulas/13`. No actualizar dependencias sin avisar.

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
│   ├── app.py                 # instancia FastAPI y registro de routers
│   ├── settings.py            # configuración desde variables de entorno
│   ├── database.py            # engine y get_session
│   ├── models.py              # modelos SQLAlchemy
│   ├── schemas.py             # esquemas Pydantic
│   ├── security.py            # JWT y hash de contraseñas
│   └── routers/               # un archivo por recurso
└── tests/
    ├── conftest.py
    ├── factories.py
    └── test_*.py
```

Si el patrón de diseño elegido necesita su propio módulo (por ejemplo `fulvo/servicios/`), se agrega y se documenta acá.

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
- Si se definen excepciones propias de dominio, se traducen a `HTTPException` en un solo lugar.

## 8. Arquitectura y patrón de diseño

Decidido. Es entregable (va en la presentación con el UML) y tema central de la defensa. El detalle está en `docs/clases.md` (clases, métodos y decisiones) y el diagrama en `docs/diagramas/clases.drawio`. Leerlos antes de tocar modelos.

Se aplican dos patrones:

- **Observer.** `Partido` es el sujeto y emite eventos (`postulacion_recibida`, `postulacion_aceptada`, `postulacion_rechazada`, `partido_completo`, `revocacion`, `postulacion_retirada`, `partido_cancelado`, `partido_jugado`, `no_show_marcado`). Los observadores implementan `ObservadorPartido`: `NotificadorPartido` crea las notificaciones y `ProcesadorPostPartido` suma partidos jugados, crea votaciones pendientes y aplica el no-show. El evento es un objeto `EventoPartido`.
- **Factory.** `FabricaNotificaciones` (fábrica simple) arma cada `Notificacion` según su tipo. La usa `NotificadorPartido` y también la lógica de reclamos.

Por qué: `Partido` solo avisa y no sabe quién reacciona, así que agregar una consecuencia nueva no lo modifica. La fábrica concentra los mensajes de notificación en un solo lugar.

Pendiente: en qué módulos de `fulvo/` viven las clases del patrón. Se documenta acá cuando se creen.

## 9. Testing

- Mínimo exigido: **10 tests unitarios**. Objetivo real: cubrir cada endpoint, sus caminos felices y sus errores.
- Estructura **AAA** (Organizar, Actuar, Afirmar) en cada test.
- Nombres de tests en español y descriptivos: `test_crear_usuario_con_email_repetido_devuelve_conflicto`.
- Fixtures compartidas en `tests/conftest.py`: `client`, `session`, `user`, `token`, etc. Datos de prueba con `factory-boy` en `tests/factories.py`.
- Cada test se aísla: las tablas se crean y se borran por test.
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
- Pasos: checkout, instalar Python, instalar Poetry, `poetry install`, `poetry test`.
- Las variables de entorno van como **GitHub Secrets**, nunca en el workflow.

### Deploy

- Fly.io con `fly.toml`, siguiendo la lección de la cátedra. `entrypoint.sh` corre las migraciones antes de iniciar la API.

## 11. Seguridad y configuración

- Variables en `.env` (local) leídas con `pydantic-settings`: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Valores propios del dominio: límite de deuda X (3, fijo en `settings.py`) y credenciales del primer admin (variables de entorno que lee el script de carga inicial).
- **Nunca** commitear `.env` ni secretos. Mantener un `.env.example` sin valores reales.
- Contraseñas siempre hasheadas (argon2 vía `pwdlib`), nunca guardadas ni logueadas en claro.
- Las rutas protegidas usan la dependencia de usuario actual. Un usuario solo puede tocar sus propios recursos (`403` si no).
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
- No modificar `docs/consigna.pdf`.
- No commitear ni hacer push sin pedido explícito. No tocar `.env`.
- Antes de dar algo por terminado: correr `poetry test` y reportar el resultado real, incluso si falla.
- Si un cambio no se puede rastrear a un RQ de la sección 3, preguntar por qué hace falta.
- Mantener este archivo al día cuando se tomen decisiones (patrón, ramas, versión de Python, requerimientos).
