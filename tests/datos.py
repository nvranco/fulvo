from datetime import date, timedelta

CONTRASENA = 'secreta123'
EMAIL = 'ana@ejemplo.com'


def hoy_menos_anios(anios: int) -> date:
    """Fecha de hoy menos `anios` años (el 29/2 pasa al 28/2)."""
    hoy = date.today()
    try:
        return hoy.replace(year=hoy.year - anios)
    except ValueError:
        return hoy.replace(year=hoy.year - anios, day=28)


def cumple_en_un_dia(anios: int) -> date:
    """Nacimiento de alguien que cumple `anios` años mañana."""
    return hoy_menos_anios(anios) + timedelta(days=1)


def datos_de_registro(**cambios) -> dict:
    """Cuerpo válido para POST /usuarios; `cambios` pisa campos."""
    datos = {
        'email': EMAIL,
        'contrasena': CONTRASENA,
        'nombre': 'Ana',
        'apellido': 'Pérez',
        'whatsapp': '+5491100000000',
        'fecha_nacimiento': hoy_menos_anios(30).isoformat(),
        'posicion': 'Delantera',
    }
    return datos | cambios
