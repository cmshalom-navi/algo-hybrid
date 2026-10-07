"""Create the database and the tables of the ORM models, if missing.

Connects with the POSTGRES_* settings in common.config. Creates the
database itself first if it doesn't exist, then the tables and enum types
of common.cdm. Existing tables are left untouched, so this is safe to
re-run, but it does not migrate tables whose models have changed.
"""

import sqlalchemy as sa

from common import cdm
from common import config


def _url(database: str) -> sa.URL:
    """Returns the URL of a database on the configured server.

    Args:
        database: Name of the database.

    Returns:
        The SQLAlchemy URL.
    """
    return sa.URL.create(
        "postgresql+psycopg",
        username=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        database=database,
    )


def _create_database() -> None:
    """Creates the configured database if it doesn't exist."""
    engine = sa.create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.scalar(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": config.POSTGRES_DB},
        )
        if not exists:
            name = engine.dialect.identifier_preparer.quote(config.POSTGRES_DB)
            connection.execute(sa.text(f"CREATE DATABASE {name}"))
            print(f"created database {config.POSTGRES_DB}")
    engine.dispose()


def main() -> None:
    """Creates the database and its tables."""
    _create_database()
    engine = sa.create_engine(_url(config.POSTGRES_DB))
    cdm.Base.metadata.create_all(engine)
    engine.dispose()
    tables = ", ".join(cdm.Base.metadata.tables)
    print(f"tables in {config.POSTGRES_DB}: {tables}")


if __name__ == "__main__":
    main()
