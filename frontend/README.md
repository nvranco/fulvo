# Front de demostración de fulvo

Interfaz web para **mostrar el MVP** en la presentación. No es un entregable de la consigna (la consigna es la API): solo consume los endpoints que ya existen, sin agregar ninguno.

## Qué muestra

| Pantalla | Qué hace | RQ |
|---|---|---|
| Ingresar / Registrarme | Login OAuth2 y registro (edad mínima 16, la valida la API) | RQ1 |
| Encabezado | Perfil propio: posición, puntuación y partidos jugados | RQ2 |
| Mapa de canchas | Los 51 complejos en un mapa (verde = tiene partidos abiertos). Click en el mapa = búsqueda de cercanos por radio | RQ3 |
| Publicar partido | Complejo, fecha y hora, tipo y cupos faltantes (duración fija de 60 min) | RQ4 |
| Partidos abiertos | Listado con filtros por zona, tipo y complejo, y botón Postularme | RQ5 |
| Mis partidos | Lista de espera de cada partido propio: aceptar, rechazar, revocar y cancelar. Al aceptar aparece el WhatsApp. En los partidos jugados, botón "No vino" para marcar un no-show | RQ6, RQ7, RQ8 |
| Mis postulaciones | Estado de cada postulación, WhatsApp del organizador si te aceptaron, retirarse o bajarse | RQ5 a RQ7 |
| Notificaciones | Avisos creados por `NotificadorPartido` (Observer), con contador de no leídas | RQ9 |
| Votaciones | Tres pestañas: pendientes (agrupadas por partido, de 0 a 5 estrellas), emitidas y recibidas (sin mostrar quién votó). Desde recibidas se puede reclamar un voto. Un banner muestra la deuda: avisa si la deuda es mayor que 0 y, cuando no está habilitado, bloquea el mensaje de publicar y postularse y ofrece ir a votar | RQ8, RQ11 |
| Reclamos | Denunciar a un usuario (por id) o a un complejo, y ver el estado y la resolución de los propios. Los de no-show y de votación se abren desde Mis postulaciones y desde Votaciones › Recibidas | RQ11 |
| Admin | Solo aparece si la API confirma que sos admin. Resolver o rechazar reclamos (al dar la razón a una denuncia contra un usuario se puede bloquear), ver el historial de sanciones y bloquear o desbloquear por id de usuario | RQ10, RQ11 |

## Cómo levantarlo

Necesita [Node.js](https://nodejs.org/) 22.12 o más nuevo (Vite 8 también acepta la 20, desde la 20.19) y la API corriendo. En Windows se instala con `winget install OpenJS.NodeJS.LTS`.

```bash
# Terminal 1, en la raíz del repo: la API
poetry serve

# Terminal 2: el front
cd frontend
npm install        # solo la primera vez
npm run dev
```

Abrir http://localhost:5173.

Para la demo conviene usar dos navegadores (o una ventana normal y otra de incógnito) con dos usuarios: uno organiza y el otro se postula. Así se ve aparecer el WhatsApp de los dos lados al aceptar.

## Datos de demo

Votaciones y reclamos no se pueden mostrar haciendo clic: las votaciones se crean recién cuando un partido termina (inicio + 60 minutos) y la API no deja publicar partidos en el pasado. `frontend/sembrar_demo.py` arma un partido ya jugado, con postulantes aceptados, un no-show y votos emitidos, usando los mismos métodos del dominio y observadores que la API.

Desde la raíz del repo, con la base migrada:

```bash
poetry run alembic upgrade head
poetry run python -m fulvo.carga_inicial    # roles, complejos y admin (ADMIN_EMAIL y ADMIN_PASSWORD en el .env)
poetry run python frontend/sembrar_demo.py  # datos de demo
```

El script escribe en la base de `DATABASE_URL` (el `.env`), igual que la carga inicial. Es idempotente: si `org@demo.fulvo` ya existe, no hace nada. Todos los usuarios de demo tienen la contraseña `demo1234`.

| Usuario | Qué probar |
|---|---|
| `org@demo.fulvo` | Mis partidos: el partido jugado, con el no-show de Beto. Votaciones pendientes. |
| `ana@demo.fulvo` | Votaciones recibidas (las de Caro) para reclamar una, y sus votaciones pendientes. Tiene un partido abierto para mañana a las 20. |
| `beto@demo.fulvo` | Mis postulaciones: reclamar el no-show que le marcaron. |
| `caro@demo.fulvo` | Ya votó a todos: solo emitidas, sin pendientes. |
| Admin (`ADMIN_EMAIL`) | Resolver o rechazar los reclamos. |

## Decisiones (para la defensa)

- **React + Vite, sin router ni librerías de estado.** Las pestañas son un `useState`. Las únicas dependencias son `react`, `leaflet` y `react-leaflet`.
- **Proxy de Vite en vez de CORS.** El front le pide todo a `/api/...` y Vite lo reenvía a `http://127.0.0.1:8000` (`vite.config.js`). El navegador ve un solo origen, así que la API no se toca. Para apuntar a otra API: `FULVO_API=https://... npm run dev`.
- **Un solo módulo habla con la API** (`src/api.js`): agrega el token, manda el login como formulario OAuth2 y traduce el `detail` de los errores (texto en los 401/403/404/409, lista en los 422) a un mensaje.
- **Las reglas viven en la API.** El front solo limita los formularios (por ejemplo, el máximo de cupos según el tipo) para que sea más cómodo. Si algo no se puede, la API responde 409 o 422 y el front muestra el motivo tal cual.
- **"Mis partidos" sin endpoint nuevo.** `GET /partidos` devuelve solo los abiertos. El front junta tres fuentes: los abiertos donde el usuario es organizador, los partidos de sus votaciones (así se ven también los jugados) y los ids que publicó desde ese navegador (`localStorage`). Un `GET /partidos?organizador=yo` sería más prolijo, pero no está en ningún RQ.
- **Admin sin rol en el perfil.** El perfil no trae el rol, así que el front detecta al admin llamando a `GET /usuarios/{id}/sanciones?limit=1`: 200 significa admin y 403, cualquier otro usuario. No hay endpoint para listar usuarios, así que el admin trabaja con ids que vienen de los reclamos o que escribe a mano.
- **Fechas sin conversión.** La API usa hora de Argentina sin zona horaria. El front la muestra partiendo el texto y la manda igual, sin pasar por `Date`.
