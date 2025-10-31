from typing import List
from loguru import logger
from fastapi import APIRouter, HTTPException, status, Depends

from api.security import get_current_user_id, require_role
from db.facade import DB
from db.models.filters import UserFilterModel


router = APIRouter()
db_crud = DB()


@router.post("/filters/", response_model=UserFilterModel | dict, status_code=status.HTTP_201_CREATED)
async def create_user_filter(user_filter: dict, user_id: int = Depends(get_current_user_id)):
    logger.warning(user_filter)

    new_event = await db_crud.userFilter_crud.create(user_filter, user_id)
    return new_event


@router.get("/filters/{filter_id}", response_model=UserFilterModel)
async def read_user_filter(filter_id: int):
    filter = await db_crud.userFilter_crud.read(filter_id)
    if not filter:
        raise HTTPException(status_code=404, detail="User filter not found")
    return filter


@router.put("/filters/{filter_id}", response_model=UserFilterModel)
async def update_user_filter(filter_id: int, user_filter: UserFilterModel, user_id: int = Depends(get_current_user_id)):
    updated_filter = await db_crud.userFilter_crud.update(filter_id, **user_filter.model_dump())
    if not updated_filter:
        raise HTTPException(status_code=404, detail="User filter not found")
    return updated_filter


@router.delete("/filters/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_filter(filter_id: int, user_id: int = Depends(get_current_user_id)):
    await db_crud.userFilter_crud.delete(filter_id)
    return {"detail": "User filter deleted"}


@router.get("/filters_all/", response_model=List[UserFilterModel])
@require_role('admin')
async def get_all_user_filters(user_id: int = Depends(get_current_user_id)):
    filters = await db_crud.userFilter_crud.get_all()
    return filters


@router.get("/filters/user/me", response_model=List[dict])
async def get_user_filters_by_user_id(user_id: int = Depends(get_current_user_id)):
    filters = await db_crud.userFilter_crud.get_all_by_user_id(user_id)
    if not filters:
        raise HTTPException(status_code=404, detail="No filters found for this user")
    filters = [filter.get_data() for filter in filters]
    return filters
