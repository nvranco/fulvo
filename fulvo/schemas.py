from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PastDate,
    StringConstraints,
)

from fulvo.models import (
    HORA_ARGENTINA,
    EstadoPartido,
    EstadoPostulacion,
    TipoNotificacion,
    TipoPartido,
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


class UsuarioRegistrado(BaseModel):
    """Usuario como lo devuelve el registro (RQ1).

    Sin contraseña ni hash, y sin WhatsApp: ese dato solo se muestra entre
    organizador y aceptado (CLAUDE.md, sección 3).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nombre: str
    apellido: str
    posicion: str


class UsuarioPublico(BaseModel):
    """Perfil público (RQ2): lo que un usuario ve de otro.

    El apellido y el WhatsApp no van, y por eso los campos se listan a mano.
    La puntuación queda vacía hasta el primer voto.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    posicion: str
    puntuacion_promedio: float | None
    partidos_jugados: int


class UsuarioPerfil(UsuarioPublico):
    """Perfil propio (RQ2): el público más los datos privados del usuario.

    Solo lo devuelve `/usuarios/yo`, que no recibe un id: cada uno puede ver
    únicamente sus propios datos privados.
    """

    email: EmailStr
    apellido: str
    whatsapp: str
    fecha_nacimiento: date


class UsuarioEdicion(BaseModel):
    """Datos del perfil que se pueden cambiar con PATCH (RQ2).

    Son opcionales: se cambia solo lo que se manda. El `None` por defecto
    significa "no vino" y Pydantic no lo valida. Mandar `null` a propósito
    da 422, porque el tipo no lo admite: estos datos son obligatorios en la
    base y no se pueden vaciar.

    No están el email ni la contraseña: RQ2 no los incluye, y el email
    identifica al usuario dentro del token.
    """

    nombre: Texto = None
    apellido: Texto = None
    whatsapp: Texto = None
    fecha_nacimiento: PastDate = None
    posicion: Texto = None


class Token(BaseModel):
    """Respuesta del login: el JWT y su tipo, como pide OAuth2."""

    access_token: str
    token_type: str


def a_hora_argentina(momento: datetime) -> datetime:
    """Pasa una fecha y hora a la de Argentina, sin zona horaria.

    Si el cliente la manda con zona (por ejemplo en UTC, con `Z` al final),
    se convierte. Si viene sin zona, se toma como hora de Argentina. Así
    queda igual que `ahora_argentina()` y se pueden comparar.
    """
    if momento.tzinfo is not None:
        momento = momento.astimezone(HORA_ARGENTINA).replace(tzinfo=None)
    return momento


HoraArgentina = Annotated[datetime, AfterValidator(a_hora_argentina)]


class PartidoEntrada(BaseModel):
    """Datos que envía el organizador para publicar un partido (RQ4).

    No incluye organizador, estado ni duración: el organizador sale del
    token, todo partido nace abierto y la duración es siempre de 60
    minutos. El máximo de cupos depende del tipo y lo controla la ruta.
    """

    complejo_id: int
    inicio: HoraArgentina
    tipo: TipoPartido
    cupos_faltantes: Annotated[int, Field(ge=1)]


class PartidoPublico(BaseModel):
    """Partido como lo devuelve la API (RQ4 y RQ5).

    El organizador va con su perfil público, sin apellido ni WhatsApp. Las
    fechas y horas están en hora de Argentina, sin zona horaria.
    """

    id: int
    inicio: datetime
    fin: datetime
    duracion_minutos: int
    tipo: TipoPartido
    cupos_faltantes: int
    estado: EstadoPartido
    organizador: UsuarioPublico
    complejo: ComplejoPublico


class ListaPartidos(BaseModel):
    """Respuesta del listado de partidos, envuelta como en la cátedra."""

    partidos: list[PartidoPublico]


class Paginacion(BaseModel):
    """`offset` y `limit` de un listado, como `FilterPage` del aula 10."""

    offset: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class FiltroPartidos(Paginacion):
    """Filtros opcionales del listado de partidos abiertos (RQ5).

    Hereda la paginación, como `FilterTodo` del aula 10. La ruta lo recibe
    entero desde la query string con `Annotated[FiltroPartidos, Query()]`.
    """

    zona: str | None = None
    complejo_id: int | None = None
    tipo: TipoPartido | None = None


class PartidoEdicion(BaseModel):
    """Cambio de un partido publicado: solo se puede cancelar (RQ7).

    Un partido publicado no se edita: se cancela y se publica otro
    (`requerimientos.md`). Por eso el único valor válido es "cancelado".
    """

    estado: Literal['cancelado']


class PostulacionRespuesta(BaseModel):
    """Respuesta del organizador a una postulación (RQ6 y RQ7)."""

    estado: Literal['aceptada', 'rechazada', 'revocada']


class PostulacionRetiro(BaseModel):
    """Lo único que el jugador puede hacer con su postulación: retirarla."""

    estado: Literal['retirada']


class PostulacionDelPartido(BaseModel):
    """Postulación como la ve el organizador del partido (RQ6).

    El jugador va con su perfil público. Su WhatsApp va aparte, y solo
    mientras la postulación está aceptada y el partido no se canceló.
    """

    id: int
    estado: EstadoPostulacion
    created_at: datetime
    respondida_at: datetime | None
    jugador: UsuarioPublico
    whatsapp_jugador: str | None


class ListaPostulaciones(BaseModel):
    """Postulaciones de un partido, envueltas como en la cátedra."""

    postulaciones: list[PostulacionDelPartido]


class MiPostulacion(BaseModel):
    """Postulación como la ve el jugador que se postuló (RQ5 y RQ6).

    Trae el partido completo y el WhatsApp del organizador, que también va
    solo mientras la postulación está aceptada y el partido no se canceló.
    """

    id: int
    estado: EstadoPostulacion
    created_at: datetime
    respondida_at: datetime | None
    partido: PartidoPublico
    whatsapp_organizador: str | None


class ListaMisPostulaciones(BaseModel):
    """Postulaciones del usuario, envueltas como en la cátedra."""

    postulaciones: list[MiPostulacion]


class NotificacionPublica(BaseModel):
    """Notificación como la ve su destinatario (RQ9).

    `referencia_tipo` ("postulacion" o "partido") y `referencia_id` dicen
    qué originó el aviso, para que la app pueda llevar a esa pantalla.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoNotificacion
    mensaje: str
    referencia_tipo: str
    referencia_id: int
    leida: bool
    created_at: datetime


class ListaNotificaciones(BaseModel):
    """Notificaciones del usuario, envueltas como en la cátedra."""

    notificaciones: list[NotificacionPublica]


class FiltroNotificaciones(Paginacion):
    """Filtro opcional por leídas o no leídas, más la paginación."""

    leida: bool | None = None


class NotificacionLectura(BaseModel):
    """Lo único que se puede cambiar de una notificación: marcarla leída."""

    leida: Literal[True]
