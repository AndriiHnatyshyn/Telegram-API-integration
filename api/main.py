import logging
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from starlette.websockets import WebSocket

from api.routers import botApi, userApi, messageApi, accountApi, chatsApi, proxyApi, userEventApi, filtersApi, \
    notificationApi, securityApi, scrapeForwardApi
from bot.main import bot
from db.models.accounts import AccountCRUD


logging.getLogger("telethon").setLevel(logging.WARNING)
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except KeyError:
            level = record.levelno

        if level == "DEBUG":
            return

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0)
logging.getLogger("uvicorn").handlers = [InterceptHandler()]
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    if request.scope["type"] == "http":
        # Handle HTTP requests
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"Completed request: {request.method} {request.url} in {process_time:.2f} "
            f"seconds with status code {response.status_code}"
        )
        return response
    elif request.scope["type"] == "websocket":
        # Log WebSocket connections
        logger.info(f"WebSocket connection started: {request.url}")
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"WebSocket connection closed: {request.url} in {process_time:.2f} seconds")
        return response


app.include_router(botApi.router, tags=["Bot"], prefix='/api')
app.include_router(userApi.router, tags=["User"], prefix='/api')
app.include_router(messageApi.router, tags=["Message"], prefix='/api')
app.include_router(accountApi.router, tags=["Account"], prefix='/api')
app.include_router(chatsApi.router, tags=["Chats"], prefix='/api')
app.include_router(proxyApi.router, tags=["Proxy"], prefix='/api')
app.include_router(userEventApi.router, tags=["UserEvent"], prefix='/api')
app.include_router(filtersApi.router, tags=["Filters"], prefix='/api')
app.include_router(notificationApi.router, tags=["Notification"], prefix='/api')
app.include_router(securityApi.router, tags=["Security"], prefix='/api')
app.include_router(scrapeForwardApi.router, tags=["ScrapeForwardMode"], prefix='/api')


async def start_active_accounts():
    account_crud = AccountCRUD()
    accounts = await account_crud.get_all_accounts()
    for account in accounts:
        if account.active:
            await bot.start_monitoring_for_session(account.id)


app.on_event("startup")(start_active_accounts)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Noice Filter Documentation",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["paths"]["/ws/new_messages"] = {
        "get": {
            "summary": "WebSocket endpoint to receive new messages in real-time",
            "description": """
               **Commands:**
               - `reset_filters`: Resets the filters to default values.

               **Filters:**
               - `username`: Filter messages by username.
               - `chat_title`: Filter messages by chat title.
               - `content`: Filter messages by content.
               - `startswith`: Filter messages that start with a specific string.

               **Message Format:**
               ```json
               {
                   "command": "reset_filters" | null,
                   "username": "list" | null,
                   "chat_title": "list" | null,
                   "content": "list" | null,
                   "startswith": "list" | null
               }
               ```

               **Response Format:**
               ```json
               [
                   {
                       "id": "integer",
                       "text": "string",
                       "created_at": "datetime",
                       "chat_id": "integer",
                       "chat_title": "string",
                       "account_id": "integer",
                       "sender_user_id": "integer",
                       "sender_username": "string"
                   }
               ]
               ```

               **Response:**
               - JSON formatted list of new messages based on the current filters.
               """,
            "responses": {
                "101": {
                    "description": "Switching Protocols - WebSocket connection established",
                },
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "example": [
                                {
                                    "id": "integer",
                                    "text": "string",
                                    "created_at": "datetime",
                                    "chat_id": "integer",
                                    "chat_title": "string",
                                    "account_id": "integer",
                                    "sender_user_id": "integer",
                                    "sender_username": "string"
                                }
                            ]
                        }
                    }
                },
            },
        }
    }
    openapi_schema['paths']["/ws/notifications"] = {
        "get": {
            "summary": "WebSocket endpoint to receive real-time notifications",
            "description": """
               **Functionality:**
               - This WebSocket endpoint allows clients to receive notifications in real-time as they are created or updated in the system.
               - Clients can connect to this endpoint to get a stream of new notifications without having to continuously poll the server.

               **Flow:**
               - Once the connection is established, the server will begin sending any new notifications related to the connected user.
               - The server filters out notifications that have already been sent, ensuring only new, unread notifications are transmitted through the WebSocket connection.
               - Notifications are sent as soon as they are created or updated, ensuring the client always has the most current information.

               **Message Format:**
               - No specific message format is required to be sent by the client; the server automatically sends notifications as they become available.

               **Response Format:**
               - Notifications are sent as a JSON array, with each notification containing the following fields:
                   ```json
                   [
                       {
                           "id": "integer",          // Notification ID
                           "user_id": "integer",     // User ID associated with the notification
                           "event_id": "integer",    // Optional Event ID associated with the notification
                           "text": "string",         // Content of the notification
                           "read": "boolean"         // Whether the notification has been read
                       }
                   ]
                   ```

               **Response:**
               - A JSON array of notification objects is sent whenever new notifications are available.
               - The server continues to send new notifications as long as the WebSocket connection remains open.
               """,
            "responses": {
                "101": {
                    "description": "Switching Protocols - WebSocket connection established",
                },
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "example": [
                                {
                                    "id": 1,
                                    "user_id": 123,
                                    "event_id": 456,
                                    "text": "New message received",
                                    "read": False
                                }
                            ]
                        }
                    }
                },
            },
        }
    }
    openapi_schema["security"] = [{"OAuth2PasswordBearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# app.openapi = custom_openapi


def run_app():
    uvicorn.run(app, host="0.0.0.0", port=8001, access_log=False)
