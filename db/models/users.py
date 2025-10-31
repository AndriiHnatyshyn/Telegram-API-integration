from datetime import datetime

import bcrypt
from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, select, and_, BigInteger, update, Boolean, DateTime, func
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from db.engine import Base
from decorators.db_session import db_session
from db.crud import AsyncCRUD


class UserModel(BaseModel):
    username: str
    password: str
    email: str = None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, index=True, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, index=True, unique=True, nullable=True)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))
    verification_token = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    tg_notifications = Column(Boolean, default=False)
    scrape_forward_mode = Column(Boolean, default=False)
    target_chats = Column(String, default=None)

    event = relationship("UserEvents", back_populates="users")
    filter = relationship("UserFilters", back_populates="user")
    user_events_messages = relationship("UserEventMessage", back_populates="user")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UserResponseModel(BaseModel):
    id: int
    username: str
    tg_id: int | None
    email: str
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    is_verified: bool
    tg_notifications: bool
    scrape_forward_mode: bool
    target_chats: str | None


class UserRegistrationResponseModel(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    updated_at: datetime
    is_verified: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(User)

    async def set_notification_status(self, user_id: int, status: bool):
        updated = await self.update(id=user_id, tg_notifications=status)
        return updated

    @db_session
    async def validate_credentials(self, session: AsyncSession, username: str, password: str) -> User | None:
        # Query to find the user by username
        query = select(self.model).where(self.model.username == username)
        result = await session.execute(query)
        user = result.scalars().one_or_none()
        stored_password = user.password.encode('utf-8') if isinstance(user.password, str) else user.password

        if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
            return user

        # Return None if the credentials are invalid
        return None

    @db_session
    async def get_user_id_by_username(self, session, username: str):
        query = select(self.model).where(self.model.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        return user if user else None

    @db_session
    async def update_user_tg_id(self, session, tg_id: int, user_id: int):
        existing_user_query = select(self.model.id).where(self.model.tg_id == tg_id)
        existing_user = await session.execute(existing_user_query)
        existing_user_id = existing_user.scalars().first()

        if existing_user_id is not None and existing_user_id != user_id:
            # If tg_id is assigned to another user, raise an exception or handle as needed
            return {'error': 'Telegram ID is already assigned to another user', 'user_id': existing_user_id}

        # Update tg_id for the specified user_id
        update_query = (
            update(self.model)
            .where(self.model.id == user_id)
            .values(tg_id=tg_id)
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(update_query)
        await session.commit()
        return {'success': True, 'user_id': user_id}

    @db_session
    async def get_user_by_email(self, session, email: str):
        query = select(self.model).where(self.model.email == email)
        result = await session.execute(query)
        user = result.scalars().one_or_none()

        return user

    @db_session
    async def get_user_by_username(self, session, username: str):
        query = select(self.model).where(self.model.username == username)
        result = await session.execute(query)
        user = result.scalars().one_or_none()

        return user

    @db_session
    async def get_all(self, session):
        result = await session.execute(select(User))
        return result.scalars().all()
