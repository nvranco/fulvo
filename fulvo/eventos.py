"""Patrón Observer de los partidos (`docs/clases.md`, sección 3).

`Partido` es el sujeto: cuando le pasa algo, arma un `EventoPartido` y se lo
pasa a cada uno de sus observadores. No sabe quién reacciona ni cómo, así que
sumar una consecuencia nueva (una notificación, una votación pendiente) no lo
modifica.

Hoy el módulo tiene el evento y la interfaz. Los observadores concretos
llegan con sus requerimientos: `NotificadorPartido` y la fábrica
`FabricaNotificaciones` con las notificaciones (RQ9), y
`ProcesadorPostPartido` con las votaciones (RQ8). Todos van en este módulo
(decisión del equipo del 2026-11-11).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Solo para anotar los tipos. `models.py` importa este módulo, así que
    # importar `models` acá de forma normal sería un import circular.
    from fulvo.models import Partido, Postulacion


class TipoEvento(str, Enum):
    """Lo que le puede pasar a un partido: los 9 eventos de `clases.md`."""

    postulacion_recibida = 'postulacion_recibida'
    postulacion_aceptada = 'postulacion_aceptada'
    postulacion_rechazada = 'postulacion_rechazada'
    partido_completo = 'partido_completo'
    revocacion = 'revocacion'
    postulacion_retirada = 'postulacion_retirada'
    partido_cancelado = 'partido_cancelado'
    partido_jugado = 'partido_jugado'
    no_show_marcado = 'no_show_marcado'


@dataclass(frozen=True)
class EventoPartido:
    """Lo que recibe cada observador: qué pasó, en qué partido y con qué
    postulación, si el evento nace de una.

    Es inmutable (`frozen=True`): todos los observadores reciben el mismo
    evento y ninguno puede cambiárselo a los demás.
    """

    tipo: TipoEvento
    partido: 'Partido'
    postulacion: 'Postulacion | None' = None


class ObservadorPartido(ABC):
    """Interfaz de los observadores de un partido.

    Es una clase abstracta: Python no deja crear un observador que no
    implemente `actualizar`. Así `Partido` puede llamar a `actualizar` en
    cualquiera sin saber de qué clase es.
    """

    @abstractmethod
    def actualizar(self, evento: EventoPartido) -> None:
        """Reacciona a un evento del partido."""
