from fastapi import FastAPI

app = FastAPI()


@app.get('/')
def leer_raiz():
    """Ruta mínima para comprobar que el entorno funciona."""
    return {'mensaje': 'Hola Mundo!'}
