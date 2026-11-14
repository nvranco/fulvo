import pytest
from pydantic import ValidationError

from fulvo.settings import Settings

MINUTOS_POR_DEFECTO = 30


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


def test_valores_por_defecto_de_jwt(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'una-clave')
    monkeypatch.delenv('ALGORITHM', raising=False)
    monkeypatch.delenv('ACCESS_TOKEN_EXPIRE_MINUTES', raising=False)

    settings = Settings(_env_file=None)

    assert settings.ALGORITHM == 'HS256'
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == MINUTOS_POR_DEFECTO


def test_sin_secret_key_la_configuracion_falla(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_las_credenciales_del_admin_son_opcionales(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'una-clave')
    monkeypatch.delenv('ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)

    settings = Settings(_env_file=None)

    assert settings.ADMIN_EMAIL is None
    assert settings.ADMIN_PASSWORD is None


def test_sin_cors_origins_no_se_permite_ningun_origen(monkeypatch):
    monkeypatch.delenv('CORS_ORIGINS', raising=False)

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == []


def test_cors_origins_se_lee_del_env_como_lista_json(monkeypatch, tmp_path):
    monkeypatch.delenv('CORS_ORIGINS', raising=False)
    archivo_env = tmp_path / '.env'
    # El mismo formato que muestra `.env.example`.
    archivo_env.write_text(
        'CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5500"]\n',
        encoding='utf-8',
    )

    settings = Settings(_env_file=archivo_env)

    assert settings.CORS_ORIGINS == [
        'http://localhost:5173',
        'http://127.0.0.1:5500',
    ]
