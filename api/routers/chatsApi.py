from fastapi import HTTPException, status, APIRouter, Depends
from typing import List

from api.security import get_current_user_id, require_role
from db.facade import DB
from db.models.chats import ChatCreateUpdateRequest, ChatModel

router = APIRouter()
# Instance of the CRUD class for chats
db_crud = DB()


@router.post("/chats/", response_model=ChatModel, status_code=status.HTTP_201_CREATED)
async def create_chat(chat_data: ChatCreateUpdateRequest):
    try:
        new_chat = await db_crud.chat_crud.create(**chat_data.model_dump())
        return new_chat
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/chats/", response_model=List[ChatModel])
@require_role('admin')
async def get_all_chats(user_id: int = Depends(get_current_user_id)):
    try:
        chats = await db_crud.chat_crud.get_all()
        return chats
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/chats/{chat_id}", response_model=ChatModel)
async def get_chat(chat_id: int):
    try:
        chat = await db_crud.chat_crud.read(chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chat
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/chats/{chat_id}", response_model=ChatModel)
async def update_chat(chat_id: int, chat_data: ChatCreateUpdateRequest):
    try:
        updated_chat = await db_crud.chat_crud.update(chat_id, **chat_data.model_dump())
        if updated_chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return updated_chat
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/chats/{chat_id}", response_model=ChatModel)
async def delete_chat(chat_id: int):
    try:
        deleted_chat = await db_crud.chat_crud.delete(chat_id)
        if deleted_chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return deleted_chat
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/search_chats/")
async def search_chats(q: str, user_id: int = Depends(get_current_user_id)):
    if len(q) < 3:
        return []
    try:
        accounts = await db_crud.account_crud.get_accounts_by_user_id(user_id)
        account_ids = [account.id for account in accounts]
        chats = await db_crud.chat_crud.search_chats_by_title(title_query=q, account_ids=account_ids)
        return chats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chats_all/user/me", response_model=List[ChatModel])
async def chats_all_by_user(user_id: int = Depends(get_current_user_id)):
    accounts = await db_crud.account_crud.get_accounts_by_user_id(user_id)
    account_ids = [account.id for account in accounts]
    chats = await db_crud.chat_crud.get_all_by_accounts(account_ids)
    return chats


@router.get("/chats_all/account/{account_id}", response_model=List[ChatModel])
async def chats_all_by_account(account_id: str):
    chats = await db_crud.chat_crud.get_chats_for_account(account_id)
    return chats
