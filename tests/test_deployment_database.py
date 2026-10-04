import pytest
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from app import database
from app.models import Movie, User, UserRating


def test_explicit_sqlite_path_overrides_url_and_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused.invalid/db")
    engine = database.create_database_engine(tmp_path / "local.db", database_url="invalid")
    try:
        assert engine.dialect.name == "sqlite"
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()


def test_postgresql_url_and_bounded_configuration(monkeypatch):
    captured = {}
    def create(url, **kwargs):
        captured.update(url=url, **kwargs)
        return captured
    monkeypatch.setattr(database, "create_engine", create)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/env")
    result = database.create_database_engine(database_url="postgresql://example.invalid/explicit?sslmode=require&channel_binding=require")
    assert result['url'].drivername == 'postgresql+psycopg'
    assert result['url'].database == 'explicit'
    assert dict(result['url'].query) == {'sslmode':'require','channel_binding':'require'}
    assert result['pool_size'] == 2 and result['max_overflow'] == 0
    assert result['pool_pre_ping'] and result['pool_timeout'] == 3
    assert result['connect_args'] == {'connect_timeout':5,'prepare_threshold':None}
    assert result['hide_parameters']
    assert database.create_database_engine()['url'].database == 'env'


def test_sqlite_url_only_creates_sqlite_directories(tmp_path):
    path = tmp_path / 'nested/local.db'
    engine = database.create_database_engine(database_url=f'sqlite:///{path.as_posix()}')
    assert path.parent.is_dir()
    engine.dispose()
    memory = database.create_database_engine(database_url='sqlite:///:memory:')
    assert memory.url.database == ':memory:'
    memory.dispose()


@pytest.mark.parametrize('url', ['not a url', 'mysql://example.invalid/db'])
def test_configuration_errors_are_safe(url, capsys):
    with pytest.raises(ValueError) as error:
        database.create_database_engine(database_url=url)
    assert url not in str(error.value)
    assert not capsys.readouterr().out


@pytest.mark.parametrize('model', [User, Movie, UserRating])
def test_id_ddl_preserves_int64_and_sqlite_integer(model):
    pg = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
    local = str(CreateTable(model.__table__).compile(dialect=sqlite.dialect()))
    assert 'BIGINT' in pg or 'BIGSERIAL' in pg
    assert 'BIGINT' not in local and 'INTEGER' in local
    if model is User:
        assert 'AUTOINCREMENT' in local and 'BIGSERIAL' in pg


@pytest.mark.parametrize('dialect', [postgresql.dialect(), sqlite.dialect()])
def test_native_conflict_statements_compile(dialect):
    movie = database.conflict_insert(Movie,dialect.name).values(movie_id=10).on_conflict_do_nothing(index_elements=['movie_id'])
    rating = database.conflict_insert(UserRating,dialect.name).values(user_id=1,movie_id=10,rating=4.).on_conflict_do_update(index_elements=['user_id','movie_id'],set_={'rating':4.})
    assert 'ON CONFLICT (movie_id) DO NOTHING' in str(movie.compile(dialect=dialect))
    assert 'ON CONFLICT (user_id, movie_id) DO UPDATE SET rating' in str(rating.compile(dialect=dialect))


def test_postgresql_catalog_registration_uses_batches():
    class Bind:
        dialect = postgresql.dialect()
    class Session:
        statements = []
        def get_bind(self): return Bind()
        def execute(self, statement): self.statements.append(statement)
    session = Session()
    database.register_movies(session, range(1,2502))
    assert len(session.statements) == 3
    assert [len(statement.compile(dialect=postgresql.dialect()).params) for statement in session.statements] == [1000,1000,501]
