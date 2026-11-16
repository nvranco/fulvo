"""Carga datos de demo para mostrar RQ8 (votaciones) y RQ11 (reclamos).

Es una herramienta de la presentación, no parte de la API: por eso vive en
`frontend/`. Esas dos pantallas no se pueden mostrar haciendo clic, porque
las votaciones se crean recién cuando un partido termina (inicio + 60
minutos) y la API no deja publicar partidos en el pasado. Este script arma
un partido que ya se jugó, con postulantes aceptados, un no-show y votos
emitidos, usando los métodos del dominio y los observadores de siempre.

Uso, desde la raíz del repo y con la carga inicial ya hecha:

    poetry run python -m fulvo.carga_inicial
    poetry run python frontend/sembrar_demo.py

Escribe en la base de `DATABASE_URL` (el `.env`), como la carga inicial.
Correrlo dos veces no duplica nada.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# `fulvo` no se instala como paquete (`package-mode = false`): se suma la
# raíz del repo a la ruta de imports para poder correr este archivo suelto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from fulvo.database import engine  # noqa: E402
from fulvo.models import (  # noqa: E402
    ROL_USUARIO,
    Complejo,
    Partido,
    Postulacion,
    Rol,
    TipoPartido,
    Usuario,
    ahora_argentina,
)
from fulvo.observadores import (  # noqa: E402
    NotificadorPartido,
    ProcesadorPostPartido,
)
from fulvo.routes.partidos import (  # noqa: E402
    poner_al_dia_partidos_de,
    preparar_partido,
    rechazar_cupos_de_mas,
    rechazar_inicio_pasado,
)
from fulvo.security import hashear_contrasena  # noqa: E402
from fulvo.settings import Settings  # noqa: E402

CONTRASENA_DEMO = 'demo1234'

# Clave interna, email y datos de perfil de cada usuario de demo. El
# WhatsApp va en formato internacional (+54 9 11...), como sugiere el
# formulario de registro: el front arma el enlace a wa.me con esos dígitos,
# y sin el +549 WhatsApp lo tomaría como un número de otro país.
USUARIOS_DEMO = {
    'org': (
        'org@demo.fulvo',
        'Martín',
        'Gómez',
        '+5491155550001',
        1990,
        'Arquero',
    ),
    'ana': (
        'ana@demo.fulvo',
        'Ana',
        'Pérez',
        '+5491155550002',
        1995,
        'Defensora',
    ),
    'beto': (
        'beto@demo.fulvo',
        'Beto',
        'Ruiz',
        '+5491155550003',
        1988,
        'Volante',
    ),
    'caro': (
        'caro@demo.fulvo',
        'Carolina',
        'López',
        '+5491155550004',
        1998,
        'Delantera',
    ),
}

# Estrellas que Caro le pone a cada uno (y al complejo).
ESTRELLAS_DE_CARO = 4


def crear_usuarios(session: Session, rol_id: int) -> dict[str, Usuario]:
    """Crea los cuatro usuarios de demo, todos con rol usuario."""
    contrasena_hash = hashear_contrasena(CONTRASENA_DEMO)
    usuarios = {}
    for clave, datos in USUARIOS_DEMO.items():
        email, nombre, apellido, whatsapp, anio, posicion = datos
        usuarios[clave] = Usuario(
            email=email,
            contrasena_hash=contrasena_hash,
            nombre=nombre,
            apellido=apellido,
            whatsapp=whatsapp,
            fecha_nacimiento=date(anio, 5, 10),
            posicion=posicion,
            rol_id=rol_id,
        )
    session.add_all(usuarios.values())
    session.flush()
    return usuarios


def observar(session: Session, partido: Partido) -> None:
    """Le suma al partido los mismos observadores que `preparar_partido`.

    No se usa `preparar_partido` mientras se arma el partido pasado porque
    también lo pone al día: lo pasaría a jugado antes de que nadie se
    postule, y sin aceptados no habría votaciones.
    """
    partido.agregar_observador(NotificadorPartido(session))
    partido.agregar_observador(ProcesadorPostPartido(session))


def armar_partido_jugado(
    session: Session, usuarios: dict[str, Usuario], complejo_id: int
) -> int:
    """Crea un partido de hace tres horas con Ana, Beto y Caro aceptados.

    Es el único atajo del script: el partido se construye directo, sin la
    validación de la ruta que rechaza un inicio pasado. Lo demás pasa por
    `Partido.postular` y `Partido.aceptar`, que reciben `ahora`: se les pasa
    una fecha anterior al inicio, como si se hubieran postulado días antes.
    """
    inicio = ahora_argentina().replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=3)
    partido = Partido(
        organizador_id=usuarios['org'].id,
        complejo_id=complejo_id,
        inicio=inicio,
        tipo=TipoPartido.F5,
        cupos_faltantes=3,
    )
    session.add(partido)
    # El partido necesita id antes de recibir postulaciones.
    session.flush()
    observar(session, partido)

    postulaciones: list[Postulacion] = []
    for minutos, clave in enumerate(('ana', 'beto', 'caro')):
        hace_dos_dias = inicio - timedelta(days=2) + timedelta(minutes=minutos)
        postulaciones.append(partido.postular(usuarios[clave], hace_dos_dias))
    hace_un_dia = inicio - timedelta(days=1)
    for postulacion in postulaciones:
        partido.aceptar(postulacion, hace_un_dia)
    session.commit()
    return partido.id


def pasar_a_jugado(session: Session, organizador_id: int) -> None:
    """Pone al día los partidos del organizador, como `GET /votaciones`.

    Es el mecanismo real: `actualizar_estado` ve que el partido terminó,
    emite `partido_jugado` y `ProcesadorPostPartido` crea las votaciones.
    """
    poner_al_dia_partidos_de(session, session.get(Usuario, organizador_id))
    session.commit()


def marcar_no_show_de_beto(session: Session, partido_id: int) -> None:
    """El organizador marca que Beto no vino, como en la ruta (RQ8)."""
    partido = session.get(Partido, partido_id)
    preparar_partido(session, partido)
    beto = USUARIOS_DEMO['beto'][0]
    postulacion = next(
        p for p in partido.postulaciones if p.jugador.email == beto
    )
    partido.marcar_no_show(postulacion)
    session.commit()


def votar_como_caro(session: Session) -> None:
    """Caro emite todas sus votaciones pendientes, como en `PATCH`."""
    caro = session.scalar(
        select(Usuario).where(Usuario.email == USUARIOS_DEMO['caro'][0])
    )
    poner_al_dia_partidos_de(session, caro)
    for votacion in caro.votaciones_pendientes():
        votacion.emitir(ESTRELLAS_DE_CARO, ahora_argentina())
    session.commit()


def publicar_partido_de_ana(session: Session, complejo_id: int) -> None:
    """Publica un partido de Ana para mañana a las 20, con las reglas de
    la ruta `POST /partidos`, así el mapa tiene un partido abierto."""
    ana = session.scalar(
        select(Usuario).where(Usuario.email == USUARIOS_DEMO['ana'][0])
    )
    manana = ahora_argentina().date() + timedelta(days=1)
    inicio = datetime(manana.year, manana.month, manana.day, 20)
    rechazar_inicio_pasado(inicio)
    rechazar_cupos_de_mas(TipoPartido.F5, 2)
    poner_al_dia_partidos_de(session, ana)
    ana.exigir_habilitado()
    session.add(
        Partido(
            organizador_id=ana.id,
            complejo_id=complejo_id,
            inicio=inicio,
            tipo=TipoPartido.F5,
            cupos_faltantes=2,
        )
    )
    session.commit()


def imprimir_resumen() -> None:
    """Muestra con qué usuarios entrar y qué probar con cada uno."""
    admin = Settings().ADMIN_EMAIL or '(definí ADMIN_EMAIL en el .env)'
    print('Datos de demo cargados.')
    print(f'Contraseña de los usuarios de demo: {CONTRASENA_DEMO}')
    print(
        f'- {USUARIOS_DEMO["org"][0]}: Mis partidos (el partido jugado, con '
        'el no-show de Beto) y Votaciones pendientes.'
    )
    print(
        f'- {USUARIOS_DEMO["beto"][0]}: reclamar el no-show que le marcaron.'
    )
    print(
        f'- {USUARIOS_DEMO["ana"][0]}: Votaciones recibidas (las de Caro) '
        'para reclamar una, y sus votaciones pendientes.'
    )
    print(f'- {USUARIOS_DEMO["caro"][0]}: ya votó a todos.')
    print(
        f'- Admin ({admin}, contraseña ADMIN_PASSWORD): resolver o rechazar '
        'los reclamos.'
    )


def main() -> None:
    """Carga los datos de demo, salvo que ya estén."""
    with Session(engine) as session:
        rol_id = session.scalar(
            select(Rol.id).where(Rol.nombre == ROL_USUARIO)
        )
        if rol_id is None:
            sys.exit(
                'Faltan los roles: corré antes '
                '`poetry run python -m fulvo.carga_inicial`.'
            )
        complejo_id = session.scalar(select(Complejo.id).order_by(Complejo.id))
        if complejo_id is None:
            sys.exit(
                'No hay complejos: corré antes '
                '`poetry run python -m fulvo.carga_inicial`.'
            )
        email_org = USUARIOS_DEMO['org'][0]
        if session.scalar(
            select(Usuario.id).where(Usuario.email == email_org)
        ):
            print('Los datos de demo ya estaban cargados: no se hizo nada.')
            return
        usuarios = crear_usuarios(session, rol_id)
        organizador_id = usuarios['org'].id
        partido_id = armar_partido_jugado(session, usuarios, complejo_id)

    # Una sesión por paso, como pedidos separados a la API: cada uno vuelve
    # a leer el partido de la base y le suma sus observadores.
    with Session(engine) as session:
        pasar_a_jugado(session, organizador_id)
    with Session(engine) as session:
        marcar_no_show_de_beto(session, partido_id)
    with Session(engine) as session:
        votar_como_caro(session)
    with Session(engine) as session:
        publicar_partido_de_ana(session, complejo_id)
    imprimir_resumen()


if __name__ == '__main__':
    main()
