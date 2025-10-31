from db.models.accounts import AccountCRUD
from db.models.chats import ChatCRUD
from db.models.message import MessageCRUD
from db.models.proxy import ProxyCRUD
from db.models.user_events import UserEventsCRUD
from db.models.users import UserCRUD
from db.models.user_event_messages import UserEventMessageCRUD
from db.models.filters import UserFiltersCRUD
from db.models.notification import NotificationCRUD


class DB:
    user_crud = UserCRUD()
    account_crud = AccountCRUD()
    chat_crud = ChatCRUD()
    message_crud = MessageCRUD()
    proxy_crud = ProxyCRUD()
    userEvent_crud = UserEventsCRUD()
    userFilter_crud = UserFiltersCRUD()
    userEventMessage_crud = UserEventMessageCRUD()
    notification_crud = NotificationCRUD()
