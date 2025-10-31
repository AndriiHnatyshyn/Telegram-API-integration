from operator import and_
from typing import List, Optional

from sqlalchemy import Column, Integer, String, select, BigInteger, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, joinedload, aliased
from db.engine import Base
from db.crud import AsyncCRUD
from pydantic import BaseModel

from db.models.accounts import Account
from db.models.associations import account_chat_association
from decorators.db_session import db_session


class ChatCreateUpdateRequest(BaseModel):
    chat_title: str
    chat_username: str
    chat_type: str
    account_ids: List[int]


class ChatModel(BaseModel):
    id: int
    chat_title: Optional[None] | Optional[str]
    chat_username: Optional[None] | Optional[str]
    chat_type: Optional[None] | Optional[str]

    class Config:
        from_attributes = True


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, autoincrement=False)
    chat_title = Column(String, nullable=True)
    chat_username = Column(String, nullable=True)
    chat_type = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))

    accounts = relationship("Account", secondary=account_chat_association, back_populates="chats")
    message = relationship("Message", back_populates="chat")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class ChatCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(Chat)

    @db_session
    async def create(self, session, **kwargs):
        existing_chat = await self.read(kwargs['id'])
        if existing_chat:
            return existing_chat

        instance = self.model(**kwargs)
        session.add(instance)
        await session.commit()
        return instance

    @db_session
    async def get_chats_for_account(self, session: AsyncSession, account_id: int):
        # Fetch chats associated with the account
        result = await session.execute(
            select(Chat)
            .join(Chat.accounts)
            .options(joinedload(Chat.accounts))
            .where(Account.id == account_id)
        )
        chats = result.unique().scalars().all()
        return chats

    @db_session
    async def get_all(self, session: AsyncSession) -> List[Chat]:
        result = await session.execute(select(self.model))
        return result.scalars().all()

    @db_session
    async def get_all_by_accounts(self, session: AsyncSession, account_ids: list):
        # Query to get all chats associated with the given account_ids
        result = await session.execute(
            select(Chat)
            .join(Chat.accounts)
            .options(joinedload(Chat.accounts))
            .where(Account.id.in_(account_ids))
        )
        chats = result.unique().scalars().all()
        return chats

    @db_session
    async def search_chats_by_title(self, session, title_query: str, account_ids: list):
        account_chat_alias = aliased(account_chat_association)

        query = (
            select(Chat)
            .join(account_chat_alias, Chat.id == account_chat_alias.c.chat_id)
            .filter(and_(
                account_chat_alias.c.account_id.in_(account_ids),
                Chat.chat_title.ilike(f"%{title_query}%")
            ))
        )

        result = await session.execute(query)
        chats = result.scalars().all()
        return chats

    @db_session
    async def get_by_title(self, db, title: str):
        query = select(self.model).where(self.model.chat_title == title)
        result = await db.execute(query)
        return result.scalars().one_or_none()

    @db_session
    async def add_account_to_chat(self, session: AsyncSession, chat_id: int, account_id: int):
        result = await session.execute(
            select(Chat).options(joinedload(Chat.accounts)).where(Chat.id == chat_id)
        )

        chat = result.unique().scalars().one_or_none()

        if not chat:
            return {"error": "Chat not found"}
        account = await session.get(Account, account_id)
        if not account:
            return {"error": "Account not found"}

        chat.accounts.append(account)
        await session.commit()

        return chat
