from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import (
    ROL_ADMIN,
    Complejo,
    EstadoReclamo,
    Postulacion,
    Reclamo,
    TipoNotificacion,
    TipoObjetivo,
    Usuario,
    Votacion,
    ahora_argentina,
)
from fulvo.observadores import FabricaNotificaciones
from fulvo.routes.partidos import preparar_partido, sacar_de_partidos_por_jugar
from fulvo.schemas import (
    FiltroReclamos,
    ListaReclamos,
    ReclamoEntrada,
    ReclamoPublico,
    ReclamoResolucion,
    UsuarioPublico,
)
from fulvo.security import AdminActual, UsuarioActual

# Una sola colección para todos (decisión del equipo del 2026-11-12): cada
# usuario abre reclamos y ve los suyos, y el admin ve los de todos y los
# resuelve. Lo que cambia según el rol es qué se lista y quién responde.
router = APIRouter(prefix='/reclamos', tags=['reclamos'])
Session = Annotated[Session, Depends(get_session)]

# Dónde se busca el objetivo de cada tipo de reclamo, y el 404 si no está.
# No es una clave foránea (`clases.md`): la ruta lo busca según el tipo.
OBJETIVOS = {
    TipoObjetivo.no_show: (Postulacion, 'Postulación no encontrada'),
    TipoObjetivo.votacion: (Votacion, 'Votación no encontrada'),
    TipoObjetivo.usuario: (Usuario, 'Usuario no encontrado'),
    TipoObjetivo.complejo: (Complejo, 'Complejo no encontrado'),
}


def buscar_objetivo(
    session: Session, tipo_objetivo: TipoObjetivo, objetivo_id: int
) -> Postulacion | Votacion | Usuario | Complejo:
    """Devuelve el objetivo del reclamo según su tipo, o levanta 404."""
    modelo, no_encontrado = OBJETIVOS[tipo_objetivo]
    objetivo = session.get(modelo, objetivo_id)
    if objetivo is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=no_encontrado
        )
    return objetivo


def partido_del_reclamo(session: Session, reclamo: Reclamo) -> int | None:
    """El partido del no-show o de la votación; ninguno en las denuncias.

    El reclamo no lo guarda: sale del objetivo (`clases.md`). Las
    postulaciones no se borran nunca, y una votación reclamada está emitida
    o anulada, que tampoco se borran: el objetivo siempre está.
    """
    if reclamo.tipo_objetivo not in {
        TipoObjetivo.no_show,
        TipoObjetivo.votacion,
    }:
        return None
    modelo, _ = OBJETIVOS[reclamo.tipo_objetivo]
    return session.get(modelo, reclamo.objetivo_id).partido_id


def reclamo_publico(session: Session, reclamo: Reclamo) -> ReclamoPublico:
    """Arma el reclamo como lo ven su autor y el admin.

    No alcanza con `from_attributes`: `partido_id` no es una columna, sale
    del objetivo, así que los campos se pasan a mano.
    """
    resuelto_por = None
    if reclamo.resuelto_por is not None:
        resuelto_por = UsuarioPublico.model_validate(reclamo.resuelto_por)
    return ReclamoPublico(
        id=reclamo.id,
        tipo_objetivo=reclamo.tipo_objetivo,
        objetivo_id=reclamo.objetivo_id,
        partido_id=partido_del_reclamo(session, reclamo),
        motivo=reclamo.motivo,
        estado=reclamo.estado,
        created_at=reclamo.created_at,
        autor=UsuarioPublico.model_validate(reclamo.autor),
        resolucion=reclamo.resolucion,
        resuelto_at=reclamo.resuelto_at,
        resuelto_por=resuelto_por,
    )


def rechazar_repetido(
    session: Session, autor: Usuario, datos: ReclamoEntrada
) -> None:
    """Levanta 409 si el autor ya tiene un reclamo abierto sobre lo mismo.

    Es una regla del reclamo, pero necesita consultar la base, así que la
    controla la ruta antes de llamar a `Reclamo.abrir` (`clases.md`).
    Uno resuelto o rechazado no cuenta: se puede volver a reclamar.
    """
    repetido = session.scalar(
        select(Reclamo.id).where(
            Reclamo.autor_id == autor.id,
            Reclamo.tipo_objetivo == datos.tipo_objetivo,
            Reclamo.objetivo_id == datos.objetivo_id,
            Reclamo.estado == EstadoReclamo.abierto,
        )
    )
    if repetido is not None:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya tenés un reclamo abierto sobre eso',
        )


@router.post('', status_code=HTTPStatus.CREATED, response_model=ReclamoPublico)
def abrir_reclamo(
    datos: ReclamoEntrada, autor: UsuarioActual, session: Session
):
    """Abre un reclamo sobre un no-show, una votación recibida, otro usuario
    o un complejo (RQ11).

    404 si el objetivo no existe, y 409 si el autor ya tiene uno abierto
    sobre lo mismo o si el objetivo no lo permite (por ejemplo, el no-show
    de otro). El admin no recibe aviso: ve los abiertos en su listado.
    """
    objetivo = buscar_objetivo(session, datos.tipo_objetivo, datos.objetivo_id)
    rechazar_repetido(session, autor, datos)
    reclamo = Reclamo.abrir(
        autor, datos.tipo_objetivo, objetivo, datos.motivo, ahora_argentina()
    )
    session.add(reclamo)
    session.commit()
    return reclamo_publico(session, reclamo)


@router.get('', response_model=ListaReclamos)
def listar_reclamos(
    usuario: UsuarioActual,
    session: Session,
    filtro: Annotated[FiltroReclamos, Query()],
):
    """Los reclamos del usuario; el admin ve los de todos (RQ11).

    Van del más nuevo al más viejo. Con `estado=abierto`, el admin ve lo
    que le queda por resolver.
    """
    consulta = select(Reclamo)
    if not usuario.tiene_rol(ROL_ADMIN):
        consulta = consulta.where(Reclamo.autor_id == usuario.id)
    if filtro.estado is not None:
        consulta = consulta.where(Reclamo.estado == filtro.estado)
    reclamos = session.scalars(
        consulta
        .order_by(Reclamo.id.desc())
        .offset(filtro.offset)
        .limit(filtro.limit)
    ).all()
    return {'reclamos': [reclamo_publico(session, r) for r in reclamos]}


def objetivo_para_resolver(
    session: Session, reclamo: Reclamo, bloquear: bool
) -> Postulacion | Votacion | Usuario | None:
    """Busca el objetivo, si la medida lo necesita.

    El no-show necesita su postulación, con el partido preparado: anularlo
    es un evento del partido y lo atienden sus observadores. La votación
    necesita la votación, y la denuncia a un usuario, al usuario, solo si
    se lo bloquea. Una denuncia a un complejo no aplica ninguna medida.
    """
    tipo = reclamo.tipo_objetivo
    if tipo == TipoObjetivo.no_show:
        postulacion = buscar_objetivo(session, tipo, reclamo.objetivo_id)
        preparar_partido(session, postulacion.partido)
        return postulacion
    if tipo == TipoObjetivo.votacion or (
        tipo == TipoObjetivo.usuario and bloquear
    ):
        return buscar_objetivo(session, tipo, reclamo.objetivo_id)
    return None


@router.patch('/{reclamo_id}', response_model=ReclamoPublico)
def responder_reclamo(
    reclamo_id: int,
    datos: ReclamoResolucion,
    admin: AdminActual,
    session: Session,
):
    """El admin resuelve o rechaza un reclamo abierto (RQ11).

    Resolverlo aplica la medida del objetivo (`Reclamo.resolver`). Si el
    admin bloquea al denunciado, además se cancelan sus partidos y se
    retiran sus postulaciones, como en RQ10. En los dos casos el autor
    recibe la respuesta. 404 si el reclamo no existe y 409 si ya se cerró
    o si se pide bloquear en algo que no es una denuncia a un usuario.
    """
    reclamo = session.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Reclamo no encontrado'
        )
    ahora = ahora_argentina()
    if datos.estado == 'rechazado':
        reclamo.rechazar(admin, datos.resolucion, ahora)
    else:
        objetivo = objetivo_para_resolver(session, reclamo, datos.bloquear)
        sancion = reclamo.resolver(
            admin, datos.resolucion, objetivo, ahora, datos.bloquear
        )
        if sancion is not None:
            sacar_de_partidos_por_jugar(session, objetivo)
    # La respuesta al autor se le pide directo a la fábrica: un reclamo no
    # es parte del Observer, que queda para los partidos (`clases.md`).
    session.add(
        FabricaNotificaciones().crear(
            TipoNotificacion.reclamo_resuelto, reclamo.autor, reclamo
        )
    )
    session.commit()
    return reclamo_publico(session, reclamo)
