from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, ForeignKey, func, BigInteger
from sqlalchemy import select
from sqlalchemy.orm import relationship

from db.crud import AsyncCRUD
from db.engine import Base
from decorators.db_session import db_session


class UserEventMessage(Base):
    __tablename__ = 'user_event_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    event_id = Column(Integer, ForeignKey('user_events.id'), nullable=False)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)

    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))

    user = relationship("User", back_populates="user_events_messages")
    event = relationship("UserEvents", back_populates="user_events_messages")
    message = relationship("Message", back_populates="user_events_messages")


class UserEventMessageModel(BaseModel):
    user_id: int
    event_name: str
    message_id: int
    timestamp: datetime


class UserEventMessageCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(UserEventMessage)

    @db_session
    async def get_event_messages_by_user(self, session, user_id: int):
        query = select(UserEventMessage).filter(UserEventMessage.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()

    @db_session
    async def get_event_messages_by_event(self, session, event_id: int):
        query = select(UserEventMessage).filter(UserEventMessage.event_id == event_id)
        result = await session.execute(query)
        return result.scalars().all()

    @db_session
    async def get_event_messages_by_message(self, session, message_id: int):
        query = select(UserEventMessage).filter(UserEventMessage.message_id == message_id)
        result = await session.execute(query)
        return result.scalars().all()
