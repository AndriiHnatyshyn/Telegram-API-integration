from enum import Enum

from fastapi import HTTPException, status, APIRouter, UploadFile, File, Depends
from typing import List
from api.security import get_current_user_id, require_role
from api.utils import Country_list
from db.facade import DB
from db.models.proxy import ProxyModel, ProxyResponseModel


router = APIRouter()
db_crud = DB()
CountryEnum = Enum('CountryEnum', {country: country for country in Country_list})


@router.post("/proxies/", response_model=ProxyResponseModel, status_code=status.HTTP_201_CREATED)
@require_role('admin')
async def create_proxy(proxy: ProxyModel, user_id: int = Depends(get_current_user_id)):
    try:
        proxy_data = {'ip': proxy.ip,
                      'port': proxy.port,
                      'type': proxy.type,
                      'login': proxy.login,
                      'password': proxy.password,
                      'location': proxy.location}

        new_proxy = await db_crud.proxy_crud.create(**proxy_data)
        return new_proxy
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/proxies/", response_model=List[ProxyModel])
@require_role('admin')
async def get_all_proxies(user_id: int = Depends(get_current_user_id)):
    try:
        proxies = await db_crud.proxy_crud.get_all()
        return proxies
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/proxies/{proxy_id}", response_model=ProxyModel)
@require_role('admin')
async def get_proxy(proxy_id: int, user_id: int = Depends(get_current_user_id)):
    try:
        proxy = await db_crud.proxy_crud.read(proxy_id)
        if proxy is None:
            raise HTTPException(status_code=404, detail="Proxy not found")
        return proxy
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/proxies/{proxy_id}", response_model=ProxyModel)
@require_role('admin')
async def update_proxy(proxy_id: int, proxy_data: dict, user_id: int = Depends(get_current_user_id)):
    try:
        updated_proxy = await db_crud.proxy_crud.update(proxy_id, **proxy_data)
        if updated_proxy is None:
            raise HTTPException(status_code=404, detail="Proxy not found")
        return updated_proxy
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/proxies/{proxy_id}", response_model=ProxyModel)
@require_role('admin')
async def delete_proxy(proxy_id: int, user_id: int = Depends(get_current_user_id)):
    try:
        proxy_to_delete = await DB.proxy_crud.read(id=proxy_id)
        if proxy_to_delete is None:
            raise HTTPException(status_code=404, detail="Proxy not found")
        else:
            await DB.proxy_crud.delete(id=proxy_id)
            return {"message": f"Proxy id {proxy_id} is deleted"}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/proxies/all/available", response_model=List[ProxyModel])
@require_role('admin')
async def get_available_proxies(user_id: int = Depends(get_current_user_id)):
    try:
        available_proxies = await db_crud.proxy_crud.get_all_available()
        return available_proxies
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/proxies/upload", status_code=status.HTTP_201_CREATED)
@require_role('admin')
async def upload_proxies(prx_type: str, location: CountryEnum, file: UploadFile = File(...),
                         user_id: int = Depends(get_current_user_id)):
    try:
        contents = await file.read()
        proxies = contents.decode().splitlines()
        created_proxies = []

        for proxy_line in proxies:
            proxy_data = proxy_line.split(':')
            ip = proxy_data[0]
            port = proxy_data[1]
            login = proxy_data[2]
            password = proxy_data[3]

            clear_proxy_data = {
                "type": prx_type,
                "login": login,
                "password": password,
                "ip": ip,
                "port": int(port),
                "location": location
            }

            new_proxy = await db_crud.proxy_crud.create(**clear_proxy_data)
            created_proxies.append(new_proxy)

        return created_proxies
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        await file.close()
