from fastapi import FastAPI

from fulvo.routes import auth, complejos, partidos, usuarios, zonas

app = FastAPI()
app.include_router(complejos.router)
app.include_router(zonas.router)
app.include_router(usuarios.router)
app.include_router(auth.router)
app.include_router(partidos.router)


@app.get('/')
def leer_raiz():
    """Ruta mínima para comprobar que el entorno funciona."""
    return {'mensaje': 'Hola Fulvo!'}
