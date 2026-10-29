import pytest
from app import config, runtime


@pytest.mark.parametrize('url', ['', 'sqlite:///local.db', 'postgresql://example.invalid/db'])
def test_production_database_fails_closed(monkeypatch, url):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://portfolio.example')
    with pytest.raises(ValueError, match='PostgreSQL'): config.validate()


def test_production_validated_before_dataset_download(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr(runtime, 'ensure_prepared', lambda *args: pytest.fail('Download before config validation'))
    with pytest.raises(SystemExit, match='PostgreSQL'): runtime.main()


def test_development_retains_sqlite_and_production_accepts_tls(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    config.validate()
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://portfolio.example')
    config.validate('postgresql://example.invalid/db?sslmode=require')
