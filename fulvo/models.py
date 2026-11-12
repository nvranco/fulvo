from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as EnumSQL
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
    reconstructor,
    registry,
    relationship,
)

from fulvo.errores import ReglaDeNegocioError
from fulvo.eventos import EventoPartido, ObservadorPartido, TipoEvento
from fulvo.settings import LIMITE_DEUDA

# Registro de todos los modelos: guarda las tablas (`table_registry.metadata`)
# para que Alembic y los tests puedan crearlas.
table_registry = registry()


@mapped_as_dataclass(table_registry)
class Zona:
    """Un partido o un barrio (Vicente López, Belgrano), con su provincia."""

    __tablename__ = 'zonas'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)
    provincia: Mapped[str]


@mapped_as_dataclass(table_registry)
class Complejo:
    """Lugar donde se juegan partidos. Pertenece a una zona.

    Los campos sin valor por defecto van primero y los opcionales al final
    porque así lo exige una dataclass. La provincia no se guarda acá: se
    lee de la zona.
    """

    __tablename__ = 'complejos'
    __table_args__ = (
        # Mismo criterio que el 409 de la API: un nombre por dirección.
        UniqueConstraint('nombre', 'direccion'),
        # SQLite reutiliza el id de la última fila borrada; con esto no,
        # igual que PostgreSQL. Sin efecto en PostgreSQL.
        {'sqlite_autoincrement': True},
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    zona_id: Mapped[int] = mapped_column(ForeignKey('zonas.id'))
    localidad: Mapped[str]
    nombre: Mapped[str]
    direccion: Mapped[str]
    tipo: Mapped[str]
    latitud: Mapped[float]
    longitud: Mapped[float]
    reserva_online: Mapped[bool] = mapped_column(default=False)
    telefono_contacto: Mapped[str | None] = mapped_column(default=None)
    sitio_web: Mapped[str | None] = mapped_column(default=None)
    calificacion_maps: Mapped[float | None] = mapped_column(default=None)
    link_maps: Mapped[str | None] = mapped_column(default=None)
    # Calculadas con las votaciones de la app (RQ8), como las del usuario.
    # No se mezclan con `calificacion_maps`, que es la de Google Maps.
    puntuacion_promedio: Mapped[float | None] = mapped_column(default=None)
    cantidad_puntuaciones: Mapped[int] = mapped_column(default=0)

    # Se carga sola a partir de zona_id: al crear un Complejo se pasa
    # `zona_id`, no `zona`. Solo en este sentido (muchos a uno).
    zona: Mapped[Zona] = relationship(init=False)

    def registrar_puntuacion(self, estrellas: int) -> None:
        """Suma un voto y recalcula el promedio (RQ8).

        Es el mismo cálculo que `Usuario.registrar_puntuacion`, repetido a
        propósito: son cuatro líneas y cada clase se lee sola, sin una clase
        base `Puntuable` (`clases.md`).
        """
        cantidad = self.cantidad_puntuaciones + 1
        suma = (self.puntuacion_promedio or 0) * self.cantidad_puntuaciones
        self.puntuacion_promedio = (suma + estrellas) / cantidad
        self.cantidad_puntuaciones = cantidad


# Nombres de los roles base. Se crean con la carga inicial (no hay endpoint
# que los cree) y ningún endpoint público asigna el rol admin.
ROL_USUARIO = 'usuario'
ROL_ADMIN = 'admin'
ROLES_BASE = (ROL_USUARIO, ROL_ADMIN)

# Edad mínima para registrarse (RQ1).
EDAD_MINIMA = 16


@mapped_as_dataclass(table_registry)
class Rol:
    """Rol de un usuario (usuario, admin). Es solo un dato, sin métodos.

    Es una tabla y no un booleano `es_admin` para poder sumar roles nuevos
    sin tocar el modelo `Usuario`. La validación de permisos está en
    `Usuario.tiene_rol`.
    """

    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)


@mapped_as_dataclass(table_registry)
class Usuario:
    """Persona registrada. Absorbe el perfil de jugador (relación 1 a 1).

    `puntuacion_promedio`, `cantidad_puntuaciones` y `partidos_jugados` son
    calculados por la app (solo lectura para el usuario): por eso no se
    reciben al registrarse. `puntuacion_promedio` queda vacío hasta el
    primer voto. La contraseña nunca se guarda: solo su hash (argon2).
    """

    __tablename__ = 'usuarios'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    # El email es el identificador de login, por eso es único (409 en la API).
    email: Mapped[str] = mapped_column(unique=True)
    contrasena_hash: Mapped[str]
    nombre: Mapped[str]
    apellido: Mapped[str]
    whatsapp: Mapped[str]
    fecha_nacimiento: Mapped[date]
    # No hay lista cerrada de posiciones en la documentación, así que es
    # texto libre por ahora.
    posicion: Mapped[str]
    rol_id: Mapped[int] = mapped_column(ForeignKey('roles.id'))
    bloqueado: Mapped[bool] = mapped_column(default=False)
    puntuacion_promedio: Mapped[float | None] = mapped_column(default=None)
    cantidad_puntuaciones: Mapped[int] = mapped_column(default=0)
    partidos_jugados: Mapped[int] = mapped_column(default=0)

    # Se carga sola a partir de rol_id: al crear un Usuario se pasa
    # `rol_id`, no `rol` (mismo criterio que Complejo.zona).
    rol: Mapped[Rol] = relationship(init=False)
    # Las votaciones que el usuario tiene que emitir o ya emitió (RQ8).
    # `foreign_keys` dice cuál de las dos columnas de `votaciones` que apuntan
    # a usuarios es la de esta lista: el emisor (la otra es el receptor). Con
    # `delete-orphan`, sacar una votación de la lista la borra de la base: una
    # votación no existe sin su emisor. Por eso también se crean sumándolas a
    # esta lista, como las postulaciones de un partido.
    votaciones: Mapped[list['Votacion']] = relationship(
        init=False,
        back_populates='emisor',
        foreign_keys='Votacion.emisor_id',
        cascade='all, delete-orphan',
        order_by='Votacion.id',
    )

    def edad(self, hoy: date) -> int:
        """Devuelve los años cumplidos a la fecha `hoy`.

        Recibe `hoy` en vez de leer el reloj para poder probarla con
        fechas fijas. Se usa para la edad mínima de 16 al registrarse.
        """
        cumplio = (hoy.month, hoy.day) >= (
            self.fecha_nacimiento.month,
            self.fecha_nacimiento.day,
        )
        return hoy.year - self.fecha_nacimiento.year - (not cumplio)

    def tiene_rol(self, nombre: str) -> bool:
        """Dice si el rol del usuario es `nombre`: único punto de permisos."""
        return self.rol.nombre == nombre

    def registrar_puntuacion(self, estrellas: int) -> None:
        """Suma un voto y recalcula el promedio (RQ8).

        Los votos no se guardan uno por uno en el usuario: la suma de los
        anteriores es el promedio por la cantidad, así que alcanza con esas
        dos columnas. Un no-show cuenta como un voto de 0 (`clases.md`).
        """
        cantidad = self.cantidad_puntuaciones + 1
        suma = (self.puntuacion_promedio or 0) * self.cantidad_puntuaciones
        self.puntuacion_promedio = (suma + estrellas) / cantidad
        self.cantidad_puntuaciones = cantidad

    def sumar_partido_jugado(self) -> None:
        """Suma 1 a los partidos jugados: al pasar un partido a jugado."""
        self.partidos_jugados += 1

    def restar_partido_jugado(self) -> None:
        """Resta 1 a los partidos jugados: al marcarle un no-show."""
        self.partidos_jugados -= 1

    def votaciones_pendientes(self) -> list['Votacion']:
        """Votaciones que todavía tiene que emitir, de cualquier partido."""
        return [
            votacion
            for votacion in self.votaciones
            if votacion.estado == EstadoVotacion.pendiente
        ]

    def deuda(self) -> int:
        """Cuenta los partidos en los que le queda alguna votación pendiente.

        La deuda cuenta por partido y no por votación (`clases.md`): un
        partido con cinco votos pendientes suma 1, igual que uno con uno solo.
        """
        return len({v.partido_id for v in self.votaciones_pendientes()})

    def habilitado(self) -> bool:
        """Dice si puede publicar y postularse: si la deuda no supera X."""
        return self.deuda() <= LIMITE_DEUDA

    def exigir_habilitado(self) -> None:
        """Levanta `ReglaDeNegocioError` (409) si la deuda no lo deja seguir.

        El mensaje dice en cuántos partidos debe votos, cuántos tiene que
        completar para volver a estar habilitado y cuántas votaciones le
        faltan en total (decisión del equipo del 2026-11-11). Lo usan
        `Partido.postular` y la ruta que publica partidos.
        """
        if self.habilitado():
            return
        deuda = self.deuda()
        a_completar = deuda - LIMITE_DEUDA
        partidos = 'partido' if a_completar == 1 else 'partidos'
        raise ReglaDeNegocioError(
            f'Tenés votaciones pendientes en {deuda} partidos y el máximo es '
            f'{LIMITE_DEUDA}: completá las de al menos {a_completar} '
            f'{partidos} para publicar o postularte (te faltan '
            f'{len(self.votaciones_pendientes())} votaciones).'
        )


# Argentina usa un solo huso horario (UTC-3) y no cambia la hora en verano
# desde 2009, así que alcanza con un desfase fijo. Así no se depende de la
# base de husos horarios (tzdata), que Python no trae en Windows.
HORA_ARGENTINA = timezone(timedelta(hours=-3))


def ahora_argentina() -> datetime:
    """Fecha y hora actual de Argentina, sin zona horaria.

    Los partidos guardan su inicio como hora de Argentina sin zona, porque
    SQLite no guarda zonas horarias y PostgreSQL sí: sin zona, las dos bases
    guardan y devuelven lo mismo. Toda comparación con un inicio usa esta
    función, así ninguna depende de la hora de la máquina donde corre la API.
    """
    return datetime.now(HORA_ARGENTINA).replace(tzinfo=None)


class TipoPartido(str, Enum):
    """Modalidad del partido, según cuántos juegan por equipo (RQ4)."""

    F5 = 'F5'
    F7 = 'F7'
    F8 = 'F8'
    F11 = 'F11'


# Jugadores en cancha, sumando los dos equipos. El organizador juega, así
# que en un partido pueden faltar como mucho todos menos uno.
JUGADORES_POR_TIPO = {
    TipoPartido.F5: 10,
    TipoPartido.F7: 14,
    TipoPartido.F8: 16,
    TipoPartido.F11: 22,
}

# Todo partido dura 60 minutos: es fijo por decisión del equipo
# (2026-11-11) y el organizador no lo elige al publicar.
DURACION_PARTIDO_MINUTOS = 60


class EstadoPartido(str, Enum):
    """Estados de un partido (`docs/requerimientos.md`, sección 4)."""

    abierto = 'abierto'
    completo = 'completo'
    jugado = 'jugado'
    cancelado = 'cancelado'


def exigir(condicion: bool, mensaje: str) -> None:
    """Levanta `ReglaDeNegocioError` con `mensaje` si no se cumple la regla.

    Así cada regla del dominio se lee en una línea: `exigir(condición,
    motivo)`. La API la responde como 409 (`app.py`).
    """
    if not condicion:
        raise ReglaDeNegocioError(mensaje)


@mapped_as_dataclass(table_registry)
class Partido:
    """Partido publicado por un organizador al que le faltan jugadores (RQ4).

    Es el sujeto del patrón Observer (`docs/clases.md` y `fulvo/eventos.py`):
    toda acción sobre el partido o sus postulaciones pasa por un método de
    esta clase, que cambia el estado y avisa con un `EventoPartido` a sus
    observadores. No sabe quiénes son ni qué hacen con el aviso.
    """

    __tablename__ = 'partidos'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    organizador_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    complejo_id: Mapped[int] = mapped_column(ForeignKey('complejos.id'))
    inicio: Mapped[datetime]
    # Los enums se guardan como texto (`native_enum=False`). En PostgreSQL
    # un enum nativo es un tipo aparte, que Alembic no borra solo al deshacer
    # la migración. Como texto, SQLite y PostgreSQL guardan lo mismo, y la
    # lista de valores válidos la controla Python.
    tipo: Mapped[TipoPartido] = mapped_column(
        EnumSQL(TipoPartido, native_enum=False)
    )
    cupos_faltantes: Mapped[int]
    # Se guarda aunque hoy sea siempre la misma: `fin()` la usa, y si la
    # regla cambia no hace falta migrar los partidos que ya existen.
    duracion_minutos: Mapped[int] = mapped_column(
        default=DURACION_PARTIDO_MINUTOS
    )
    estado: Mapped[EstadoPartido] = mapped_column(
        EnumSQL(EstadoPartido, native_enum=False),
        default=EstadoPartido.abierto,
    )

    # Se cargan solas a partir de los ids, como `Complejo.zona`.
    organizador: Mapped[Usuario] = relationship(init=False)
    complejo: Mapped[Complejo] = relationship(init=False)
    # Las postulaciones del partido, en el orden en que llegaron. Al sumar
    # una a esta lista, SQLAlchemy la guarda con el partido en el commit.
    postulaciones: Mapped[list['Postulacion']] = relationship(
        init=False, back_populates='partido', order_by='Postulacion.id'
    )

    def __post_init__(self) -> None:
        """Arranca sin observadores. Corre al crear un partido nuevo.

        Los observadores no son una columna: viven solo en memoria mientras
        dura el pedido, y cada ruta suma los que necesita.
        """
        self.observadores: list[ObservadorPartido] = []

    @reconstructor
    def al_leerse_de_la_base(self) -> None:
        """Hace lo mismo que `__post_init__` con los partidos de la base.

        SQLAlchemy no llama a `__init__` (ni a `__post_init__`) cuando trae
        un objeto de la base: arma el objeto y llama a los métodos marcados
        con `@reconstructor`. Sin esto, un partido leído no tendría lista de
        observadores.
        """
        self.__post_init__()

    def agregar_observador(self, observador: ObservadorPartido) -> None:
        """Suma un observador, que va a recibir los eventos del partido."""
        self.observadores.append(observador)

    def quitar_observador(self, observador: ObservadorPartido) -> None:
        """Deja de avisarle a un observador."""
        self.observadores.remove(observador)

    def notificar(self, evento: EventoPartido) -> None:
        """Pasa el evento a cada observador, en el orden en que se sumaron."""
        for observador in self.observadores:
            observador.actualizar(evento)

    def avisar(
        self, tipo: TipoEvento, postulacion: 'Postulacion | None' = None
    ) -> None:
        """Arma el `EventoPartido` y lo notifica a los observadores."""
        self.notificar(EventoPartido(tipo, self, postulacion))

    def fin(self) -> datetime:
        """Devuelve cuándo termina el partido: el inicio más la duración."""
        return self.inicio + timedelta(minutes=self.duracion_minutos)

    def en_juego(self) -> bool:
        """Dice si el partido sigue vigente: abierto o completo."""
        return self.estado in {EstadoPartido.abierto, EstadoPartido.completo}

    def participantes(self) -> list[Usuario]:
        """El organizador y los jugadores aceptados: los que juegan (RQ8).

        No es una clase aparte: sale de las postulaciones (`clases.md`). Son
        los que suman el partido jugado y se votan entre sí.
        """
        aceptados = [
            postulacion.jugador
            for postulacion in self.postulaciones
            if postulacion.estado == EstadoPostulacion.aceptada
        ]
        return [self.organizador, *aceptados]

    def actualizar_estado(self, ahora: datetime) -> bool:
        """Pasa el partido a jugado si ya terminó, y dice si cambió.

        No hay una tarea periódica: se llama cada vez que se consulta el
        partido (`docs/requerimientos.md`). Solo cambian los abiertos y los
        completos: uno cancelado sigue cancelado aunque ya haya pasado su
        fecha. Recibe `ahora` en vez de leer el reloj para poder probarlo
        con fechas fijas, como `Usuario.edad`. Si cambia, emite
        `partido_jugado`.
        """
        if self.en_juego() and ahora >= self.fin():
            self.estado = EstadoPartido.jugado
            self.avisar(TipoEvento.partido_jugado)
            return True
        return False

    def postular(self, jugador: Usuario, ahora: datetime) -> 'Postulacion':
        """Crea la postulación del jugador, en espera, y la devuelve (RQ5).

        El partido tiene que estar abierto y sin empezar, el jugador no
        puede ser el organizador y no puede tener otra postulación a este
        partido, aunque la anterior se haya retirado o rechazado (decisión
        del equipo del 2026-11-11). Tampoco puede deber votaciones en más
        de X partidos (bloqueo por deuda, RQ8).
        """
        exigir(
            self.estado == EstadoPartido.abierto, 'El partido no está abierto'
        )
        exigir(ahora < self.inicio, 'El partido ya empezó')
        exigir(
            jugador.id != self.organizador_id,
            'El organizador no puede postularse a su propio partido',
        )
        exigir(
            all(p.jugador_id != jugador.id for p in self.postulaciones),
            'El jugador ya se postuló a este partido',
        )
        jugador.exigir_habilitado()
        postulacion = Postulacion(
            partido_id=self.id, jugador_id=jugador.id, created_at=ahora
        )
        self.postulaciones.append(postulacion)
        self.avisar(TipoEvento.postulacion_recibida, postulacion)
        return postulacion

    def aceptar(self, postulacion: 'Postulacion', ahora: datetime) -> None:
        """Acepta una postulación en espera y resta un cupo (RQ6).

        Si los cupos llegan a 0, el partido pasa a completo y las
        postulaciones que seguían en espera pasan a rechazadas. Por cada una
        se emite `partido_completo`, porque el aviso es para cada postulante
        que quedó afuera (`clases.md`).
        """
        exigir(
            self.estado == EstadoPartido.abierto, 'El partido no está abierto'
        )
        postulacion.aceptar(ahora)
        self.cupos_faltantes -= 1
        self.avisar(TipoEvento.postulacion_aceptada, postulacion)
        if self.cupos_faltantes == 0:
            self.estado = EstadoPartido.completo
            for otra in self.postulaciones:
                if otra.estado == EstadoPostulacion.en_espera:
                    otra.rechazar(ahora)
                    self.avisar(TipoEvento.partido_completo, otra)

    def rechazar(self, postulacion: 'Postulacion', ahora: datetime) -> None:
        """Rechaza una postulación en espera (RQ6)."""
        exigir(
            self.estado == EstadoPartido.abierto, 'El partido no está abierto'
        )
        postulacion.rechazar(ahora)
        self.avisar(TipoEvento.postulacion_rechazada, postulacion)

    def revocar(self, postulacion: 'Postulacion', ahora: datetime) -> None:
        """Revoca a un aceptado: libera su cupo (RQ7)."""
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        postulacion.revocar(ahora)
        self.liberar_cupo()
        self.avisar(TipoEvento.revocacion, postulacion)

    def retirar(self, postulacion: 'Postulacion') -> None:
        """El jugador retira su postulación o, si estaba aceptado, se baja.

        Si estaba aceptado, libera su cupo (RQ7). Las dos cosas son el mismo
        evento, `postulacion_retirada` (`requerimientos.md`).
        """
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        estaba_aceptada = postulacion.estado == EstadoPostulacion.aceptada
        postulacion.retirar()
        if estaba_aceptada:
            self.liberar_cupo()
        self.avisar(TipoEvento.postulacion_retirada, postulacion)

    def liberar_cupo(self) -> None:
        """Suma un cupo y, si el partido estaba completo, lo reabre."""
        self.cupos_faltantes += 1
        if self.estado == EstadoPartido.completo:
            self.estado = EstadoPartido.abierto

    def cancelar(self) -> None:
        """Cancela el partido (RQ7).

        Las postulaciones no cambian de estado, pero el WhatsApp deja de
        verse (`Postulacion.whatsapp_visible`).
        """
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        self.estado = EstadoPartido.cancelado
        self.avisar(TipoEvento.partido_cancelado)

    def marcar_no_show(self, postulacion: 'Postulacion') -> None:
        """Marca que un jugador aceptado no vino al partido (RQ8).

        Solo con el partido ya jugado: antes no hay votaciones ni partido
        jugado que deshacer (decisión del equipo del 2026-11-11). Que lo
        haga solo el organizador lo controla la ruta, como al aceptar. Las
        consecuencias (restarle el partido jugado, el voto de 0 y borrar
        votaciones pendientes) las aplica `ProcesadorPostPartido` al recibir
        `no_show_marcado`: el partido solo avisa.
        """
        exigir(
            self.estado == EstadoPartido.jugado,
            'Solo se puede marcar un no-show en un partido jugado',
        )
        postulacion.marcar_no_show()
        self.avisar(TipoEvento.no_show_marcado, postulacion)


class EstadoPostulacion(str, Enum):
    """Estados de una postulación (`docs/requerimientos.md`, sección 4)."""

    en_espera = 'en_espera'
    aceptada = 'aceptada'
    rechazada = 'rechazada'
    retirada = 'retirada'
    revocada = 'revocada'


@mapped_as_dataclass(table_registry)
class Postulacion:
    """Pedido de un jugador para sumarse a un partido (RQ5 a RQ7).

    Es dueña de sus transiciones de estado: cada método revisa desde qué
    estado se puede pasar y, si no se puede, levanta `ReglaDeNegocioError`.
    No emite eventos: los emite `Partido`, que es quien llama a estos
    métodos (`clases.md`).
    """

    __tablename__ = 'postulaciones'
    # Un jugador se postula una sola vez a cada partido, aunque se retire o
    # lo rechacen (decisión del equipo del 2026-11-11). `Partido.postular`
    # lo controla, y la base lo garantiza aunque lleguen dos pedidos juntos.
    __table_args__ = (UniqueConstraint('partido_id', 'jugador_id'),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey('partidos.id'))
    jugador_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    created_at: Mapped[datetime]
    estado: Mapped[EstadoPostulacion] = mapped_column(
        EnumSQL(EstadoPostulacion, native_enum=False),
        default=EstadoPostulacion.en_espera,
    )
    # Cuándo respondió el organizador: al aceptar, rechazar o revocar.
    respondida_at: Mapped[datetime | None] = mapped_column(default=None)
    # El organizador marcó que el jugador aceptado no vino (RQ8).
    no_show: Mapped[bool] = mapped_column(default=False)

    partido: Mapped[Partido] = relationship(
        init=False, back_populates='postulaciones'
    )
    jugador: Mapped[Usuario] = relationship(init=False)

    def pasar(
        self,
        desde: set[EstadoPostulacion],
        hacia: EstadoPostulacion,
        mensaje: str,
    ) -> None:
        """Cambia al estado `hacia` si el actual está en `desde`; si no, 409.

        Es la única regla de estados de la postulación: los métodos de
        abajo solo dicen desde dónde y hacia dónde se puede pasar.
        """
        exigir(self.estado in desde, mensaje)
        self.estado = hacia

    def aceptar(self, ahora: datetime) -> None:
        """De en espera a aceptada; guarda cuándo respondió el organizador."""
        self.pasar(
            {EstadoPostulacion.en_espera},
            EstadoPostulacion.aceptada,
            'Solo se puede aceptar una postulación en espera',
        )
        self.respondida_at = ahora

    def rechazar(self, ahora: datetime) -> None:
        """De en espera a rechazada; guarda cuándo respondió el organizador."""
        self.pasar(
            {EstadoPostulacion.en_espera},
            EstadoPostulacion.rechazada,
            'Solo se puede rechazar una postulación en espera',
        )
        self.respondida_at = ahora

    def revocar(self, ahora: datetime) -> None:
        """De aceptada a revocada; guarda cuándo respondió el organizador."""
        self.pasar(
            {EstadoPostulacion.aceptada},
            EstadoPostulacion.revocada,
            'Solo se puede revocar una postulación aceptada',
        )
        self.respondida_at = ahora

    def retirar(self) -> None:
        """De en espera o aceptada a retirada: la decisión es del jugador."""
        self.pasar(
            {EstadoPostulacion.en_espera, EstadoPostulacion.aceptada},
            EstadoPostulacion.retirada,
            'Solo se puede retirar una postulación en espera o aceptada',
        )

    def marcar_no_show(self) -> None:
        """Marca que el jugador no vino: solo si estaba aceptado, una vez."""
        exigir(
            self.estado == EstadoPostulacion.aceptada,
            'Solo se puede marcar el no-show de un jugador aceptado',
        )
        exigir(not self.no_show, 'El no-show ya estaba marcado')
        self.no_show = True

    def whatsapp_visible(self) -> bool:
        """Dice si el organizador y el jugador se ven el WhatsApp.

        Solo mientras la postulación está aceptada y el partido no se
        canceló (decisión del equipo del 2026-11-11). Es la única regla de
        exposición del WhatsApp: las rutas la consultan y no la repiten.
        """
        return (
            self.estado == EstadoPostulacion.aceptada
            and self.partido.estado != EstadoPartido.cancelado
        )


class TipoNotificacion(str, Enum):
    """Tipos de notificación (`docs/requerimientos.md`, sección 4).

    Están los que generan las postulaciones y los partidos, y el aviso de
    votaciones pendientes (RQ8). "Reclamo resuelto" se suma con los reclamos
    (RQ11).
    """

    postulacion_recibida = 'postulacion_recibida'
    postulacion_aceptada = 'postulacion_aceptada'
    postulacion_rechazada = 'postulacion_rechazada'
    partido_completo = 'partido_completo'
    postulacion_retirada = 'postulacion_retirada'
    revocacion = 'revocacion'
    partido_cancelado = 'partido_cancelado'
    votaciones_pendientes = 'votaciones_pendientes'


@mapped_as_dataclass(table_registry)
class Notificacion:
    """Aviso dentro de la app para un usuario (RQ9).

    No se arma a mano: la crea `FabricaNotificaciones`
    (`fulvo/observadores.py`), que es la única que conoce los textos. La
    referencia (tipo e id) dice qué originó el aviso. No es una clave
    foránea, porque puede apuntar a una postulación o a un partido
    (`clases.md`).
    """

    __tablename__ = 'notificaciones'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    # El destinatario.
    usuario_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    # Largo fijo de 30: así se pueden sumar los tipos de RQ8 y RQ11 sin
    # migrar la columna (como texto, el largo sale del valor más largo).
    tipo: Mapped[TipoNotificacion] = mapped_column(
        EnumSQL(TipoNotificacion, native_enum=False, length=30)
    )
    mensaje: Mapped[str]
    # "postulacion" o "partido".
    referencia_tipo: Mapped[str]
    referencia_id: Mapped[int]
    created_at: Mapped[datetime]
    leida: Mapped[bool] = mapped_column(default=False)

    def marcar_leida(self) -> None:
        """Marca la notificación como leída. Repetirlo no cambia nada."""
        self.leida = True


# Un voto va de 0 a 5 estrellas (RQ8).
ESTRELLAS_MAXIMAS = 5


class EstadoVotacion(str, Enum):
    """Estados de una votación: la crea el sistema y la completa el emisor."""

    pendiente = 'pendiente'
    emitida = 'emitida'


@mapped_as_dataclass(table_registry)
class Votacion:
    """Voto de un participante a otro o al complejo de un partido (RQ8).

    Las crea pendientes `ProcesadorPostPartido` cuando el partido pasa a
    jugado: cada participante vota a los demás y al complejo. El emisor la
    completa con `emitir`. El receptor se guarda con dos referencias
    opcionales, a un usuario o a un complejo, y exactamente una tiene valor:
    no hay subclases por tipo de receptor (`clases.md`).
    """

    __tablename__ = 'votaciones'
    __table_args__ = (
        # Exactamente un receptor: "es nulo" tiene que dar distinto en las
        # dos columnas. Si las dos fueran nulas, o las dos tuvieran valor,
        # darían lo mismo y la base rechazaría la fila.
        CheckConstraint(
            '(receptor_usuario_id IS NULL) <> (receptor_complejo_id IS NULL)',
            name='un_solo_receptor',
        ),
        # Un voto por emisor y receptor en cada partido. En SQL dos nulos no
        # son iguales, así que los votos al complejo (sin usuario) no chocan
        # entre sí en la primera restricción, ni los votos a usuarios en la
        # segunda.
        UniqueConstraint('partido_id', 'emisor_id', 'receptor_usuario_id'),
        UniqueConstraint('partido_id', 'emisor_id', 'receptor_complejo_id'),
        # Las votaciones pendientes se borran (no-show), y SQLite reutiliza
        # el id de la última fila borrada; con esto no, igual que PostgreSQL
        # (mismo criterio que `Complejo`). Un reclamo (RQ11) va a apuntar a
        # una votación por su id.
        {'sqlite_autoincrement': True},
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey('partidos.id'))
    emisor_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    created_at: Mapped[datetime]
    receptor_usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey('usuarios.id'), default=None
    )
    receptor_complejo_id: Mapped[int | None] = mapped_column(
        ForeignKey('complejos.id'), default=None
    )
    estado: Mapped[EstadoVotacion] = mapped_column(
        EnumSQL(EstadoVotacion, native_enum=False),
        default=EstadoVotacion.pendiente,
    )
    # Vacías mientras la votación está pendiente.
    estrellas: Mapped[int | None] = mapped_column(default=None)
    emitida_at: Mapped[datetime | None] = mapped_column(default=None)

    partido: Mapped[Partido] = relationship(init=False)
    # Dos columnas apuntan a usuarios: `foreign_keys` dice cuál usa cada
    # relación.
    emisor: Mapped[Usuario] = relationship(
        init=False, back_populates='votaciones', foreign_keys=[emisor_id]
    )
    receptor_usuario: Mapped[Usuario | None] = relationship(
        init=False, foreign_keys=[receptor_usuario_id]
    )
    receptor_complejo: Mapped[Complejo | None] = relationship(init=False)

    def receptor(self) -> Usuario | Complejo:
        """Devuelve a quién va el voto: el usuario o el complejo.

        Los dos tienen `registrar_puntuacion`, así que quien lo usa no
        necesita saber cuál de los dos es.
        """
        if self.receptor_usuario_id is not None:
            return self.receptor_usuario
        return self.receptor_complejo

    def emitir(self, estrellas: int, ahora: datetime) -> None:
        """Completa la votación y le suma el voto al receptor (RQ8).

        Solo una vez: un voto emitido no se cambia. Recibe `ahora` para
        poder probarla con fechas fijas, como `Partido.aceptar`.
        """
        exigir(
            0 <= estrellas <= ESTRELLAS_MAXIMAS,
            f'Las estrellas van de 0 a {ESTRELLAS_MAXIMAS}',
        )
        exigir(
            self.estado == EstadoVotacion.pendiente,
            'La votación ya fue emitida',
        )
        self.estado = EstadoVotacion.emitida
        self.estrellas = estrellas
        self.emitida_at = ahora
        self.receptor().registrar_puntuacion(estrellas)
