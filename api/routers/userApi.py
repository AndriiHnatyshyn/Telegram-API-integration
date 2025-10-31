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
FRONT_URL = os.getenv("FRONT_URL")
ACCESS_TOKEN_EXPIRE_MINUTES = 180
REFRESH_TOKEN_EXPIRE_DAYS = 7


@router.get("/users/me",
            summary="A protected route",
            description="Requires an Authorization header with a valid token",
            response_model=UserResponseModel)
async def read_user(user_id: int = Depends(get_current_user_id)):
    user = await db_crud.user_crud.read(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/all/", response_model=List[UserResponseModel])
async def get_all_users():
    users = await DB.user_crud.get_all()

    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    return users


@router.get("/user_by_name/{username}", response_model=UserResponseModel)
async def read_username(username: str = Path(description="The username of the user to read")):
    user = await db_crud.user_crud.get_user_id_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.put("/users/me", summary="A protected route",
            description="Requires an Authorization header with a valid token",
            response_model=UserResponseModel)
async def update_user(user: dict, user_id: int = Depends(get_current_user_id)):
    updated_user = await DB.user_crud.update(user_id, **user)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int = Depends(get_current_user_id)):
    await DB.user_crud.delete(id=user_id)
    return {"detail": "User deleted"}


@router.post("/login/")
async def login(login_request: LoginRequest):
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if re.match(email_pattern, login_request.username):
        user = await db_crud.user_crud.get_user_by_email(email=login_request.username)
    else:
        user = await db_crud.user_crud.get_user_by_username(username=login_request.username)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    stored_password = user.password.encode('utf-8') if isinstance(user.password, str) else user.password

    if not bcrypt.checkpw(login_request.password.encode('utf-8'), stored_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": str(user.id)},
                                       expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_access_token(data={"sub": str(user.id)},
                                        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponseModel.model_validate(user.to_dict())
    }


@router.post('/change_password/', response_model=UserResponseModel)
async def change_password(data: ChangePassword, user_id: int = Depends(get_current_user_id)):
    user = await db_crud.user_crud.read(id=user_id)

    if not user or not bcrypt.checkpw(data.old_password.encode('utf-8'), user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    new_hashed_password = bcrypt.hashpw(data.new_password.encode('utf-8'), bcrypt.gensalt())
    updated = await db_crud.user_crud.update(id=user_id, password=new_hashed_password.decode('utf-8'))
    return updated


@router.post("/register/", response_model=UserRegistrationResponseModel)
async def register(user: UserModel):
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern=email_pattern, string=user.email):
        raise HTTPException(status_code=400, detail='Email is not valid')

    existing_user = await db_crud.user_crud.get_user_by_email(email=user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    characters = string.ascii_letters + string.digits
    verification_token = ''.join(random.choices(characters, k=10))

    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

    user_data = {
        'username': user.username,
        'password': hashed_password.decode('utf-8'),
        'email': user.email,
        'verification_token': verification_token
    }

    new_user = await db_crud.user_crud.create(**user_data)

    verification_link = f"{FRONT_URL}/verify_email?user_id={new_user.id}&token={verification_token}"
    await send_verification_email(new_user.email, verification_link)
    return new_user


@router.post("/retry_email")
async def retry_email_verification(user_id: int):
    user = await DB.user_crud.get_user_by_id(user_id)
    verification_link = f"{FRONT_URL}/verify_email?user_id={user.id}&token={user.verification_token}"
    await send_verification_email(user.email, verification_link)


@router.post("/verify_email")
async def verify_email(user_id: int, token: str):
    user = await DB.user_crud.read(id=user_id)
    if user and user.verification_token == token:
        await DB.user_crud.update(id=user_id, is_verified=True)
        access_token = create_access_token(data={"sub": str(user.id)},
                                           expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        refresh_token = create_access_token(data={"sub": str(user.id)},
                                            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
        return {
            "msg": "Email verified successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid token or user ID")


@router.get("/users/get_telegram_link/me")
async def telegram_link(user_id: int = Depends(get_current_user_id)):
    user = await DB.user_crud.read(id=user_id)
    tg_link = f't.me/{BOT_USERNAME}?start={user.verification_token}_{user.id}'
    return tg_link


@router.post('/users/set_telegram_notifications/me/{status}', response_model=UserResponseModel)
async def set_telegram_notifications(status: bool = False, user_id: int = Depends(get_current_user_id)):
    user = await DB.user_crud.update(id=user_id, tg_notifications=status)
    return user
