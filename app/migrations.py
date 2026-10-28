"""Additive, versioned migrations. No user/rating deletion or public claiming."""

from sqlalchemy import select, text

from app.models import Base, SchemaVersion


VERSION = 1
LOCK_ID = 698217431


def migrate(engine) -> None:
    """Serialize check/create on both supported databases; roll back failures."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
        try:
            SchemaVersion.__table__.create(connection, checkfirst=True)
            current = connection.scalar(select(SchemaVersion.version).where(SchemaVersion.id == 1))
            if current is not None and current > VERSION:
                raise ValueError("Database schema is newer than this application")
            if current is None:
                # Version 1 only adds tables. Original users/movies/ratings stay intact.
                Base.metadata.create_all(connection)
                connection.execute(SchemaVersion.__table__.insert().values(id=1, version=VERSION))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def check_schema(engine) -> None:
    with engine.connect() as connection:
        if connection.scalar(select(SchemaVersion.version).where(SchemaVersion.id == 1)) != VERSION:
            raise ValueError("Database migration required: run python -m app.manage migrate")
