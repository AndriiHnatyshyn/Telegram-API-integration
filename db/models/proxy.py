from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean, func, select, BigInteger
from sqlalchemy.orm import relationship

from db.crud import AsyncCRUD
from db.engine import Base
from decorators.db_session import db_session


class ProxyModel(BaseModel):
    ip: str
    port: int
    type: str
    login: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None


class ProxyResponseModel(BaseModel):
    id: int
    ip: str
    port: int
    type: str
    login: Optional[str]
    password: Optional[str]
    location: Optional[str]


class Proxy(Base):
    __tablename__ = "proxy"
    id = Column(Integer, primary_key=True)
    ip = Column(String)
    port = Column(Integer)
    type = Column(String)
    login = Column(String)
    password = Column(String)
    location = Column(String, nullable=True, default='usa')
    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))
    in_use = Column(Boolean, default=False)

    account = relationship("Account", back_populates="proxy")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class ProxyCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(Proxy)

    @db_session
    async def get_all_available(self, session):
        result = await session.execute(select(Proxy).where(Proxy.in_use == False))
        return result.scalars().all()

    @db_session
    async def get_all(self, session):
        result = await session.execute(select(Proxy))
        return result.scalars().all()

    @db_session
    async def get_available_by_location(self, session, location: str):
        result = await session.execute(select(Proxy).where(Proxy.in_use.is_(False),
                                                           Proxy.location == location))
        return result.scalars().all()
