from contextlib import asynccontextmanager
from functools import wraps
from db.engine import async_session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError


@asynccontextmanager
async def session_scope():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except (SQLAlchemyError, IntegrityError):
            await session.rollback()
            raise
        finally:
            await session.close()


def db_session(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with session_scope() as session:
            return await func(self, session, *args, **kwargs)
    return wrapper
