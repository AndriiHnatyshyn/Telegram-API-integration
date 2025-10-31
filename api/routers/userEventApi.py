from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from api.security import get_current_user_id, require_role
from db.facade import DB
from db.models.message import MessageModel
from db.models.user_events import UserEventModel


router = APIRouter()
db_crud = DB()


@router.post("/user_events/", response_model=UserEventModel | dict, status_code=status.HTTP_201_CREATED)
async def create_user_event(user_event: dict, user_id: int = Depends(get_current_user_id)):

    new_event = await db_crud.userEvent_crud.create(user_event, user_id)
    return new_event


@router.get("/user_events/{event_id}", response_model=UserEventModel)
async def read_user_event(event_id: int, user_id: int = Depends(get_current_user_id)):
    event = await db_crud.userEvent_crud.read(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="User event not found")
    return event


@router.put("/user_events/{event_id}", response_model=UserEventModel)
async def update_user_event(event_id: int, user_event: UserEventModel, user_id: int = Depends(get_current_user_id)):
    updated_event = await db_crud.userEvent_crud.update(event_id, **user_event.model_dump())
    if not updated_event:
        raise HTTPException(status_code=404, detail="User event not found")
    return updated_event


@router.delete("/user_events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_event(event_id: int, user_id: int = Depends(get_current_user_id)):
    await db_crud.userEvent_crud.delete(event_id)
    return {"detail": "User event deleted"}


@router.get("/user_events_all/", response_model=List[UserEventModel])
@require_role('admin')
async def get_all_user_events():
    events = await db_crud.userEvent_crud.get_all()
    return events


@router.get("/user_events/user/me", response_model=List[dict])
async def get_user_events_by_user_id(user_id: int = Depends(get_current_user_id)):
    events = await db_crud.userEvent_crud.get_all_by_user_id(user_id)
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this user")
    events = [event.get_data() for event in events]
    return events


@router.get("/triggered_messages/event/{event_id}", response_model=List[MessageModel])
async def get_triggered_messages_by_event_id(event_id: int):
    event_messages = await db_crud.userEventMessage_crud.get_event_messages_by_event(event_id)
    if not event_messages:
        raise HTTPException(status_code=404, detail="No messages found for this event")

    message_ids = [em.message_id for em in event_messages]
    messages = await db_crud.userEventMessage_crud.get_messages_by_ids(message_ids)
    return messages


@router.get("/triggered_messages/user/me", response_model=List[MessageModel])
async def get_triggered_messages_by_user_id(user_id: int = Depends(get_current_user_id)):
    user_messages = await db_crud.userEventMessage_crud.get_event_messages_by_user(user_id)
    if not user_messages:
        raise HTTPException(status_code=404, detail="No messages found for this user")

    message_ids = [um.message_id for um in user_messages]
    messages = await db_crud.userEventMessage_crud.get_messages_by_ids(message_ids)
    return messages
