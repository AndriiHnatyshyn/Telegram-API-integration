import json
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Boolean, func, select, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship

from db.crud import AsyncCRUD
from db.engine import Base
from decorators.db_session import db_session


class UserFilterModel(BaseModel):
    id: int
    user_id: int
    username: Optional[str]
    chat_title: Optional[str]
    content: Optional[str]
    startswith: Optional[str]


class UserFilters(Base):
    __tablename__ = "user_filters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(Text, nullable=True)
    chat_title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    startswith = Column(Text, nullable=True)
    triggers_count = Column(Integer, nullable=False, default=0)
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))
    scrape_and_forward_mode = Column(Boolean, default=False)

    user = relationship("User", back_populates="filter")

    def set_data(self, data: dict):
        self.user_id = data.get('user_id', self.user_id)
        self.username = json.dumps(data.get('username', []))
        self.chat_title = json.dumps(data.get('chat_title', []))
        self.content = json.dumps(data.get('content', []))
        self.startswith = json.dumps(data.get('startswith', []))
        self.scrape_and_forward_mode = data.get('scrape_and_forward_mode', False)

    def get_data(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': json.loads(self.username) if self.username else [],
            'chat_title': json.loads(self.chat_title) if self.chat_title else [],
            'content': json.loads(self.content) if self.content else [],
            'startswith': json.loads(self.startswith) if self.startswith else [],
            'triggers_count': self.triggers_count,
        }

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UserFiltersCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(UserFilters)

    @db_session
    async def create(self, session, data: dict, user_id):
        existing_event = await session.execute(
            select(UserFilters).filter_by(
                user_id=user_id,
                username=json.dumps(data.get('username', [])),
                chat_title=json.dumps(data.get('chat_title', [])),
                content=json.dumps(data.get('content', [])),
                startswith=json.dumps(data.get('startswith', [])),
                scrape_and_forward_mode=data.get('scrape_and_forward_mode', False)
            )
        )

        existing_event = existing_event.scalars().first()

        data.update({"user_id": user_id})
        if existing_event:
            return {"error": "Duplicate event already exists."}

        existing_filters = await session.execute(
            select(UserFilters).filter(UserFilters.user_id == data['user_id']).order_by(UserFilters.created_at.asc())
        )
        existing_filters = existing_filters.scalars().all()

        if len(existing_filters) >= 10:
            oldest_filter = existing_filters[0]
            await session.delete(oldest_filter)
            await session.commit()

        instance = UserFilters()
        instance.set_data(data)
        session.add(instance)
        await session.commit()
        return instance

    @db_session
    async def get_all_by_user_id(self, session, user_id):
        result = await session.execute(select(UserFilters).filter(UserFilters.user_id == user_id))
        return result.scalars().all()

    @db_session
    async def get_scrape_and_forward_filters(self, session, user_id):
        result = await session.execute(select(UserFilters).filter(UserFilters.user_id.is_(user_id),
                                                                  UserFilters.scrape_and_forward_mode == True))
        return result.scalars().all()

    @db_session
    async def get_all(self, session):
        result = await session.execute(select(UserFilters))
        return result.scalars().all()
