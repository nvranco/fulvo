class Secuencia:
    """Entrega ids consecutivos y nunca repite uno, aunque se borre datos.

    Cumple el papel de la secuencia de la base de datos. Con `max(id) + 1`,
    borrar el último elemento y crear otro reutilizaría su id, y un cliente
    que guardó ese id vería un recurso distinto en lugar de un 404.
    """

    def __init__(self, ultimo: int = 0) -> None:
        self.ultimo = ultimo

    def siguiente(self) -> int:
        """Devuelve el próximo id y lo da por usado."""
        self.ultimo += 1
        return self.ultimo
