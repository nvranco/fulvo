from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
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
from fulvo.observadores import NotificadorPartido, ProcesadorPostPartido
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
    complejo no existe. 409 si debe votaciones en más de X partidos
    (bloqueo por deuda, RQ8): antes se ponen al día sus partidos, para que
    la deuda incluya los que ya terminaron.
    """
    rechazar_inicio_pasado(datos.inicio)
    rechazar_cupos_de_mas(datos.tipo, datos.cupos_faltantes)
    buscar_complejo(session, datos.complejo_id)
    poner_al_dia_partidos_de(session, organizador)
    organizador.exigir_habilitado()
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


def preparar_partido(session: Session, partido: Partido) -> None:
    """Bloquea el partido, le suma sus observadores y lo pone al día.

    Primero lo vuelve a leer con `SELECT ... FOR UPDATE`: su fila queda
    bloqueada hasta el commit del pedido. Si otro pedido lo está cambiando
    en ese momento, este espera y lo lee ya cambiado. Sin el bloqueo, dos
    pedidos a la vez sobre un partido recién terminado lo pasaban dos veces
    a jugado, y el segundo chocaba con las votaciones del primero (un 500);
    también dos aceptaciones a la vez se pisaban los cupos. SQLite ignora el
    bloqueo, y ahí solo se desarrolla. Se llama antes de cambiar el partido,
    porque `refresh` descarta los cambios que todavía no se mandaron.

    Los observadores no se guardan en la base: cada pedido los suma, antes
    de que pase cualquier cosa. Si el partido ya los tiene (porque ya está
    en memoria en esta sesión), no se repiten: si no, cada evento llegaría
    dos veces. Son dos: `NotificadorPartido` (RQ9) y `ProcesadorPostPartido`
    (RQ8).

    Después revisa si ya terminó: es el pase a jugado al consultar que pide
    `docs/requerimientos.md`. El commit de cada ruta guarda el cambio.
    """
    session.refresh(partido, with_for_update=True)
    if not partido.observadores:
        partido.agregar_observador(NotificadorPartido(session))
        partido.agregar_observador(ProcesadorPostPartido(session))
    partido.actualizar_estado(ahora_argentina())


def poner_al_dia_partidos_de(session: Session, usuario: Usuario) -> None:
    """Pasa a jugado los partidos del usuario que ya terminaron (RQ8).

    La deuda se cuenta con las votaciones pendientes, y esas se crean
    recién cuando alguien consulta el partido terminado. Si nadie lo
    consultó, el usuario todavía no tendría sus votaciones. Por eso, antes
    de listar sus votaciones o de calcular su deuda, se preparan los
    partidos en los que juega (como organizador o aceptado) que siguen en
    juego y ya empezaron. Cuáles terminaron lo decide `actualizar_estado`.

    Van en orden de id: preparar uno lo bloquea hasta el commit, y bloquear
    siempre en el mismo orden evita que dos pedidos se queden esperando uno
    al otro.
    """
    en_juego = [EstadoPartido.abierto, EstadoPartido.completo]
    aceptado = select(Postulacion.partido_id).where(
        Postulacion.jugador_id == usuario.id,
        Postulacion.estado == EstadoPostulacion.aceptada,
    )
    partidos = session.scalars(
        select(Partido)
        .where(
            Partido.estado.in_(en_juego),
            Partido.inicio <= ahora_argentina(),
            or_(
                Partido.organizador_id == usuario.id,
                Partido.id.in_(aceptado),
            ),
        )
        .order_by(Partido.id)
    ).all()
    for partido in partidos:
        preparar_partido(session, partido)


def sacar_de_partidos_por_jugar(session: Session, usuario: Usuario) -> None:
    """Cancela los partidos del usuario y retira sus postulaciones (RQ10).

    La usa el bloqueo: un usuario bloqueado ya no entra a la app, así que no
    podría aceptar jugadores ni coordinar (decisión del equipo del
    2026-11-12). Solo toca partidos que todavía no empezaron: los que ya
    empezaron o se jugaron quedan como están, con sus votaciones. Cada
    cambio pasa por los métodos de `Partido`, así los afectados reciben los
    avisos de siempre (partido cancelado, postulación retirada) y el patrón
    Observer no cambia. Desbloquear no deshace nada de esto. Los partidos
    van en orden de id, como en `poner_al_dia_partidos_de`.
    """
    por_jugar = (
        Partido.estado.in_([EstadoPartido.abierto, EstadoPartido.completo]),
        Partido.inicio > ahora_argentina(),
    )
    organizados = session.scalars(
        select(Partido)
        .where(Partido.organizador_id == usuario.id, *por_jugar)
        .order_by(Partido.id)
    ).all()
    for partido in organizados:
        preparar_partido(session, partido)
        partido.cancelar()

    postulaciones = session.scalars(
        select(Postulacion)
        .join(Postulacion.partido)
        .where(
            Postulacion.jugador_id == usuario.id,
            Postulacion.estado.in_([
                EstadoPostulacion.en_espera,
                EstadoPostulacion.aceptada,
            ]),
            *por_jugar,
        )
        .order_by(Postulacion.partido_id)
    ).all()
    for postulacion in postulaciones:
        preparar_partido(session, postulacion.partido)
        postulacion.partido.retirar(postulacion)


def buscar_partido(session: Session, partido_id: int) -> Partido:
    """Devuelve el partido con ese id, preparado, o levanta 404.

    Lo usan todas las rutas que reciben un partido, así ninguna trabaja con
    un estado viejo ni sin sus observadores, y cada una lo tiene bloqueado
    hasta su commit (`preparar_partido`).
    """
    partido = session.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Partido no encontrado'
        )
    preparar_partido(session, partido)
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
        no_show=postulacion.no_show,
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
        no_show=postulacion.no_show,
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

    409 si el partido no está abierto o ya empezó, si es el organizador,
    si ya se había postulado antes o si debe votaciones en más de X
    partidos (RQ8). Antes se ponen al día sus partidos, por la deuda.
    """
    partido = buscar_partido(session, partido_id)
    poner_al_dia_partidos_de(session, jugador)
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
    """El organizador responde una postulación (RQ6 a RQ8).

    Acepta, rechaza o revoca (`{"estado": ...}`), o marca que el jugador
    aceptado no vino (`{"no_show": true}`), que solo se puede con el partido
    jugado. 403 si no es el organizador, 404 si la postulación no es de este
    partido y 409 si el cambio no se puede hacer desde el estado actual. Al
    aceptar, la respuesta ya trae el WhatsApp del jugador.
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
    if datos.no_show:
        partido.marcar_no_show(postulacion)
    elif datos.estado == EstadoPostulacion.aceptada:
        partido.aceptar(postulacion, ahora)
    elif datos.estado == EstadoPostulacion.rechazada:
        partido.rechazar(postulacion, ahora)
    else:
        partido.revocar(postulacion, ahora)
    session.commit()
    return postulacion_del_partido(postulacion)
