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
