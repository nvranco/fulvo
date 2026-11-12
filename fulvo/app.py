from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fulvo.errores import ReglaDeNegocioError
from fulvo.routes import (
    auth,
    complejos,
    notificaciones,
    partidos,
    postulaciones,
    sanciones,
    usuarios,
    votaciones,
    zonas,
)

app = FastAPI()
app.include_router(complejos.router)
app.include_router(zonas.router)
app.include_router(usuarios.router)
app.include_router(auth.router)
app.include_router(partidos.router)
app.include_router(postulaciones.router)
app.include_router(notificaciones.router)
app.include_router(votaciones.router)
app.include_router(sanciones.router)


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
