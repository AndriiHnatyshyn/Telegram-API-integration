import os
import re
from datetime import timedelta
from typing import List
import bcrypt
from dotenv import load_dotenv
from api.security import create_access_token, get_current_user_id
from utils.functions import send_verification_email
from fastapi import APIRouter, HTTPException, status, Path, Depends
from db.facade import DB
from db.models.users import UserResponseModel, UserModel, LoginRequest, UserRegistrationResponseModel, ChangePassword
import random
import string


router = APIRouter()
db_crud = DB()
load_dotenv()
BOT_USERNAME = os.getenv("BOT_USERNAME")
SECRET_KEY = os.getenv("SECRET_KEY", "blablablapesparton")
ACCESS_TOKEN_EXPIRE_MINUTES = 180
REFRESH_TOKEN_EXPIRE_DAYS = 7


@router.put("/scrape_forward/update_mode", summary="A protected route",
            description="Requires an Authorization header with a valid token",
            response_model=UserResponseModel)
async def update_scrape_forward_mode(scrape_forward_mode: bool, user_id: int = Depends(get_current_user_id)):
    update_data = {"scrape_forward_mode": scrape_forward_mode}
    updated_user = await db_crud.user_crud.update(user_id, **update_data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user


@router.put("/scrape_forward/update_target_chats", summary="A protected route",
            description="Requires an Authorization header with a valid token",
            response_model=UserResponseModel)
async def update_scrape_forward_mode(title: str | list[str] | None, user_id: int = Depends(get_current_user_id)):
    titles = title
    if isinstance(title, str):
        titles = [title]

    chat_ids = []
    for chat_title in titles:
        chat = await db_crud.chat_crud.get_by_title(title=chat_title)
        if chat:
            chat_ids.append(str(chat.id))

    clear_chat_ids = ",".join(chat_ids)
    update_data = {"target_chats": clear_chat_ids}
    updated_user = await db_crud.user_crud.update(user_id, **update_data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user



