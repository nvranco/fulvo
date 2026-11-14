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

    def quitar_puntuacion(self, estrellas: int) -> None:
        """Deshace un voto y recalcula el promedio (RQ11).

        Es la cuenta inversa de `registrar_puntuacion`, repetida a propósito
        como esa. Si era el único voto, el promedio vuelve a quedar vacío.
        """
        cantidad = self.cantidad_puntuaciones - 1
        if cantidad == 0:
            self.puntuacion_promedio = None
        else:
            suma = self.puntuacion_promedio * self.cantidad_puntuaciones
            self.puntuacion_promedio = (suma - estrellas) / cantidad
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
    # El historial de bloqueos del usuario (RQ10). Como en `votaciones`, dos
    # columnas de `sanciones` apuntan a usuarios: esta lista es la del
    # sancionado (la otra es el admin que la aplicó). Las sanciones nunca se
    # borran: se cierran al desbloquear y quedan como historial.
    sanciones: Mapped[list['Sancion']] = relationship(
        init=False,
        back_populates='usuario',
        foreign_keys='Sancion.usuario_id',
        order_by='Sancion.id',
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

    def quitar_puntuacion(self, estrellas: int) -> None:
        """Deshace un voto y recalcula el promedio (RQ11).

        Lo usan los reclamos: al anular una votación, o un no-show, que
        contaba como un voto de 0 (`clases.md`). Si era el único voto, el
        promedio vuelve a quedar vacío, como antes del primero.
        """
        cantidad = self.cantidad_puntuaciones - 1
        if cantidad == 0:
            self.puntuacion_promedio = None
        else:
            suma = self.puntuacion_promedio * self.cantidad_puntuaciones
            self.puntuacion_promedio = (suma - estrellas) / cantidad
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

    def bloquear(
        self,
        admin: 'Usuario',
        motivo: str,
        ahora: datetime,
        reclamo: 'Reclamo | None' = None,
    ) -> 'Sancion':
        """Bloquea al usuario y registra la sanción, y la devuelve (RQ10).

        Solo se bloquea a usuarios comunes: si un admin pudiera bloquear a
        otro, o a sí mismo, la app podría quedarse sin nadie que desbloquee,
        porque un bloqueado no inicia sesión (decisión del equipo del
        2026-11-12). Tampoco se bloquea dos veces: hay una sola sanción
        activa por usuario. `reclamo` es la denuncia que originó el bloqueo,
        si la hay (RQ11). Recibe `ahora` para poder probarlo con fechas
        fijas, como `Votacion.emitir`.
        """
        exigir(
            not self.tiene_rol(ROL_ADMIN),
            'No se puede bloquear a un administrador',
        )
        exigir(not self.bloqueado, 'El usuario ya está bloqueado')
        sancion = Sancion(
            usuario_id=self.id,
            aplicada_por_id=admin.id,
            motivo=motivo,
            desde=ahora,
            reclamo_id=None if reclamo is None else reclamo.id,
        )
        self.sanciones.append(sancion)
        self.bloqueado = True
        return sancion

    def desbloquear(self, sancion: 'Sancion', ahora: datetime) -> None:
        """Cierra la sanción que lo tiene bloqueado y le quita el bloqueo.

        Recibe la sanción porque la API la nombra por su id
        (`PATCH /usuarios/{id}/sanciones/{id}`). Si ya estaba cerrada,
        `Sancion.cerrar` levanta el error: no hay nada que desbloquear.
        """
        sancion.cerrar(ahora)
        self.bloqueado = False


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

    Desde el inicio el partido no cambia: nadie se postula, el organizador
    no acepta, rechaza ni revoca, nadie se retira ni se baja y el partido no
    se cancela. Cada uno de esos métodos recibe `ahora` y levanta "El
    partido ya empezó" (decisión del equipo del 2026-11-14). Lo que pase en
    la cancha se corrige cuando termina, con el no-show y los reclamos. Sin
    esta regla, un aceptado que no fue se bajaba con el partido empezado y
    así esquivaba el no-show.
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

    def presentes(self) -> list[Usuario]:
        """Los participantes que vinieron: todos menos los no-show (RQ11).

        Son los que se votan entre sí. Lo usa la reposición de votaciones
        cuando un reclamo anula un no-show: con alguien que sigue marcado
        como ausente no se vota.
        """
        ausentes = {
            postulacion.jugador_id
            for postulacion in self.postulaciones
            if postulacion.estado == EstadoPostulacion.aceptada
            and postulacion.no_show
        }
        return [u for u in self.participantes() if u.id not in ausentes]

    def actualizar_estado(self, ahora: datetime) -> bool:
        """Pasa el partido a jugado si ya terminó, y dice si cambió.

        No hay una tarea periódica: se llama cada vez que se consulta el
        partido (`docs/requerimientos.md`). Solo cambian los abiertos y los
        completos: uno cancelado sigue cancelado aunque ya haya pasado su
        fecha. Recibe `ahora` en vez de leer el reloj para poder probarlo
        con fechas fijas, como `Usuario.edad`.

        Si tuvo aceptados, emite `partido_jugado`: los observadores suman
        los partidos jugados, crean las votaciones y avisan. Si nadie se
        sumó, no emite nada: el organizador no jugó con nadie de la app, así
        que no hay a quién votar ni partido jugado que contar (decisión del
        equipo del 2026-11-14). Si no, cada partido sin nadie le dejaba un
        voto pendiente al complejo, y con cuatro quedaba bloqueado por
        deuda.
        """
        if self.en_juego() and ahora >= self.fin():
            self.estado = EstadoPartido.jugado
            hubo_aceptados = any(
                postulacion.estado == EstadoPostulacion.aceptada
                for postulacion in self.postulaciones
            )
            if hubo_aceptados:
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
        que quedó afuera (`clases.md`). Solo antes del inicio.
        """
        exigir(
            self.estado == EstadoPartido.abierto, 'El partido no está abierto'
        )
        exigir(ahora < self.inicio, 'El partido ya empezó')
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
        """Rechaza una postulación en espera (RQ6). Solo antes del inicio."""
        exigir(
            self.estado == EstadoPartido.abierto, 'El partido no está abierto'
        )
        exigir(ahora < self.inicio, 'El partido ya empezó')
        postulacion.rechazar(ahora)
        self.avisar(TipoEvento.postulacion_rechazada, postulacion)

    def revocar(self, postulacion: 'Postulacion', ahora: datetime) -> None:
        """Revoca a un aceptado y libera su cupo, antes del inicio (RQ7)."""
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        exigir(ahora < self.inicio, 'El partido ya empezó')
        postulacion.revocar(ahora)
        self.liberar_cupo()
        self.avisar(TipoEvento.revocacion, postulacion)

    def retirar(self, postulacion: 'Postulacion', ahora: datetime) -> None:
        """El jugador retira su postulación o, si estaba aceptado, se baja.

        Si estaba aceptado, libera su cupo (RQ7). Las dos cosas son el mismo
        evento, `postulacion_retirada` (`requerimientos.md`). Solo antes del
        inicio: con el partido empezado, un aceptado que no fue ya no se
        baja, y el organizador le puede marcar el no-show cuando termina.
        """
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        exigir(ahora < self.inicio, 'El partido ya empezó')
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

    def cancelar(self, ahora: datetime) -> None:
        """Cancela el partido (RQ7). Solo antes del inicio.

        Las postulaciones no cambian de estado, pero el WhatsApp deja de
        verse (`Postulacion.whatsapp_visible`).
        """
        exigir(self.en_juego(), 'El partido ya se jugó o fue cancelado')
        exigir(ahora < self.inicio, 'El partido ya empezó')
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

    def quitar_no_show(self, postulacion: 'Postulacion') -> None:
        """Anula un no-show, cuando el admin le da la razón al jugador (RQ11).

        Como al marcarlo, el partido solo avisa: devolverle el partido
        jugado, quitarle el voto de 0 y reponer las votaciones lo hace
        `ProcesadorPostPartido` al recibir `no_show_anulado`. No hace falta
        revisar el estado del partido: un no-show solo existe en un partido
        jugado, y un partido jugado ya no cambia.
        """
        postulacion.quitar_no_show()
        self.avisar(TipoEvento.no_show_anulado, postulacion)


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

    def quitar_no_show(self) -> None:
        """Quita la marca de no-show: solo si estaba marcada (RQ11)."""
        exigir(self.no_show, 'La postulación no tiene un no-show marcado')
        self.no_show = False

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

    Están los que generan las postulaciones y los partidos, el aviso de
    votaciones pendientes (RQ8) y los de los reclamos (RQ11): la respuesta
    al autor y el aviso a los que vuelven a deber votos cuando se anula un
    no-show (decisión del equipo del 2026-11-12).
    """

    postulacion_recibida = 'postulacion_recibida'
    postulacion_aceptada = 'postulacion_aceptada'
    postulacion_rechazada = 'postulacion_rechazada'
    partido_completo = 'partido_completo'
    postulacion_retirada = 'postulacion_retirada'
    revocacion = 'revocacion'
    partido_cancelado = 'partido_cancelado'
    votaciones_pendientes = 'votaciones_pendientes'
    votaciones_repuestas = 'votaciones_repuestas'
    reclamo_resuelto = 'reclamo_resuelto'


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
    # "postulacion", "partido" o "reclamo".
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
    """Estados de una votación: la crea el sistema y la completa el emisor.

    Una emitida pasa a anulada si el admin le da la razón a un reclamo del
    receptor (RQ11). Como texto entra en la misma columna: el largo lo da
    "pendiente", que sigue siendo el valor más largo.
    """

    pendiente = 'pendiente'
    emitida = 'emitida'
    anulada = 'anulada'


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

    def anular(self) -> None:
        """Deja sin efecto un voto emitido: sale del promedio (RQ11).

        La usa el reclamo resuelto. La votación no se borra: queda anulada,
        con sus estrellas, y el reclamo sigue apuntando a ella (decisión del
        equipo del 2026-11-12).
        """
        exigir(
            self.estado == EstadoVotacion.emitida,
            'Solo se puede anular una votación emitida',
        )
        self.estado = EstadoVotacion.anulada
        self.receptor().quitar_puntuacion(self.estrellas)


@mapped_as_dataclass(table_registry)
class Sancion:
    """Registro de un bloqueo de usuario (RQ10).

    Bloquear crea una sanción activa y desbloquear la cierra con su fecha de
    fin. Nunca se borra: así queda el historial de quién bloqueó a quién,
    cuándo y por qué (`requerimientos.md`). No se crea a mano: la crea
    `Usuario.bloquear` y la cierra `Usuario.desbloquear`, que además
    mantienen al día `Usuario.bloqueado`, que es lo que mira el login. Si el
    bloqueo salió de una denuncia, `reclamo_id` la guarda (RQ11).
    """

    __tablename__ = 'sanciones'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    # El usuario bloqueado.
    usuario_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    # El admin que lo bloqueó.
    aplicada_por_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    motivo: Mapped[str]
    desde: Mapped[datetime]
    # Vacía mientras la sanción está activa: se completa al desbloquear.
    hasta: Mapped[datetime | None] = mapped_column(default=None)
    # La denuncia que originó el bloqueo, si la hay (RQ11). Vacía cuando el
    # admin bloquea directo, con `POST /usuarios/{id}/sanciones`.
    reclamo_id: Mapped[int | None] = mapped_column(
        ForeignKey('reclamos.id'), default=None
    )

    # Dos columnas apuntan a usuarios: `foreign_keys` dice cuál usa cada
    # relación, como en `Votacion`.
    usuario: Mapped[Usuario] = relationship(
        init=False, back_populates='sanciones', foreign_keys=[usuario_id]
    )
    aplicada_por: Mapped[Usuario] = relationship(
        init=False, foreign_keys=[aplicada_por_id]
    )

    def activa(self) -> bool:
        """Dice si la sanción sigue vigente: lo está hasta que se cierra."""
        return self.hasta is None

    def cerrar(self, ahora: datetime) -> None:
        """Le pone la fecha de fin. Lo usa `Usuario.desbloquear`."""
        exigir(self.activa(), 'La sanción ya estaba cerrada')
        self.hasta = ahora


class TipoObjetivo(str, Enum):
    """Sobre qué es un reclamo (RQ11): un no-show o una votación que recibió
    el autor, o una denuncia a otro usuario o a un complejo."""

    no_show = 'no_show'
    votacion = 'votacion'
    usuario = 'usuario'
    complejo = 'complejo'


class EstadoReclamo(str, Enum):
    """Estados de un reclamo: lo abre un usuario y lo cierra el admin."""

    abierto = 'abierto'
    resuelto = 'resuelto'
    rechazado = 'rechazado'


@mapped_as_dataclass(table_registry)
class Reclamo:
    """Reclamo de un usuario, que el admin resuelve o rechaza (RQ11).

    El objetivo se guarda como tipo e id, sin clave foránea, igual que la
    referencia de `Notificacion`: puede ser una postulación (la del
    no-show), una votación, un usuario o un complejo (`clases.md`). La ruta
    busca el objeto según el tipo y se lo pasa a `abrir` y a `resolver`:
    las reglas viven acá, pero las consultas a la base no.
    """

    __tablename__ = 'reclamos'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'))
    tipo_objetivo: Mapped[TipoObjetivo] = mapped_column(
        EnumSQL(TipoObjetivo, native_enum=False)
    )
    # El id de la postulación (no-show), la votación, el usuario o el
    # complejo, según `tipo_objetivo`.
    objetivo_id: Mapped[int]
    motivo: Mapped[str]
    created_at: Mapped[datetime]
    estado: Mapped[EstadoReclamo] = mapped_column(
        EnumSQL(EstadoReclamo, native_enum=False),
        default=EstadoReclamo.abierto,
    )
    # Vacíos mientras el reclamo está abierto.
    resolucion: Mapped[str | None] = mapped_column(default=None)
    resuelto_por_id: Mapped[int | None] = mapped_column(
        ForeignKey('usuarios.id'), default=None
    )
    resuelto_at: Mapped[datetime | None] = mapped_column(default=None)

    # Dos columnas apuntan a usuarios: `foreign_keys` dice cuál usa cada
    # relación, como en `Votacion` y `Sancion`.
    autor: Mapped[Usuario] = relationship(init=False, foreign_keys=[autor_id])
    resuelto_por: Mapped[Usuario | None] = relationship(
        init=False, foreign_keys=[resuelto_por_id]
    )

    @classmethod
    def abrir(
        cls,
        autor: Usuario,
        tipo_objetivo: TipoObjetivo,
        objetivo: Postulacion | Votacion | Usuario | Complejo,
        motivo: str,
        ahora: datetime,
    ) -> 'Reclamo':
        """Crea el reclamo abierto, si el objetivo lo permite (RQ11).

        Un no-show tiene que ser del autor y estar marcado. Una votación
        tiene que haberla recibido el autor y estar emitida: una pendiente
        todavía no tiene estrellas. Nadie se denuncia a sí mismo. Que el
        objetivo exista (404) y que el autor no tenga otro reclamo abierto
        sobre el mismo objetivo lo controla la ruta, porque hay que consultar
        la base (`clases.md`).
        """
        if tipo_objetivo == TipoObjetivo.no_show:
            exigir(
                objetivo.jugador_id == autor.id,
                'Solo podés reclamar un no-show tuyo',
            )
            exigir(
                objetivo.no_show,
                'Esa postulación no tiene un no-show marcado',
            )
        elif tipo_objetivo == TipoObjetivo.votacion:
            exigir(
                objetivo.receptor_usuario_id == autor.id,
                'Solo podés reclamar una votación que recibiste',
            )
            exigir(
                objetivo.estado == EstadoVotacion.emitida,
                'Solo se puede reclamar una votación emitida',
            )
        elif tipo_objetivo == TipoObjetivo.usuario:
            exigir(objetivo.id != autor.id, 'No podés denunciarte a vos mismo')
        return cls(
            autor_id=autor.id,
            tipo_objetivo=tipo_objetivo,
            objetivo_id=objetivo.id,
            motivo=motivo,
            created_at=ahora,
        )

    def resolver(
        self,
        admin: Usuario,
        resolucion: str,
        objetivo: Postulacion | Votacion | Usuario | None,
        ahora: datetime,
        bloquear: bool = False,
    ) -> 'Sancion | None':
        """Le da la razón al autor y aplica la medida del objetivo (RQ11).

        - No-show: el partido le quita la marca, y `ProcesadorPostPartido`
          le devuelve el partido jugado, le quita el voto de 0 y repone las
          votaciones (decisión del equipo del 2026-11-12).
        - Votación: queda anulada y sale del promedio del autor.
        - Usuario: si el admin lo pide (`bloquear`), lo bloquea con una
          sanción unida a este reclamo, y la devuelve.
        - Complejo: ninguna medida automática; el admin edita sus datos con
          `PUT /complejos/{id}` (`clases.md`).

        Primero aplica la medida y después cambia el estado: si la medida no
        se puede aplicar (por ejemplo, el usuario ya está bloqueado), el
        reclamo sigue abierto.
        """
        self.exigir_abierto()
        exigir(
            not bloquear or self.tipo_objetivo == TipoObjetivo.usuario,
            'Solo se puede bloquear al resolver una denuncia a un usuario',
        )
        sancion = None
        if self.tipo_objetivo == TipoObjetivo.no_show:
            objetivo.partido.quitar_no_show(objetivo)
        elif self.tipo_objetivo == TipoObjetivo.votacion:
            objetivo.anular()
        elif bloquear:
            sancion = objetivo.bloquear(admin, resolucion, ahora, self)
        self.cerrar(EstadoReclamo.resuelto, admin, resolucion, ahora)
        return sancion

    def rechazar(
        self, admin: Usuario, resolucion: str, ahora: datetime
    ) -> None:
        """No le da la razón al autor: no aplica ninguna medida (RQ11)."""
        self.exigir_abierto()
        self.cerrar(EstadoReclamo.rechazado, admin, resolucion, ahora)

    def exigir_abierto(self) -> None:
        """Levanta `ReglaDeNegocioError` (409) si el reclamo ya se cerró."""
        exigir(
            self.estado == EstadoReclamo.abierto,
            'El reclamo ya fue resuelto o rechazado',
        )

    def cerrar(
        self,
        estado: EstadoReclamo,
        admin: Usuario,
        resolucion: str,
        ahora: datetime,
    ) -> None:
        """Guarda la respuesta del admin: el estado final, quién y cuándo."""
        self.estado = estado
        self.resolucion = resolucion
        self.resuelto_por_id = admin.id
        self.resuelto_at = ahora
