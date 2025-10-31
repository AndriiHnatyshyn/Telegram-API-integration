import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict
from loguru import logger
from pydantic import BaseModel
from api.security import get_current_user_id, get_user_id_from_token, require_role
from bot.main import bot
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from db.facade import DB

router = APIRouter()
db_crud = DB()


@router.post("/bot/get_code/{phone}")
async def get_code(phone: str):
    status = await bot.create_user_session(phone)
    if status != "Code sent":
        account = await db_crud.account_crud.read(phone)
        if not account:
            session_file_path = f'bot/sessions/{phone}.session'
            os.remove(session_file_path)
        raise HTTPException(status_code=403, detail=f"{status}")
    return status


@router.post("/bot/pass_code/{phone}/{code}/{username}")
async def pass_code(phone: str, code: str, username: str):
    account = await bot.pass_code(phone=phone, code=code, account=username)
    return account


@router.post("/bot/password/")
async def pass_password(data: dict):
    phone = data['phone']
    password = data['password']
    username = data['username']
    account = await bot.pass_code(phone=phone, account=username, password=password)
    return account


class FiltersModel(BaseModel):
    filters: Dict


class ChatsModel(BaseModel):
    chats: List[int]


@router.post("/bot/get_deleted/")
async def get_deleted(start_timestamp: int = Query(..., description="Start timestamp"),
                      end_timestamp: int = Query(..., description="End timestamp"),
                      chats: ChatsModel = Depends(),
                      filters: FiltersModel = Depends(),
                      user_id: int = Depends(get_current_user_id)):
    account_ids = await db_crud.account_crud.get_accounts_by_user_id(user_id=user_id)
    account_id = account_ids[0]
    try:
        deleted_messages = await bot.check_deleted_in_chat(start_time=start_timestamp,
                                                           end_time=end_timestamp,
                                                           chats=chats.chats,
                                                           account_id=account_id.id,
                                                           filters=filters.filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "deleted_messages": [{chat_id: [message for message in messages] for chat_id, messages in
                              deleted_messages["deleted"].items()}],
        "modified_messages": {chat_id: [message for message in messages] for chat_id, messages in
                              deleted_messages["modified"].items()}
    }


@router.delete("/bot/remove_session/{session_name}")
async def remove_session(session_name: str):
    result = await bot.remove_session(session_name)
    if result:
        return {"message": f"Session {session_name} removed successfully."}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/bot/create_session/{session_name}")
@require_role("admin")
async def create_session(session_name: str, user_id: int = Depends(get_current_user_id)):
    await bot.create_session(session_name)
    return {"message": f"Session {session_name} created and monitoring started."}


@router.get("/bot/list_sessions")
@require_role("admin")
async def list_sessions(user_id: int = Depends(get_current_user_id)):
    sessions = bot.list_sessions()
    return sessions


@router.get("/bot/fetch_chats/{session_name}", response_model=str)
async def fetch_chats(session_name: str):
    try:
        chats_json = await bot.fetch_all_chats_to_json(session_name)
        return chats_json
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bot/start_monitoring/{session_name}")
async def start_monitoring(session_name: str):
    try:
        await bot.start_monitoring_for_session(session_name)
        return {"message": f"Monitoring started for {session_name}"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/bot/stop_monitoring/{session_name}")
async def stop_monitoring(session_name: str):
    try:
        await bot.stop_monitoring_for_session(session_name)
        return {"message": f"Monitoring stopped for {session_name}"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.websocket("/ws/new_messages")
async def websocket_new_messages(websocket: WebSocket):
    await websocket.accept()

    try:
        data = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        try:
            message = json.loads(data)
            if "token" not in message:
                await websocket.send_text(json.dumps({"error": "Token missing"}))
                await websocket.close(code=4002, reason="Token missing")
                return

            user_id = await get_user_id_from_token(token=message["token"])
        except json.JSONDecodeError:
            await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
            await websocket.close(code=4003, reason="Invalid JSON")
            return
        except Exception as e:
            logger.error(f"Error retrieving user ID: {e}")
            await websocket.send_text(json.dumps({"error": "Authentication failed"}))
            await websocket.close(code=4005, reason="Authentication failed")
            return

    except asyncio.TimeoutError:
        logger.error("Token not received in time")
        await websocket.close(code=4004, reason="Token not received in time")
        return

    user_accounts = await db_crud.account_crud.get_accounts_by_user_id(user_id)
    if not user_accounts:
        logger.error(f"No accounts found for user_id {user_id}")
        await websocket.close(code=4001, reason="No accounts found for user_id")
        return

    account_ids = [account.id for account in user_accounts]
    last_sent_time = datetime.now().timestamp()
    default_filters = {"username": None,
                       "chat_title": None,
                       "content": None,
                       "startswith": None}

    filters = default_filters.copy()

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                try:
                    message = json.loads(data)
                    if message.get("command") == "reset_filters":
                        filters = default_filters.copy()
                        await websocket.send_text(json.dumps({"message": "Filters reset."}))
                        logger.info(f'Filters reset.')
                    else:
                        filters.update({k: v for k, v in message.items() if v is not None})
                        logger.info(f'Set new filters: {filters}')
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
            except asyncio.TimeoutError:
                pass

            new_messages = await db_crud.message_crud.get_new_messages_async(filters, last_sent_time, account_ids)
            if new_messages:
                msgs = []
                for message in new_messages:
                    msg = message.to_dict()
                    msg.update({"chat": message.chat.to_dict()})
                    msgs.append(msg)
                await websocket.send_text(json.dumps(msgs, default=str))
                last_sent_time = max(message.created_at for message in new_messages)

    except WebSocketDisconnect:
        logger.error("WebSocket disconnected")
    except asyncio.TimeoutError:
        logger.error("WebSocket timeout")
        await websocket.close()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await websocket.close()
