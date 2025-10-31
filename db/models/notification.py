from collections import defaultdict
from collections import defaultdict
from typing import Optional, List

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Boolean, func, select, ForeignKey, Text, BigInteger, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, relationship

from db.crud import AsyncCRUD
from db.engine import Base
from decorators.db_session import db_session


class NotificationModel(BaseModel):
    id: int
    user_id: int
    event_id: int | None = None
    text: str
    read: bool


class MarkAsReadModel(BaseModel):
    notification_ids: List[int]


class CreateNotificationModel(BaseModel):
    user_id: int
    event_id: Optional[int] = None
    text: str
    read: bool = False


class Notification(Base):
    __tablename__ = "notification"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    event_id = Column(Integer, ForeignKey('user_events.id'), nullable=True)
    text = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, default=False)

    created_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()))
    updated_at = Column(BigInteger, nullable=False, default=func.extract('epoch', func.now()),
                        onupdate=func.extract('epoch', func.now()))

    event = relationship("UserEvents", back_populates="notifications")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class NotificationCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(Notification)

    @db_session
    async def get_all_by_user_id(self, session, user_id):
        result = await session.execute(select(Notification).filter(Notification.user_id == user_id))
        return result.scalars().all()

    @db_session
    async def get_grouped_notifications_by_user_id(self, session, user_id):
        result = await session.execute(
            select(Notification)
            .options(joinedload(Notification.event))
            .filter(Notification.user_id == user_id)
        )
        notifications = result.scalars().all()

        grouped_notifications = {"read": defaultdict(list), "unread": defaultdict(list)}

        for notification in notifications:
            event = notification.event.get_data() if notification.event else None
            notification_dict = notification.to_dict()
            notification_dict['event'] = event
            if notification.read:
                grouped_notifications["read"][event['id'] if event else None].append(notification_dict)
            else:
                grouped_notifications["unread"][event['id'] if event else None].append(notification_dict)

        grouped_notifications["read"] = dict(grouped_notifications["read"])
        grouped_notifications["unread"] = dict(grouped_notifications["unread"])

        return grouped_notifications

    @db_session
    async def get_grouped_notifications_by_event_id(self, session, user_id):
        result = await session.execute(
            select(Notification)
            .options(joinedload(Notification.event))
            .filter(Notification.user_id == user_id)
        )
        notifications = result.scalars().all()

        grouped_notifications = defaultdict(list)

        for notification in notifications:
            event_id = notification.event_id if notification.event else None
            notification_dict = notification.to_dict()
            notification_dict['event'] = notification.event.get_data() if notification.event else None
            grouped_notifications[event_id].append(notification_dict)

        return dict(grouped_notifications)

    @db_session
    async def delete_bulk(self, session: AsyncSession, notification_ids: List[int]):
        # Build the delete statement
        delete_stmt = delete(Notification).where(Notification.id.in_(notification_ids))

        # Execute the delete statement
        result = await session.execute(delete_stmt)
        await session.commit()

        # Return the number of deleted rows
        return result.rowcount
