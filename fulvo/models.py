from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import Enum as EnumSQL
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
    registry,
    relationship,
)

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

    # Se carga sola a partir de zona_id: al crear un Complejo se pasa
    # `zona_id`, no `zona`. Solo en este sentido (muchos a uno).
    zona: Mapped[Zona] = relationship(init=False)


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


@mapped_as_dataclass(table_registry)
class Partido:
    """Partido publicado por un organizador al que le faltan jugadores (RQ4).

    En el diseño es el sujeto del patrón Observer (`docs/clases.md`). Por
    ahora solo maneja su estado; los avisos a los observadores llegan con
    las postulaciones (RQ5 a RQ7).
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

    def fin(self) -> datetime:
        """Devuelve cuándo termina el partido: el inicio más la duración."""
        return self.inicio + timedelta(minutes=self.duracion_minutos)

    def actualizar_estado(self, ahora: datetime) -> bool:
        """Pasa el partido a jugado si ya terminó, y dice si cambió.

        No hay una tarea periódica: se llama cada vez que se consulta el
        partido (`docs/requerimientos.md`). Solo cambian los abiertos y los
        completos: uno cancelado sigue cancelado aunque ya haya pasado su
        fecha. Recibe `ahora` en vez de leer el reloj para poder probarlo
        con fechas fijas, como `Usuario.edad`.
        """
        en_juego = self.estado in {
            EstadoPartido.abierto,
            EstadoPartido.completo,
        }
        if en_juego and ahora >= self.fin():
            self.estado = EstadoPartido.jugado
            return True
        return False
