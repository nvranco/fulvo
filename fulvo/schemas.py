from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Rangos válidos de coordenadas: evitan guardar ubicaciones imposibles.
Latitud = Annotated[float, Field(ge=-90, le=90)]
Longitud = Annotated[float, Field(ge=-180, le=180)]

# Texto obligatorio: se recortan los espacios de los bordes y no puede quedar
# vacío. Así "Belgrano " no se vuelve una zona distinta de "Belgrano" y no se
# cargan nombres o direcciones en blanco.
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Mensaje(BaseModel):
    """Respuesta de texto simple, como `Message` en la cátedra."""

    mensaje: str


class ComplejoEntrada(BaseModel):
    """Datos que envía el cliente para cargar un complejo (sin id).

    No incluye la provincia: la tiene la zona, y el servidor se la copia al
    complejo. Así no pueden contradecirse.
    """

    zona: Texto
    localidad: Texto
    nombre: Texto
    direccion: Texto
    telefono_contacto: str | None = None
    tipo: Texto
    reserva_online: bool = False
    sitio_web: str | None = None
    calificacion_maps: float | None = None
    latitud: Latitud
    longitud: Longitud
    link_maps: str | None = None


class ComplejoPublico(ComplejoEntrada):
    """Complejo como lo devuelve la API: datos, id y provincia."""

    id: int
    provincia: str


class ComplejoCercano(ComplejoPublico):
    """Complejo hallado en una búsqueda por radio, con su distancia."""

    distancia_km: float


class ListaComplejos(BaseModel):
    """Respuesta de los listados, envuelta como en la lección de la cátedra."""

    complejos: list[ComplejoPublico]


class ZonaEntrada(BaseModel):
    """Datos que envía el cliente para crear una zona (sin id)."""

    nombre: Texto
    provincia: Texto


class ZonaPublica(ZonaEntrada):
    """Zona del dominio: un partido o un barrio, con su provincia."""

    id: int


class ListaZonas(BaseModel):
    """Zonas que tienen al menos un complejo, envueltas como en la cátedra."""

    zonas: list[ZonaPublica]
