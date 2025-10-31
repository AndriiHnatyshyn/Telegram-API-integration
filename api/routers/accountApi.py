from typing import List, Optional

import loguru
from fastapi import APIRouter, HTTPException, status, Depends

from api.security import get_current_user_id, require_role
from db.facade import DB
from bot.main import bot
from db.models.accounts import AccountModel, AccountResponseModel


router = APIRouter()
db_crud = DB()


@router.post("/accounts/", response_model=AccountResponseModel, status_code=status.HTTP_201_CREATED)
async def create_account(account: AccountModel):
    new_account = await db_crud.account_crud.create(**account.model_dump())
    return new_account


@router.get("/accounts/{phone}", response_model=AccountResponseModel)
async def read_account(phone: str):
    account = await db_crud.account_crud.read(phone)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/accounts/{phone}", response_model=AccountResponseModel)
async def update_account(phone: str, username: Optional[str] = None, created_by: Optional[int] = None):
    updated_data = {}
    if username or created_by:
        if username:
            updated_data.update({'username': username})

        if created_by:
            updated_data.update({'created_by': created_by})
        updated_account = await db_crud.account_crud.update(phone, **updated_data)
        if not updated_account:
            raise HTTPException(status_code=404, detail="Account not found")
        return updated_account
    raise HTTPException(status_code=404, detail="No data provided")


@router.delete("/accounts/{phone}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(phone: str, user_id: int = Depends(get_current_user_id)):
    await db_crud.account_crud.delete_on_cascade(phone)
    return {"detail": "Account deleted"}


@router.get("/accounts/", response_model=List[AccountResponseModel])
@require_role("admin")
async def get_all(user_id: int = Depends(get_current_user_id)):
    account = await db_crud.account_crud.get_all_accounts()
    if not account:
        raise HTTPException(status_code=404, detail="Accounts not found")
    return account


@router.get("/accounts_all/user/me", response_model=List[AccountResponseModel])
async def get_all_by_user_id(user_id: int = Depends(get_current_user_id)):
    account = await db_crud.account_crud.get_accounts_by_user_id(user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/account_set_active/{phone}/{choose}")
async def set_active(phone: str, choose: bool, user_id: int = Depends(get_current_user_id)):
    res = await db_crud.account_crud.set_active(phone, choose)
    loguru.logger.info(choose)
    if choose:
        await bot.start_monitoring_for_session(phone)
    else:
        await bot.stop_monitoring_for_session(phone)
    return res
