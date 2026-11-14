"""Pedidos simultáneos sobre un mismo partido, contra el PostgreSQL de prueba.

El `client` de los demás tests comparte una sola sesión y manda los pedidos
de a uno, así que no puede mostrar una carrera. Acá cada pedido corre en su
propio hilo, con su propia sesión y su propia conexión, como en producción
(`get_session` abre una sesión por pedido).
"""

import threading
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fulvo.models import (
    EstadoPartido,
    EstadoPostulacion,
    Notificacion,
    Partido,
    Postulacion,
    TipoNotificacion,
    Usuario,
    Votacion,
    ahora_argentina,
)
from fulvo.routes.partidos import buscar_partido, poner_al_dia_partidos_de
from tests.factories import (
    guardar_aceptado,
    guardar_partido,
    guardar_usuario_comun,
)


def a_la_vez(engine, *pedidos) -> list[Exception]:
    """Corre cada pedido en su hilo y con su sesión, todos al mismo tiempo.

    Cada pedido recibe su sesión, hace lo mismo que una ruta y después se
    confirma con `commit`. La barrera los larga juntos, como dos personas
    que abren la app en el mismo momento. Devuelve los errores que
    levantaron: un error dentro de un hilo no hace fallar el test por sí
    solo, así que se juntan para revisarlos al final.
    """
    barrera = threading.Barrier(len(pedidos))
    errores = []

    def correr(pedido):
        with Session(engine) as session:
            barrera.wait()
            try:
                pedido(session)
                session.commit()
            # Cualquier error: el 409 esperado o un choque en la base.
            except Exception as error:
                errores.append(error)

    hilos = [threading.Thread(target=correr, args=(p,)) for p in pedidos]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return errores


def contar(session, modelo, *condiciones) -> int:
    """Cuántas filas de `modelo` cumplen las condiciones."""
    consulta = select(func.count()).select_from(modelo).where(*condiciones)
    return session.scalar(consulta)


def test_varios_pedidos_a_la_vez_pasan_el_partido_a_jugado_una_sola_vez(
    engine, session, usuario, otro_usuario
):
    inicio = ahora_argentina() - timedelta(hours=2)
    partido = guardar_partido(session, usuario, inicio=inicio)
    guardar_aceptado(session, partido, otro_usuario)
    # Los hilos usan sus propias sesiones: se les pasan los ids, no objetos
    # de esta sesión.
    partido_id, organizador_id, jugador_id = (
        partido.id,
        usuario.id,
        otro_usuario.id,
    )

    errores = a_la_vez(
        engine,
        # Lo que hace `GET /usuarios/yo` del organizador y del jugador, y dos
        # `GET /partidos/{id}`: los cuatro revisan el partido terminado.
        lambda s: poner_al_dia_partidos_de(s, s.get(Usuario, organizador_id)),
        lambda s: poner_al_dia_partidos_de(s, s.get(Usuario, jugador_id)),
        lambda s: buscar_partido(s, partido_id),
        lambda s: buscar_partido(s, partido_id),
    )

    # Los hilos escribieron con otras sesiones: se descarta lo que esta
    # sesión tenía en memoria y se vuelve a leer de la base.
    session.expire_all()
    assert errores == []
    assert session.get(Partido, partido_id).estado == EstadoPartido.jugado
    # 2 participantes: cada uno vota al otro y al complejo, una sola vez.
    participantes = 2
    votaciones = contar(session, Votacion, Votacion.partido_id == partido_id)
    assert votaciones == participantes * participantes
    jugados = [
        session.get(Usuario, i).partidos_jugados
        for i in (organizador_id, jugador_id)
    ]
    assert jugados == [1, 1]
    avisos = contar(
        session,
        Notificacion,
        Notificacion.tipo == TipoNotificacion.votaciones_pendientes,
        Notificacion.referencia_tipo == 'partido',
        Notificacion.referencia_id == partido_id,
    )
    assert avisos == len(jugados)


def test_dos_aceptaciones_a_la_vez_no_superan_los_cupos(
    engine, session, usuario
):
    partido = guardar_partido(session, usuario, cupos_faltantes=1)
    ahora = ahora_argentina()
    jugadores = [guardar_usuario_comun(session, usuario.rol_id) for _ in '12']
    postulaciones = [partido.postular(j, ahora) for j in jugadores]
    session.commit()
    partido_id = partido.id
    postulacion_ids = [p.id for p in postulaciones]

    def aceptar(postulacion_id):
        """Lo que hace `PATCH /partidos/{id}/postulaciones/{id}` al aceptar."""

        def pedido(s):
            partido = buscar_partido(s, partido_id)
            postulacion = s.get(Postulacion, postulacion_id)
            partido.aceptar(postulacion, ahora_argentina())

        return pedido

    errores = a_la_vez(engine, *(aceptar(i) for i in postulacion_ids))

    session.expire_all()
    # El segundo encuentra el partido completo: es el 409 de siempre.
    assert [str(error) for error in errores] == ['El partido no está abierto']
    estados = sorted(
        session.get(Postulacion, i).estado for i in postulacion_ids
    )
    assert estados == [EstadoPostulacion.aceptada, EstadoPostulacion.rechazada]
    assert session.get(Partido, partido_id).cupos_faltantes == 0
    avisos = contar(
        session,
        Notificacion,
        Notificacion.tipo == TipoNotificacion.postulacion_aceptada,
    )
    assert avisos == 1
