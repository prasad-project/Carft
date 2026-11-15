from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import Base

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # `users` belongs to your existing auth system; never let autogenerate touch it.
    return not (type_ == "table" and name == "users")


def run():
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, include_object=include_object, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
