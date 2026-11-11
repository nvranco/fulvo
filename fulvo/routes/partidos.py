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
    Partido,
    TipoPartido,
    ahora_argentina,
)
from fulvo.routes.complejos import buscar_complejo, complejo_publico
from fulvo.routes.zonas import buscar_zona
from fulvo.schemas import (
    FiltroPartidos,
    ListaPartidos,
    PartidoEntrada,
    PartidoPublico,
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


@router.get('/{partido_id}', response_model=PartidoPublico)
def leer_partido(partido_id: int, session: Session):
    """Devuelve un partido por id, o 404 si no existe (RQ4).

    Antes revisa si ya terminó y, si es así, lo guarda como jugado: es el
    pase a jugado "al consultar" que pide `docs/requerimientos.md`.
    """
    partido = session.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Partido no encontrado'
        )
    if partido.actualizar_estado(ahora_argentina()):
        session.commit()
    return partido_publico(partido)
