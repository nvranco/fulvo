from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Votacion, ahora_argentina
from fulvo.routes.complejos import complejo_publico
from fulvo.routes.partidos import partido_publico, poner_al_dia_partidos_de
from fulvo.schemas import (
    FiltroVotaciones,
    ListaVotaciones,
    UsuarioPublico,
    VotacionEmision,
    VotacionPublica,
)
from fulvo.security import UsuarioActual

# Las votaciones las crea `ProcesadorPostPartido` cuando un partido pasa a
# jugado. Acá cada usuario ve las suyas y las completa (RQ8). El no-show lo
# marca el organizador en `partidos.py`, sobre la postulación.
router = APIRouter(prefix='/votaciones', tags=['votaciones'])
Session = Annotated[Session, Depends(get_session)]


def votacion_publica(votacion: Votacion) -> VotacionPublica:
    """Arma la votación como la ve su emisor.

    El receptor que tiene valor se traduce a su forma pública: el perfil
    público del jugador o el complejo como lo muestra la API. El otro queda
    vacío.
    """
    receptor_usuario = None
    receptor_complejo = None
    if votacion.receptor_usuario_id is not None:
        receptor_usuario = UsuarioPublico.model_validate(
            votacion.receptor_usuario
        )
    else:
        receptor_complejo = complejo_publico(votacion.receptor_complejo)
    return VotacionPublica(
        id=votacion.id,
        estado=votacion.estado,
        estrellas=votacion.estrellas,
        created_at=votacion.created_at,
        emitida_at=votacion.emitida_at,
        partido=partido_publico(votacion.partido),
        receptor_usuario=receptor_usuario,
        receptor_complejo=receptor_complejo,
    )


@router.get('', response_model=ListaVotaciones)
def listar_mis_votaciones(
    usuario: UsuarioActual,
    session: Session,
    filtro: Annotated[FiltroVotaciones, Query()],
):
    """Votaciones que el usuario tiene que emitir o ya emitió (RQ8).

    Van de la más nueva a la más vieja. Con `estado=pendiente` se ve lo que
    debe. Antes se ponen al día sus partidos: si uno terminó y nadie lo
    consultó, recién ahí se crean sus votaciones.
    """
    poner_al_dia_partidos_de(session, usuario)
    session.commit()
    consulta = select(Votacion).where(Votacion.emisor_id == usuario.id)
    if filtro.estado is not None:
        consulta = consulta.where(Votacion.estado == filtro.estado)
    consulta = (
        consulta
        .order_by(Votacion.id.desc())
        .offset(filtro.offset)
        .limit(filtro.limit)
    )
    votaciones = session.scalars(consulta).all()
    return {'votaciones': [votacion_publica(v) for v in votaciones]}


@router.patch('/{votacion_id}', response_model=VotacionPublica)
def emitir_votacion(
    votacion_id: int,
    datos: VotacionEmision,
    usuario: UsuarioActual,
    session: Session,
):
    """Completa una votación pendiente con 0 a 5 estrellas (RQ8).

    Es PATCH porque la votación ya existe (la creó el sistema) y se cambia
    una parte. El promedio del receptor se recalcula en `Votacion.emitir`.
    404 si no existe, 403 si es de otro usuario y 409 si ya se emitió.
    """
    votacion = session.get(Votacion, votacion_id)
    if votacion is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Votación no encontrada',
        )
    if votacion.emisor_id != usuario.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Solo quien emite la votación puede completarla',
        )
    votacion.emitir(datos.estrellas, ahora_argentina())
    session.commit()
    return votacion_publica(votacion)
