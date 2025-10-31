from typing import Optional

from pydantic import BaseModel
from sqlalchemy import (
    Column, ForeignKey, Integer, String, select, or_, func, and_, Boolean, BigInteger
)
from sqlalchemy.orm import relationship, joinedload

from db.crud import AsyncCRUD
from db.engine import Base
from db.models.chats import ChatCRUD
from decorators.db_session import db_session


class MessageModel(BaseModel):
    id: int
    text: str
    chat_id: int
    account_id: int
    chat_title: str
    chat_id: int
    before_update_text: str
    is_deleted: bool
    is_updated: bool
    created_at: int
    updated_at: int
    sender_user_id: int
    sender_username: str


class MessageCreateModel(BaseModel):
    text: str
    chat_id: int
    account_id: int
    sender_user_id: int
    sender_username: str


class FilterModel(BaseModel):
    username: Optional[None] | Optional[str] | Optional[list]
    chat_title: Optional[None] | Optional[str] | Optional[list]
    content: Optional[None] | Optional[str] | Optional[list]
    startswith: Optional[None] | Optional[str] | Optional[list]

    def to_dict(self):
        return {'username': self.username,
                'chat_title': self.chat_title,
                'content': self.content,
                'startswith': self.startswith}


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String)
    chat_id = Column(String, ForeignKey("chats.id"))
    message_id = Column(Integer)
    chat_title = Column(String)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    sender_user_id = Column(Integer)
    sender_username = Column(String)
    photo_id = Column(Integer)
    before_update_text = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)
    is_updated = Column(Boolean, default=False)
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))

    chat = relationship("Chat", back_populates="message")
    account = relationship("Account", back_populates="messages")
    user_events_messages = relationship("UserEventMessage", back_populates="message")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class MessageCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(Message)

    @db_session
    async def get_messages_by_ids(self, session, ids: list):
        messages = []
        for id_ in ids:
            result = await session.execute(select(Message).filter(Message.id == id_))
            res = result.scalars().one_or_none()
            messages.extend(res)
        return messages

    @db_session
    async def set_messages_deleted(self, session, ids: list):
        messages = [
            (await session.execute(select(Message).filter(Message.id == id_))).scalars().one_or_none()
            for id_ in ids
        ]

        for message in messages:
            message.is_deleted = True
        await session.commit()
        return messages

    @db_session
    async def get_filtered_messages(self, session, username: Optional[str],
                                    chat_id: Optional[int],
                                    start_time: float,
                                    end_time: Optional[float]):
        query = select(Message)
        if username:
            query = query.filter(Message.sender_username == username)
        if chat_id:
            query = query.filter(Message.chat_id == chat_id)
        query = query.filter(Message.created_at >= start_time)
        if end_time:
            query = query.filter(Message.created_at <= end_time)

        result = await session.execute(query)
        return result.scalars().all()

    @db_session
    async def get_new_messages_async(self, session, filters: dict, last_sent_time: float, account_ids: list):
        query = select(Message).where(
            Message.created_at > last_sent_time,
            Message.account_id.in_(account_ids)
        ).options(joinedload(Message.chat))

        conditions = []

        if filters.get("username"):
            if isinstance(filters["username"], str):
                conditions.append(Message.sender_username == filters["username"])
            elif isinstance(filters["username"], list):
                conditions.append(Message.sender_username.in_(filters["username"]))

        if filters.get("chat_title"):
            chat_crud = ChatCRUD()
            if isinstance(filters["chat_title"], str):
                chat = await chat_crud.get_by_title(session, filters["chat_title"])
                if chat:
                    conditions.append(Message.chat_id == chat.id)
            elif isinstance(filters["chat_title"], list):
                chat_ids = []
                for chat_title in filters["chat_title"]:
                    chat = await chat_crud.get_by_title(session, chat_title)
                    if chat:
                        chat_ids.append(chat.id)
                if chat_ids:
                    conditions.append(Message.chat_id.in_(chat_ids))

        if filters.get("content"):
            if isinstance(filters["content"], list):
                content_conditions = [Message.text.contains(content_str) for content_str in filters["content"]]
                conditions.append(or_(*content_conditions))
            elif isinstance(filters["content"], str):
                conditions.append(Message.text.contains(filters["content"]))

        if filters.get("startswith"):
            if isinstance(filters["startswith"], str):
                conditions.append(Message.text.like(f'{filters["startswith"]}%'))
            elif isinstance(filters["startswith"], list):
                start_conditions = [Message.text.startswith(prefix) for prefix in filters["startswith"]]
                conditions.append(or_(*start_conditions))

        if conditions:
            query = query.where(and_(*conditions))

        result = await session.execute(query)
        messages = result.scalars().all()

        return messages

    @db_session
    async def get_history_messages(self, session, filters: dict, account_ids: str, timestamp: int, limit: int):

        query = select(Message).filter(Message.account_id.in_(account_ids),
                                       Message.created_at < timestamp).order_by(Message.created_at.desc())

        conditions = []
        if filters["username"] is not None:
            if isinstance(filters["username"], str):
                conditions.append(Message.sender_username == filters["username"])
            elif isinstance(filters["username"], list):
                conditions.append(Message.sender_username.in_(filters["username"]))

        if filters["chat_title"] is not None:
            chat_crud = ChatCRUD()
            if isinstance(filters["chat_title"], str):
                chat = await chat_crud.get_by_title(filters["chat_title"])
                conditions.append(Message.chat_id == chat.id)
            elif isinstance(filters["chat_title"], list):
                chat_id_s = []
                for chat_title in filters["chat_title"]:
                    chat = await chat_crud.get_by_title(chat_title)
                    chat_id_s.append(chat.id)

                conditions.append(Message.chat_id.in_(chat_id_s))

        if filters["content"] is not None:
            if isinstance(filters["content"], list):
                content_conditions = [Message.text.contains(content_str) for content_str in filters["content"]]
                conditions.append(or_(*content_conditions))
            elif isinstance(filters["content"], str):
                conditions.append(Message.text.contains(filters["content"]))

        if filters["startswith"] is not None:
            if isinstance(filters["startswith"], str):
                conditions.append(Message.text.like(f'{filters["startswith"]}%'))
            elif isinstance(filters["startswith"], list):
                start_conditions = [Message.text.startswith(prefix) for prefix in filters["startswith"]]
                conditions.append(or_(*start_conditions))

        if len(conditions) > 0:
            query = (select(Message).where(Message.account_id.in_(account_ids),
                                           Message.created_at < timestamp, and_(*conditions))
                     .order_by(Message.created_at.desc()))

        result = await session.execute(query.limit(limit))
        messages = result.scalars().all()
        clear_data = sorted(messages, key=lambda m: m.created_at)
        return clear_data

    @db_session
    async def get_all_messages(self, session, filters: dict) -> list:
        query = select(Message)

        conditions = []

        if filters["username"] is not None:
            if isinstance(filters["username"], list):
                conditions.append(Message.sender_username in filters["username"])
            elif isinstance(filters["username"], str):
                conditions.append(Message.sender_username == filters["username"])

        if filters["chat_title"] is not None:
            chat_crud = ChatCRUD()
            chats_titles = []
            for chat_title in filters['chat_title']:
                chat = await chat_crud.get_by_title(chat_title)
                chats_titles.append(chat.id)
            conditions.append(Message.chat_id in chats_titles)

        if filters["content"] is not None:
            if isinstance(filters["content"], list):
                content_conditions = [Message.text.contains(content_str) for content_str in filters["content"]]
                conditions.append(or_(*content_conditions))
            elif isinstance(filters["content"], str):
                conditions.append(Message.text.contains(filters["content"]))

        if filters["startswith"] is not None:
            conditions.append(Message.text.like(f'{filters["startswith"]}%'))

        if len(conditions) > 0:
            query = query.filter(*conditions)

        result = await session.execute(query.limit(10))
        messages = result.scalars().all()
        return messages

    @db_session
    async def count_messages(self, session) -> int:
        query = select(func.count(Message.id))
        result = await session.execute(query)
        count = result.scalar()
        return count

    @db_session
    async def get_messages_by_chat_id_and_time(self, session, chat_id: int, start_time: float, end_time: float,
                                               account_id: int):
        query = select(Message).where(
            and_(
                Message.chat_id == chat_id,
                Message.created_at >= start_time,
                Message.created_at <= end_time,
                Message.account_id == account_id
            )
        )

        result = await session.execute(query)
        messages = result.scalars().all()
        return messages

    @db_session
    async def get_unique_usernames(self, session) -> list:
        query = select(Message.sender_username).distinct()
        result = await session.execute(query)
        usernames = result.scalars().all()
        return usernames

    @db_session
    async def get_unique_usernames_by_user_and_query(self, session, account_ids, q) -> list:
        query = select(Message.sender_username).filter(and_(Message.account_id.in_(account_ids),
                                                            Message.sender_username.ilike(f"%{q}%"))).distinct()
        result = await session.execute(query)
        usernames = result.scalars().all()
        return usernames
