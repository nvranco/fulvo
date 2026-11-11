from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import (
    JUGADORES_POR_TIPO,
    Complejo,
    EstadoPartido,
    EstadoPostulacion,
    Partido,
    Postulacion,
    TipoPartido,
    Usuario,
    ahora_argentina,
)
from fulvo.routes.complejos import buscar_complejo, complejo_publico
from fulvo.routes.zonas import buscar_zona
from fulvo.schemas import (
    FiltroPartidos,
    ListaPartidos,
    ListaPostulaciones,
    MiPostulacion,
    PartidoEdicion,
    PartidoEntrada,
    PartidoPublico,
    PostulacionDelPartido,
    PostulacionRespuesta,
    UsuarioPublico,
)
from fulvo.security import UsuarioActual, obtener_usuario_actual

# Todas las rutas de partidos piden token: cada partido muestra el perfil
# público del organizador, que solo ven usuarios con sesión iniciada (RQ2).
router = APIRouter(
    prefix='/partidos',
    tags=['partidos'],
    dependencies=[Depends(obtener_usuario_actual)],
)
Session = Annotated[Session, Depends(get_session)]


def partido_publico(partido: Partido) -> PartidoPublico:
    """Arma la respuesta de la API a partir del modelo.

    No alcanza con `from_attributes`: el complejo se traduce con
    `complejo_publico` (el modelo guarda `zona_id` y la API muestra el
    nombre de la zona) y `fin` se calcula.
    """
    return PartidoPublico(
        id=partido.id,
        inicio=partido.inicio,
        fin=partido.fin(),
        duracion_minutos=partido.duracion_minutos,
        tipo=partido.tipo,
        cupos_faltantes=partido.cupos_faltantes,
        estado=partido.estado,
        organizador=UsuarioPublico.model_validate(partido.organizador),
        complejo=complejo_publico(partido.complejo),
    )


def rechazar_inicio_pasado(inicio: datetime) -> None:
    """Levanta 422 si el partido no empieza en el futuro.

    Se compara con la hora de Argentina, la misma en la que se guarda el
    inicio. Un partido que empieza justo ahora también se rechaza.
    """
    if inicio <= ahora_argentina():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='El partido tiene que empezar en el futuro',
        )


def rechazar_cupos_de_mas(tipo: TipoPartido, cupos: int) -> None:
    """Levanta 422 si los cupos faltantes no entran en el tipo de partido.

    El organizador juega, así que pueden faltar como mucho todos los
    jugadores del tipo menos uno: en un F5, que son 10, hasta 9.
    """
    maximo = JUGADORES_POR_TIPO[tipo] - 1
    if cupos > maximo:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f'Un partido {tipo.value} admite hasta {maximo} cupos '
            'faltantes',
        )


@router.post('', status_code=HTTPStatus.CREATED, response_model=PartidoPublico)
def publicar_partido(
    datos: PartidoEntrada, organizador: UsuarioActual, session: Session
):
    """Publica un partido abierto, con el usuario como organizador (RQ4).

    422 si el inicio ya pasó o los cupos no entran en el tipo, y 404 si el
    complejo no existe. El bloqueo por votaciones pendientes llega con RQ8.
    """
    rechazar_inicio_pasado(datos.inicio)
    rechazar_cupos_de_mas(datos.tipo, datos.cupos_faltantes)
    buscar_complejo(session, datos.complejo_id)
    partido = Partido(organizador_id=organizador.id, **datos.model_dump())
    session.add(partido)
    session.commit()
    session.refresh(partido)
    return partido_publico(partido)


@router.get('', response_model=ListaPartidos)
def listar_partidos_abiertos(
    session: Session, filtro: Annotated[FiltroPartidos, Query()]
):
    """Lista los partidos abiertos que todavía no empezaron (RQ5).

    Van del más próximo al más lejano, con filtros opcionales por zona,
    complejo y tipo. Un partido que ya empezó no se muestra, porque ya no
    sirve para sumarse. Por eso alcanza con mirar el inicio, sin revisar el
    pase a jugado de cada partido.
    """
    consulta = (
        select(Partido)
        .where(
            Partido.estado == EstadoPartido.abierto,
            Partido.inicio > ahora_argentina(),
        )
        .order_by(Partido.inicio, Partido.id)
    )
    if filtro.tipo:
        consulta = consulta.where(Partido.tipo == filtro.tipo)
    if filtro.complejo_id is not None:
        consulta = consulta.where(Partido.complejo_id == filtro.complejo_id)
    if filtro.zona:
        zona = buscar_zona(session, filtro.zona)
        if zona is None:
            return {'partidos': []}
        consulta = consulta.join(Partido.complejo).where(
            Complejo.zona_id == zona.id
        )
    partidos = session.scalars(
        consulta.offset(filtro.offset).limit(filtro.limit)
    )
    return {'partidos': [partido_publico(p) for p in partidos]}


def buscar_partido(session: Session, partido_id: int) -> Partido:
    """Devuelve el partido con ese id, ya al día, o levanta 404.

    "Al día" quiere decir que antes revisa si ya terminó: es el pase a
    jugado al consultar que pide `docs/requerimientos.md`. Lo usan todas
    las rutas que reciben un partido, así ninguna trabaja con un estado
    viejo; el commit de cada ruta guarda el cambio. Cuando lleguen las
    notificaciones (RQ9) y las votaciones (RQ8), acá se le suman al partido
    sus observadores, antes de que pase cualquier cosa.
    """
    partido = session.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Partido no encontrado'
        )
    partido.actualizar_estado(ahora_argentina())
    return partido


def exigir_organizador(partido: Partido, usuario: Usuario) -> None:
    """Levanta 403 si el usuario no es el organizador del partido."""
    if partido.organizador_id != usuario.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Solo el organizador del partido puede hacer esto',
        )


def postulacion_del_partido(postulacion: Postulacion) -> PostulacionDelPartido:
    """Arma la postulación como la ve el organizador.

    El WhatsApp del jugador va solo si `whatsapp_visible()`: la regla vive
    en el modelo y acá solo se consulta.
    """
    jugador = postulacion.jugador
    visible = postulacion.whatsapp_visible()
    return PostulacionDelPartido(
        id=postulacion.id,
        estado=postulacion.estado,
        created_at=postulacion.created_at,
        respondida_at=postulacion.respondida_at,
        jugador=UsuarioPublico.model_validate(jugador),
        whatsapp_jugador=jugador.whatsapp if visible else None,
    )


def mi_postulacion(postulacion: Postulacion) -> MiPostulacion:
    """Arma la postulación como la ve el jugador, con el partido completo.

    El WhatsApp del organizador sigue la misma regla que el del jugador.
    """
    partido = postulacion.partido
    visible = postulacion.whatsapp_visible()
    return MiPostulacion(
        id=postulacion.id,
        estado=postulacion.estado,
        created_at=postulacion.created_at,
        respondida_at=postulacion.respondida_at,
        partido=partido_publico(partido),
        whatsapp_organizador=partido.organizador.whatsapp if visible else None,
    )


def ordenar_por_puntuacion(
    postulaciones: list[Postulacion],
) -> list[Postulacion]:
    """Ordena como pide la lista de espera (`requerimientos.md`).

    Primero la puntuación promedio del jugador, de mayor a menor; los que
    todavía no tienen puntuación van al final y, si empatan, por orden de
    llegada. Se calcula al consultar y no se guarda.
    """

    def clave(postulacion: Postulacion) -> tuple:
        puntuacion = postulacion.jugador.puntuacion_promedio
        return (
            puntuacion is None,
            -(puntuacion or 0),
            postulacion.created_at,
            postulacion.id,
        )

    return sorted(postulaciones, key=clave)


@router.get('/{partido_id}', response_model=PartidoPublico)
def leer_partido(partido_id: int, session: Session):
    """Devuelve un partido por id, o 404 si no existe (RQ4).

    Si el partido ya terminó, `buscar_partido` lo pasa a jugado y el commit
    lo guarda. Si no cambió nada, el commit no hace nada.
    """
    partido = buscar_partido(session, partido_id)
    session.commit()
    return partido_publico(partido)


@router.patch('/{partido_id}', response_model=PartidoPublico)
def cancelar_partido(
    partido_id: int,
    datos: PartidoEdicion,
    organizador: UsuarioActual,
    session: Session,
):
    """El organizador cancela su partido (RQ7).

    Es PATCH sobre el estado porque el partido no se borra: queda
    cancelado. `datos` solo valida que se pida "cancelado". 403 si no es el
    organizador y 409 si el partido ya se jugó o ya estaba cancelado.
    """
    partido = buscar_partido(session, partido_id)
    exigir_organizador(partido, organizador)
    partido.cancelar()
    session.commit()
    return partido_publico(partido)


@router.post(
    '/{partido_id}/postulaciones',
    status_code=HTTPStatus.CREATED,
    response_model=MiPostulacion,
)
def postularse(partido_id: int, jugador: UsuarioActual, session: Session):
    """El usuario se postula al partido y queda en espera (RQ5).

    409 si el partido no está abierto o ya empezó, si es el organizador o
    si ya se había postulado antes.
    """
    partido = buscar_partido(session, partido_id)
    postulacion = partido.postular(jugador, ahora_argentina())
    session.commit()
    return mi_postulacion(postulacion)


@router.get('/{partido_id}/postulaciones', response_model=ListaPostulaciones)
def listar_postulaciones(
    partido_id: int,
    organizador: UsuarioActual,
    session: Session,
    estado: EstadoPostulacion | None = None,
):
    """Postulaciones del partido, para su organizador (RQ6).

    Van en el orden de la lista de espera. Con `estado=en_espera` se ve
    solo la lista de espera. 403 si no es el organizador.
    """
    partido = buscar_partido(session, partido_id)
    exigir_organizador(partido, organizador)
    session.commit()
    elegidas = [
        p
        for p in partido.postulaciones
        if estado is None or p.estado == estado
    ]
    return {
        'postulaciones': [
            postulacion_del_partido(p)
            for p in ordenar_por_puntuacion(elegidas)
        ]
    }


@router.patch(
    '/{partido_id}/postulaciones/{postulacion_id}',
    response_model=PostulacionDelPartido,
)
def responder_postulacion(
    partido_id: int,
    postulacion_id: int,
    datos: PostulacionRespuesta,
    organizador: UsuarioActual,
    session: Session,
):
    """El organizador acepta, rechaza o revoca una postulación (RQ6 y RQ7).

    403 si no es el organizador, 404 si la postulación no es de este
    partido y 409 si el cambio no se puede hacer desde el estado actual.
    Al aceptar, la respuesta ya trae el WhatsApp del jugador.
    """
    partido = buscar_partido(session, partido_id)
    exigir_organizador(partido, organizador)
    postulacion = session.get(Postulacion, postulacion_id)
    if postulacion is None or postulacion.partido_id != partido.id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Postulación no encontrada',
        )
    ahora = ahora_argentina()
    if datos.estado == EstadoPostulacion.aceptada:
        partido.aceptar(postulacion, ahora)
    elif datos.estado == EstadoPostulacion.rechazada:
        partido.rechazar(postulacion, ahora)
    else:
        partido.revocar(postulacion, ahora)
    session.commit()
    return postulacion_del_partido(postulacion)
