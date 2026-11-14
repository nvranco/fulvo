from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fulvo.errores import ReglaDeNegocioError
from fulvo.routes import (
    auth,
    complejos,
    notificaciones,
    partidos,
    postulaciones,
    reclamos,
    sanciones,
    usuarios,
    votaciones,
    zonas,
)
from fulvo.settings import Settings

app = FastAPI()

# CORS. El navegador solo deja que el JavaScript de una página lea las
# respuestas de otro origen (protocolo, dominio y puerto) si ese servidor lo
# permite con los encabezados `Access-Control-Allow-*`. Lo necesita un front
# que corre en otra dirección que la API. Swagger (/docs, que sale de la
# misma API), Postman, curl y los tests no, porque no son una página de
# otro origen. Antes de un pedido con el token o con JSON, el navegador
# manda un OPTIONS de consulta (preflight), que el middleware responde sin
# llegar a las rutas. CORS protege al usuario en el navegador, no a la API:
# a la API la sigue protegiendo el JWT.
app.add_middleware(
    CORSMiddleware,
    # La lista del `.env`, vacía por defecto (ver fulvo/settings.py).
    allow_origins=Settings().CORS_ORIGINS,
    # Solo los métodos que usa la API.
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    # El token JWT viaja en Authorization. Content-Type, para mandar JSON,
    # el middleware ya lo permite siempre. Sin `allow_credentials`: la API
    # no usa cookies.
    allow_headers=['Authorization'],
)

app.include_router(complejos.router)
app.include_router(zonas.router)
app.include_router(usuarios.router)
app.include_router(auth.router)
app.include_router(partidos.router)
app.include_router(postulaciones.router)
app.include_router(notificaciones.router)
app.include_router(votaciones.router)
app.include_router(sanciones.router)
app.include_router(reclamos.router)


@app.exception_handler(ReglaDeNegocioError)
def responder_regla_de_negocio(request: Request, error: ReglaDeNegocioError):
    """Traduce los errores del dominio a 409, en un solo lugar.

    Los modelos levantan `ReglaDeNegocioError` sin saber nada de HTTP (por
    ejemplo, al aceptar una postulación ya rechazada). Acá se responde 409
    con el mensaje del error como `detail`, el mismo formato que
    `HTTPException` (`CLAUDE.md`, sección 7).
    """
    return JSONResponse(
        status_code=HTTPStatus.CONFLICT, content={'detail': str(error)}
    )


@app.get('/')
def leer_raiz():
    """Ruta mínima para comprobar que el entorno funciona."""
    return {'mensaje': 'Hola Fulvo!'}
