import asyncio
from db.engine import engine, Base, async_session
from sqlalchemy.future import select
from db.models.users import User  # don`t remove this import
from db.models.accounts import Account  # don`t remove this import
from db.models.chats import Chat  # don`t remove this import
from db.models.message import Message  # don`t remove this import
from db.models.proxy import Proxy  # don`t remove this import
from db.models.user_events import UserEvents  # don`t remove this import
from db.models.user_event_messages import UserEventMessage  # don`t remove this import
from db.models.filters import UserFilters  # don`t remove this import
from db.models.notification import Notification  # don`t remove this import


async def create_tables():

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # # Now, add the base user
        # async with async_session() as session:
        #     async with session.begin():
        #         # Check if the base user already exists
        #         result = await session.execute(select(User).filter_by(username="baseuser"))
        #         base_user = result.scalars().first()
        #
        #         if not base_user:
        #             # Create and add the base user
        #             base_user = User(username="baseuser", password="password", email="baseuser@example.com")
        #             session.add(base_user)
        #
        #         # Commit the session if new user added
        #         await session.commit()

if __name__ == "__main__":
    asyncio.run(create_tables())
