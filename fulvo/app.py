from fastapi import FastAPI

from fulvo.routes import complejos, zonas

app = FastAPI()
app.include_router(complejos.router)
app.include_router(zonas.router)


@app.get('/')
def leer_raiz():
    """Ruta mínima para comprobar que el entorno funciona."""
    return {'mensaje': 'Hola Fulvo!'}
