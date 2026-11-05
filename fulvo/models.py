from datetime import date

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
