class ReglaDeNegocioError(Exception):
    """Una acción que las reglas del dominio no permiten.

    La levantan los modelos (por ejemplo, al aceptar una postulación que ya
    fue rechazada) sin saber nada de HTTP. `app.py` la traduce a un 409 en
    un solo lugar, como pide `CLAUDE.md` (sección 7): la acción choca con el
    estado actual del recurso. El mensaje es el `detail` de la respuesta.
    """
