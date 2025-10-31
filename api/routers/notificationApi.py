import asyncio
import json
from fastapi import APIRouter, HTTPException, status, Path, Depends
from loguru import logger
from typing import List
from starlette.websockets import WebSocket, WebSocketDisconnect
from api.security import get_current_user_id, get_user_id_from_token
from db.facade import DB
from db.models.notification import NotificationModel, MarkAsReadModel, CreateNotificationModel


router = APIRouter()
db_crud = DB()


@router.post("/notifications/", response_model=NotificationModel, status_code=status.HTTP_201_CREATED)
async def create_notification(notification: CreateNotificationModel):
    new_notification = await db_crud.notification_crud.create(**notification.model_dump())
    return new_notification


@router.get("/notifications/{notification_id}", response_model=NotificationModel)
async def read_notification(notification_id: int = Path(description="The ID of the notification to read")):
    notification = await db_crud.notification_crud.read(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.put("/notifications/{notification_id}", response_model=NotificationModel)
async def update_notification(notification_id: int, notification: CreateNotificationModel):
    updated_notification = await db_crud.notification_crud.update(notification_id, **notification.model_dump())
    if not updated_notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return updated_notification


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notification_id: int):
    await db_crud.notification_crud.delete(notification_id)
    return {"detail": "Notification deleted"}


@router.delete("/notifications_bulk/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notification_ids: list):
    await db_crud.notification_crud.delete_bulk(notification_ids)
    return {"detail": "Notification deleted"}


@router.get("/notifications/user/me", response_model=List[NotificationModel])
async def get_notifications_by_user(user_id: int = Depends(get_current_user_id)):
    notifications = await db_crud.notification_crud.get_all_by_user_id(user_id)
    return notifications


@router.get("/notifications/user/me/grouped", response_model=dict)
async def get_grouped_notifications_by_user(user_id: int = Depends(get_current_user_id)):
    grouped_notifications = await db_crud.notification_crud.get_grouped_notifications_by_user_id(user_id)
    return grouped_notifications


@router.get("/notifications/user/me/grouped_by_events", response_model=dict)
async def get_grouped_notifications_by_events(user_id: int = Depends(get_current_user_id)):
    grouped_notifications = await db_crud.notification_crud.get_grouped_notifications_by_event_id(user_id)
    return grouped_notifications


@router.post("/notifications/user/me/mark_as_read", status_code=status.HTTP_200_OK)
async def mark_notifications_as_read(notifications: MarkAsReadModel, user_id: int = Depends(get_current_user_id)):
    notifications_to_mark = await db_crud.notification_crud.get_all_by_user_id(user_id)
    notifications_dict = {notification.id: notification for notification in notifications_to_mark}

    for notification_id in notifications.notification_ids:
        if notification_id in notifications_dict:
            await db_crud.notification_crud.update(notification_id, read=True)
        else:
            raise HTTPException(status_code=404,
                                detail=f"Notification with ID {notification_id} not found for user {user_id}")

    return {"detail": "Notifications marked as read"}


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
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

    sent_notification_ids = set()

    try:
        while True:
            notifications = await db_crud.notification_crud.get_all_by_user_id(user_id)
            unread_notifications = [notif for notif in notifications if not notif.read]

            new_notifications = [notif for notif in unread_notifications if notif.id not in sent_notification_ids]

            if new_notifications:
                await websocket.send_json([notif.to_dict() for notif in new_notifications])
                sent_notification_ids.update(notif.id for notif in new_notifications)

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        print(f"WebSocket connection closed for user {user_id}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await websocket.close()
