"""Observadores concretos de los partidos y fábrica de notificaciones.

`fulvo/eventos.py` tiene la parte genérica del patrón Observer (el evento y
la interfaz), que usa `Partido`. Este módulo tiene las reacciones concretas,
que necesitan los modelos. Van separados para que las dependencias tengan un
solo sentido: este módulo importa `models.py` y `eventos.py`, y ninguno de los
dos lo importa a él. Si estuvieran en el mismo archivo, `models.py` y
`eventos.py` se importarían mutuamente y Python no podría cargarlos
(decisión del equipo del 2026-11-11).

Hay dos observadores: `NotificadorPartido` (RQ9), que crea los avisos con la
fábrica `FabricaNotificaciones` (patrón Factory), y `ProcesadorPostPartido`
(RQ8), que suma los partidos jugados, crea las votaciones pendientes y aplica
los no-shows (y los deshace cuando un reclamo los anula, RQ11). La fábrica
también arma la respuesta a un reclamo, que la ruta le pide directo, sin
pasar por el Observer (`clases.md`).
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fulvo.eventos import EventoPartido, ObservadorPartido, TipoEvento
from fulvo.models import (
    EstadoPostulacion,
    EstadoReclamo,
    EstadoVotacion,
    Notificacion,
    Partido,
    Postulacion,
    Reclamo,
    TipoNotificacion,
    TipoObjetivo,
    Usuario,
    Votacion,
    ahora_argentina,
)


def describir_partido(partido: Partido) -> str:
    """Día, hora y complejo, para los mensajes: "14/11 a las 20:00 en X"."""
    inicio = partido.inicio
    return f'{inicio:%d/%m} a las {inicio:%H:%M} en {partido.complejo.nombre}'


class FabricaNotificaciones:
    """Fábrica simple que arma cada `Notificacion` según su tipo (Factory).

    Es el único lugar que conoce los textos: quien necesita avisar algo le
    pide la notificación de un tipo, para un destinatario y sobre una
    referencia, y no escribe el mensaje. No hay una subclase por tipo:
    alcanza con una plantilla por tipo (`clases.md`, sección 3).
    """

    # `{partido}` es el día, la hora y el complejo, y `{jugador}` el nombre de
    # quien se postuló. El WhatsApp nunca va en el texto: lo que se guarda no
    # se puede ocultar después, si revocan al jugador o se cancela el partido
    # (decisión del equipo del 2026-11-11).
    PLANTILLAS = {
        TipoNotificacion.postulacion_recibida: (
            '{jugador} se postuló a tu partido del {partido}.'
        ),
        TipoNotificacion.postulacion_aceptada: (
            'Te aceptaron en el partido del {partido}. El WhatsApp del '
            'organizador está en tus postulaciones.'
        ),
        TipoNotificacion.postulacion_rechazada: (
            'Rechazaron tu postulación al partido del {partido}.'
        ),
        TipoNotificacion.partido_completo: (
            'El partido del {partido} se completó y tu postulación quedó '
            'afuera.'
        ),
        TipoNotificacion.postulacion_retirada: (
            '{jugador} retiró su postulación a tu partido del {partido}.'
        ),
        TipoNotificacion.revocacion: (
            'El organizador te sacó del partido del {partido}.'
        ),
        TipoNotificacion.partido_cancelado: (
            'Se canceló el partido del {partido}.'
        ),
        TipoNotificacion.votaciones_pendientes: (
            'Terminó el partido del {partido}. Tenés votaciones pendientes: '
            'puntuá a los demás jugadores y al complejo.'
        ),
        # No dice quién era el ausente: a los demás les alcanza con saber
        # que tienen votaciones para revisar.
        TipoNotificacion.votaciones_repuestas: (
            'Se anuló un no-show del partido del {partido}: revisá tus '
            'votaciones pendientes.'
        ),
        TipoNotificacion.reclamo_resuelto: (
            'Tu reclamo sobre {objetivo} fue {resultado}. Respuesta del '
            'admin: {resolucion}'
        ),
    }

    # Para la respuesta a un reclamo: sobre qué era y cómo terminó.
    OBJETIVOS = {
        TipoObjetivo.no_show: 'el no-show',
        TipoObjetivo.votacion: 'la votación',
        TipoObjetivo.usuario: 'el usuario',
        TipoObjetivo.complejo: 'el complejo',
    }
    RESULTADOS = {
        EstadoReclamo.resuelto: 'aceptado',
        EstadoReclamo.rechazado: 'rechazado',
    }

    def crear(
        self,
        tipo: TipoNotificacion,
        destinatario: Usuario,
        referencia: Partido | Postulacion | Reclamo,
    ) -> Notificacion:
        """Devuelve la notificación para `destinatario`, sin guardarla.

        `referencia` es lo que originó el aviso: una postulación, un
        partido o un reclamo. De ahí salen los datos del mensaje y la
        referencia que se guarda, así que tiene que tener id.
        """
        if isinstance(referencia, Reclamo):
            datos = {
                'objetivo': self.OBJETIVOS[referencia.tipo_objetivo],
                'resultado': self.RESULTADOS[referencia.estado],
                'resolucion': referencia.resolucion,
            }
            referencia_tipo = 'reclamo'
        elif isinstance(referencia, Postulacion):
            datos = {
                'partido': describir_partido(referencia.partido),
                'jugador': referencia.jugador.nombre,
            }
            referencia_tipo = 'postulacion'
        else:
            datos = {'partido': describir_partido(referencia)}
            referencia_tipo = 'partido'
        mensaje = self.PLANTILLAS[tipo].format(**datos)
        return Notificacion(
            usuario_id=destinatario.id,
            tipo=tipo,
            mensaje=mensaje,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia.id,
            created_at=ahora_argentina(),
        )


# Para cada evento del partido: qué notificación genera y a quién va. Es la
# tabla de `clases.md` (sección 3). Un evento que no está acá no genera
# ninguna: es el caso de `no_show_marcado`.
NOTIFICACIONES_POR_EVENTO = {
    TipoEvento.postulacion_recibida: (
        TipoNotificacion.postulacion_recibida,
        'organizador',
    ),
    TipoEvento.postulacion_aceptada: (
        TipoNotificacion.postulacion_aceptada,
        'jugador',
    ),
    TipoEvento.postulacion_rechazada: (
        TipoNotificacion.postulacion_rechazada,
        'jugador',
    ),
    TipoEvento.partido_completo: (
        TipoNotificacion.partido_completo,
        'jugador',
    ),
    TipoEvento.revocacion: (TipoNotificacion.revocacion, 'jugador'),
    TipoEvento.postulacion_retirada: (
        TipoNotificacion.postulacion_retirada,
        'organizador',
    ),
    TipoEvento.partido_cancelado: (
        TipoNotificacion.partido_cancelado,
        'postulantes',
    ),
    TipoEvento.partido_jugado: (
        TipoNotificacion.votaciones_pendientes,
        'participantes',
    ),
    # Los que vuelven a deber votos: el jugador y los demás presentes
    # (decisión del equipo del 2026-11-12).
    TipoEvento.no_show_anulado: (
        TipoNotificacion.votaciones_repuestas,
        'presentes',
    ),
}


class NotificadorPartido(ObservadorPartido):
    """Observador que crea las notificaciones de cada evento del partido.

    Decide quién recibe el aviso y le pide la notificación a la fábrica (RQ9).
    Las suma a la sesión del pedido sin confirmarlas: se guardan con el commit
    de la ruta, junto con el cambio que las originó. Si la ruta falla antes,
    no queda ninguna notificación de algo que no pasó.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.fabrica = FabricaNotificaciones()

    def actualizar(self, evento: EventoPartido) -> None:
        """Crea una notificación por destinatario, si el evento lo pide."""
        if evento.tipo not in NOTIFICACIONES_POR_EVENTO:
            return
        tipo, para = NOTIFICACIONES_POR_EVENTO[evento.tipo]
        # Una postulación recién creada todavía no tiene id. `flush` manda los
        # cambios pendientes a la base, sin confirmarlos, y así ya lo tiene.
        self.session.flush()
        if evento.postulacion is not None:
            referencia = evento.postulacion
        else:
            referencia = evento.partido
        for destinatario in self.destinatarios(evento, para):
            self.session.add(
                self.fabrica.crear(tipo, destinatario, referencia)
            )

    @staticmethod
    def destinatarios(evento: EventoPartido, para: str) -> list[Usuario]:
        """Quiénes reciben el aviso, según la tabla de arriba.

        El organizador, el jugador de la postulación, los participantes (al
        terminar el partido), los presentes (al anularse un no-show) o, si se
        cancela el partido, los que estaban en espera y los aceptados.
        """
        if para == 'organizador':
            return [evento.partido.organizador]
        if para == 'jugador':
            return [evento.postulacion.jugador]
        if para == 'participantes':
            return evento.partido.participantes()
        if para == 'presentes':
            return evento.partido.presentes()
        activas = {EstadoPostulacion.en_espera, EstadoPostulacion.aceptada}
        return [
            postulacion.jugador
            for postulacion in evento.partido.postulaciones
            if postulacion.estado in activas
        ]


class ProcesadorPostPartido(ObservadorPartido):
    """Observador que aplica lo que pasa después del partido (RQ8).

    Reacciona a tres eventos. Con `partido_jugado` suma un partido jugado a
    cada participante y crea sus votaciones pendientes. Con
    `no_show_marcado` deshace eso para el ausente y le suma un voto de 0
    estrellas. Con `no_show_anulado` (RQ11) vuelve todo atrás. Así `Partido`
    no sabe nada de votaciones ni de puntuaciones: solo avisa (`clases.md`,
    sección 3).

    Como `NotificadorPartido`, deja los cambios en la sesión del pedido y
    los guarda el commit de la ruta, junto con el cambio de estado.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def actualizar(self, evento: EventoPartido) -> None:
        """Atiende el pase a jugado y los no-shows; ignora el resto."""
        if evento.tipo == TipoEvento.partido_jugado:
            self.cerrar_partido(evento.partido)
        elif evento.tipo == TipoEvento.no_show_marcado:
            self.aplicar_no_show(evento.partido, evento.postulacion.jugador)
        elif evento.tipo == TipoEvento.no_show_anulado:
            self.anular_no_show(evento.partido, evento.postulacion.jugador)

    def cerrar_partido(self, partido: Partido) -> None:
        """Suma el partido jugado y crea las votaciones pendientes.

        Cada participante vota a los demás participantes y al complejo
        (`requerimientos.md`). Las votaciones se suman a la lista del emisor
        (`Usuario.votaciones`), y con eso SQLAlchemy las guarda en el commit.
        """
        # Como en `NotificadorPartido`: `flush` manda a la base lo pendiente,
        # sin confirmarlo. SQLAlchemy no carga las relaciones de un objeto
        # que todavía no se mandó (el jugador de una postulación recién
        # aceptada), y acá hacen falta para saber quiénes participaron.
        self.session.flush()
        participantes = partido.participantes()
        ahora = ahora_argentina()
        for emisor in participantes:
            emisor.sumar_partido_jugado()
            for receptor in participantes:
                if receptor is not emisor:
                    emisor.votaciones.append(
                        Votacion(
                            partido_id=partido.id,
                            emisor_id=emisor.id,
                            created_at=ahora,
                            receptor_usuario_id=receptor.id,
                        )
                    )
            emisor.votaciones.append(
                Votacion(
                    partido_id=partido.id,
                    emisor_id=emisor.id,
                    created_at=ahora,
                    receptor_complejo_id=partido.complejo_id,
                )
            )

    def aplicar_no_show(self, partido: Partido, ausente: Usuario) -> None:
        """Le resta el partido jugado al ausente y le suma un voto de 0.

        También borra las votaciones pendientes de este partido en las que
        el ausente vota o es votado: no jugó, y el no-show ya cuenta como su
        voto (decisión del equipo del 2026-11-11). Las ya emitidas quedan.
        Para borrarlas se sacan de la lista de su emisor (`delete-orphan`).
        """
        ausente.restar_partido_jugado()
        ausente.registrar_puntuacion(0)
        pendientes = self.session.scalars(
            select(Votacion).where(
                Votacion.partido_id == partido.id,
                Votacion.estado == EstadoVotacion.pendiente,
                or_(
                    Votacion.emisor_id == ausente.id,
                    Votacion.receptor_usuario_id == ausente.id,
                ),
            )
        ).all()
        for votacion in pendientes:
            votacion.emisor.votaciones.remove(votacion)

    def anular_no_show(self, partido: Partido, jugador: Usuario) -> None:
        """Vuelve atrás un no-show que anuló un reclamo (RQ11).

        Le devuelve el partido jugado, le quita el voto de 0 y repone las
        votaciones pendientes que se habían borrado: las suyas y las de los
        demás hacia él, como si el no-show no hubiera existido (decisión del
        equipo del 2026-11-12). Solo entre los presentes: con alguien que
        sigue marcado como ausente no se vota. Una votación que ya existe,
        por ejemplo porque se emitió antes del no-show, no se repite.
        """
        jugador.sumar_partido_jugado()
        jugador.quitar_puntuacion(0)
        existentes = {
            (v.emisor_id, v.receptor_usuario_id, v.receptor_complejo_id)
            for v in self.session.scalars(
                select(Votacion).where(Votacion.partido_id == partido.id)
            )
        }
        # (emisor, usuario votado, complejo votado): uno de los dos votados
        # queda vacío, como en la tabla.
        faltantes = [(jugador, None, partido.complejo_id)]
        for otro in partido.presentes():
            if otro.id != jugador.id:
                faltantes.append((jugador, otro.id, None))
                faltantes.append((otro, jugador.id, None))
        ahora = ahora_argentina()
        for emisor, usuario_id, complejo_id in faltantes:
            if (emisor.id, usuario_id, complejo_id) in existentes:
                continue
            emisor.votaciones.append(
                Votacion(
                    partido_id=partido.id,
                    emisor_id=emisor.id,
                    created_at=ahora,
                    receptor_usuario_id=usuario_id,
                    receptor_complejo_id=complejo_id,
                )
            )
