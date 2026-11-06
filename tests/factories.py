import factory

from fulvo.models import Usuario
from fulvo.security import hashear_contrasena
from tests.datos import CONTRASENA, hoy_menos_anios


class UsuarioFactory(factory.Factory):
    """Construye usuarios de prueba con datos válidos por defecto.

    No guarda el usuario: el `add` y el `commit` quedan en la fixture. La
    contraseña se guarda hasheada; el texto en claro está en `CONTRASENA`.
    `rol_id` lo pasa quien crea el usuario (depende de los roles cargados).
    """

    class Meta:
        model = Usuario

    # Secuencia para que cada usuario tenga un email único sin repetir el
    # valor a mano en cada test.
    email = factory.Sequence(lambda n: f'jugador{n}@ejemplo.com')
    contrasena_hash = factory.LazyFunction(
        lambda: hashear_contrasena(CONTRASENA)
    )
    nombre = 'Ana'
    apellido = 'Pérez'
    whatsapp = '+5491100000000'
    fecha_nacimiento = factory.LazyFunction(lambda: hoy_menos_anios(30))
    posicion = 'Delantera'
