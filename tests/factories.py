from datetime import timedelta

import factory

from fulvo.models import Partido, TipoPartido, Usuario, ahora_argentina
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


class PartidoFactory(factory.Factory):
    """Construye partidos de prueba: F5, con 2 cupos y dentro de una semana.

    No los guarda. `organizador_id` y `complejo_id` los pasa quien crea el
    partido, porque dependen de los datos de cada test. Como en el aula 10,
    `PartidoFactory.create_batch(5, ...)` arma varios de una vez.
    """

    class Meta:
        model = Partido

    # LazyFunction: la fecha se calcula al crear cada partido, no una sola
    # vez al importar el módulo (así funciona con freezegun).
    inicio = factory.LazyFunction(
        lambda: ahora_argentina().replace(microsecond=0) + timedelta(days=7)
    )
    tipo = TipoPartido.F5
    cupos_faltantes = 2
