from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PastDate,
    StringConstraints,
)

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

    # Permite armarla desde el modelo `Zona` (que no es un dict) leyendo sus
    # atributos: `ZonaPublica.model_validate(zona)`. FastAPI lo aplica solo al
    # devolver un modelo desde una ruta con `response_model=ZonaPublica`.
    model_config = ConfigDict(from_attributes=True)

    id: int


class ListaZonas(BaseModel):
    """Zonas que tienen al menos un complejo, envueltas como en la cátedra."""

    zonas: list[ZonaPublica]


class UsuarioEntrada(BaseModel):
    """Datos que envía el cliente para registrarse (RQ1).

    No incluye rol, bloqueado ni puntuaciones: los fija el servidor, así
    nadie puede registrarse como admin mandando un campo de más.
    """

    # EmailStr valida el formato del email.
    email: EmailStr
    # Largo mínimo para descartar contraseñas triviales; el máximo evita
    # que alguien mande un texto enorme solo para cargar al hasher (argon2
    # es lento a propósito).
    contrasena: Annotated[str, Field(min_length=8, max_length=128)]
    nombre: Texto
    apellido: Texto
    whatsapp: Texto
    fecha_nacimiento: PastDate
    posicion: Texto


class UsuarioPublico(BaseModel):
    """Usuario como lo devuelve el registro.

    Sin contraseña ni hash, y sin WhatsApp: ese dato solo se muestra entre
    organizador y aceptado (CLAUDE.md, sección 3).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nombre: str
    apellido: str
    posicion: str


class Token(BaseModel):
    """Respuesta del login: el JWT y su tipo, como pide OAuth2."""

    access_token: str
    token_type: str
