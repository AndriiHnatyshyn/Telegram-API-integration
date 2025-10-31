import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from api.security import get_current_user_id, require_role
from db.facade import DB
from db.models.message import MessageModel, MessageCreateModel, FilterModel


router = APIRouter()
db_crud = DB()


@router.post("/messages/", response_model=MessageModel, status_code=status.HTTP_201_CREATED)
async def create_message(message: MessageCreateModel):
    new_message = await db_crud.message_crud.create(**message.model_dump())
    return new_message


@router.get("/messages/{message_id}", response_model=MessageModel)
async def read_message(message_id: int):
    message = await db_crud.message_crud.read(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@router.put("/messages/{message_id}", response_model=MessageModel)
async def update_message(message_id: int, message: MessageCreateModel):
    updated_message = await db_crud.message_crud.update(message_id, **message.model_dump())
    if not updated_message:
        raise HTTPException(status_code=404, detail="Message not found")
    return updated_message


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: int):
    await db_crud.message_crud.delete(message_id)
    return {"detail": "Message deleted"}


@router.get("/messages/")
@require_role('admin')
async def read_messages(
        username: Optional[str] = None,
        chat_id: Optional[int] = None,
        start_time: Optional[datetime] = Query(None),
        end_time: Optional[datetime] = Query(None),
        user_id: int = Depends(get_current_user_id)):

    if start_time is None:
        start_time = datetime.now() - timedelta(hours=24)
        
    messages = await db_crud.message_crud.get_filtered_messages(username=username, chat_id=chat_id,
                                                                start_time=start_time,
                                                                end_time=end_time)
    return messages


@router.post("/messages/history/")
async def get_history_messages(unix_timestamp: Optional[int],
                               limit: Optional[int],
                               filters: FilterModel,
                               user_id: int = Depends(get_current_user_id)):
    try:
        accounts = await db_crud.account_crud.get_accounts_by_user_id(user_id)
        accounts_ids = [account.id for account in accounts]
        filters = filters.to_dict()
        history_messages = await DB.message_crud.get_history_messages(filters=filters,
                                                                      account_ids=accounts_ids,
                                                                      limit=limit,
                                                                      timestamp=unix_timestamp)

        return history_messages

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count_messages/")
@require_role("admin")
async def count_messages(user_id: int = Depends(get_current_user_id)):
    count = await db_crud.message_crud.count_messages()
    return {"message_count": count}


def remove_file(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


@router.get("/get_unique_usernames/")
@require_role('admin')
async def get_unique_usernames(user_id: int = Depends(get_current_user_id)):
    try:
        # Fetch unique usernames
        unique_usernames = await db_crud.message_crud.get_unique_usernames()

        if not unique_usernames:
            raise HTTPException(status_code=404, detail="No unique usernames found")

        # Create a temporary file to store the usernames
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as tmp_file:
            file_path = tmp_file.name
            for username in unique_usernames:
                tmp_file.write(f"{username}\n")

        # Return the file as a response and schedule its removal
        return FileResponse(
            file_path,
            media_type='text/plain',
            filename='unique_usernames.txt',
            background=BackgroundTask(remove_file, file_path)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_usernames_by_user/")
async def get_unique_usernames_by_user(q: str, user_id: int = Depends(get_current_user_id)):
    if len(q) < 3:
        return []

    try:
        # Fetch unique usernames
        accounts = await db_crud.account_crud.get_accounts_by_user_id(user_id)
        accounts_id = [account.id for account in accounts]
        unique_usernames = await db_crud.message_crud.get_unique_usernames_by_user_and_query(account_ids=accounts_id,
                                                                                             q=q)

        if not unique_usernames:
            raise HTTPException(status_code=404, detail="No unique usernames found")

        return unique_usernames

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
