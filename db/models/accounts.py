from datetime import datetime
from typing import List

from pydantic import BaseModel
from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, select, Boolean, BigInteger, func, Table,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from db.crud import AsyncCRUD
from db.engine import Base
from db.models.associations import account_chat_association
from decorators.db_session import db_session


class AccountModel(BaseModel):
    id: str
    username: str
    created_by: int


class AccountResponseModel(BaseModel):
    id: str
    username: str
    created_by: int | None
    created_at: datetime
    active: bool

    class Config:
        from_attributes = True


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, index=True, primary_key=True, unique=True)
    username = Column(String, index=True, nullable=True)
    active = Column(Boolean, default=True)
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))

    chats = relationship("Chat", secondary=account_chat_association,
                         back_populates="accounts", cascade="all")
    messages = relationship("Message", back_populates="account", cascade="all, delete-orphan")
    proxy = relationship("Proxy", back_populates='account')

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class AccountCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(Account)

    @db_session
    async def delete_on_cascade(self, session: AsyncSession, account_id: str):
        # Attempt to find the account by id

        query = select(self.model).where(self.model.id == account_id)
        result = await session.execute(query)
        try:
            account_to_delete = result.scalar_one()
            await session.delete(account_to_delete)
            await session.commit()
            return {"message": "Account and related entities deleted successfully"}
        except NoResultFound:
            await session.rollback()
            return {"error": "Account not found"}

    @db_session
    async def get_all_accounts(self, session: AsyncSession):
        query = select(Account)  # Assuming Message is your ORM model

        result = await session.execute(query)
        return result.scalars().all()

    @db_session
    async def set_active(self, session: AsyncSession, phone: str, choose: bool):
        query = select(Account).where(Account.id == phone)
        result = await session.execute(query)
        result = result.scalar_one_or_none()
        if result:
            result.active = 1 if choose else 0
            await session.commit()
            return {"message": "Account updated successfully"}
        return {"error": "Account not found"}

    @db_session
    async def get_accounts_by_user_id(self, session, user_id: int):
        query = select(Account).where(Account.created_by == user_id)
        result = await session.execute(query)
        return result.scalars().all()

