from fulvo.models import Zona
from fulvo.schemas import ZonaPublica


def test_zona_publica_se_arma_desde_el_modelo(session):
    zona = Zona(nombre='Belgrano', provincia='CABA')
    session.add(zona)
    session.commit()

    publica = ZonaPublica.model_validate(zona)

    assert publica.model_dump() == {
        'id': zona.id,
        'nombre': 'Belgrano',
        'provincia': 'CABA',
    }
