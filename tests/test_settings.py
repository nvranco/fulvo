from fulvo.settings import Settings


def test_database_url_por_defecto_es_sqlite(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)

    # `_env_file=None` evita leer un `.env` local: el test no depende de la
    # máquina de quien lo corre.
    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == 'sqlite:///fulvo.db'


def test_variable_de_entorno_pisa_el_valor_por_defecto(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///otra.db')

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == 'sqlite:///otra.db'
