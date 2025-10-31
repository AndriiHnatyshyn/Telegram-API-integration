import asyncio
import json
import os
import pathlib
from datetime import datetime, timezone

from aiogram.exceptions import TelegramForbiddenError

from api.utils import Country_list
from db.models.chats import ChatModel
from db.models.accounts import AccountModel
from telethon import TelegramClient, events, errors
from loguru import logger
from telethon.tl.types import Chat, Channel, User
from db.facade import DB
from telegram.tgbot import TGbot
from utils.functions import get_country_from_phone_number

db_crud = DB()


class TelegramChatHistory:
    def __init__(self, base_dir='bot/sessions'):
        self.base_dir = pathlib.Path(base_dir).resolve()
        self.api_id = 2040
        self.api_hash = 'b18441a1ff607e10a989891a5462e627'
        self.sessions = {}
        self.pending_sessions = {}
        self.monitoring_tasks = {}
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True)

    def find_session_files(self):
        return [f.stem for f in self.base_dir.glob('*.session')]

    async def create_user_session(self, phone):
        if phone in self.sessions.keys() or phone in self.pending_sessions.keys():
            logger.error("Account already exists")
            return 'Account already exists'
        try:
            location = await get_country_from_phone_number(phone)
            if location not in Country_list:
                location = 'Germany'
            proxy = await db_crud.proxy_crud.get_available_by_location(location)
            if proxy:
                proxy = proxy[0]
                client = TelegramClient(
                    session="bot/sessions/" + phone,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    proxy=(
                        proxy.type,
                        proxy.ip,
                        proxy.port,
                        True,
                        proxy.login,
                        proxy.password
                    ),

                )
                await client.connect()
                if not await client.is_user_authorized():
                    phone_code = await client.send_code_request(phone)
                    phone_code_hash = phone_code.phone_code_hash
                    self.pending_sessions[phone] = [client, phone_code_hash, proxy.id]
                    logger.info("Code sent to " + phone)
                    return 'Code sent'
                else:
                    await client.disconnect()
            else:
                client = TelegramClient(
                    session="bot/sessions/" + phone,
                    api_id=self.api_id,
                    api_hash=self.api_hash
                )
                await client.connect()
                if not await client.is_user_authorized():
                    phone_code = await client.send_code_request(phone)
                    phone_code_hash = phone_code.phone_code_hash
                    self.pending_sessions[phone] = [client, phone_code_hash, None]
                    logger.info("Code sent to " + phone)
                    return 'Code sent'
                else:
                    await client.disconnect()
        except errors.PhoneNumberBannedError as e:
            logger.error(f"got: {e.message}")
            return 'PhoneNumberBanned'

    async def pass_code(self, phone, code=None, account=None, password=None):

        client, phone_cash, proxy_id = self.pending_sessions.get(phone)
        if client:
            try:
                if password is not None:
                    await client.sign_in(phone=phone,
                                         password=password)
                else:
                    await client.sign_in(phone,
                                         code=code,
                                         phone_code_hash=phone_cash,
                                         # password=password
                                         )
                me = await client.get_me()
                self.sessions[me.phone] = client
                del self.pending_sessions[phone]
                username = me.username if me.username is not None else me.first_name
                user = await db_crud.user_crud.get_user_id_by_username(account)
                account_data = {"id": me.phone,
                                "username": username,
                                "created_by": user.id}
                new_account = await db_crud.account_crud.create(**account_data)

                if new_account:
                    logger.info(f"Account created in database for {me.phone}")
                    account_id = new_account.id
                    await self.fetch_and_save_chats(client, account_id)

                else:
                    logger.error(f"Failed to create account in database for {me.phone}")

                await self.start_monitoring_for_session(me.phone)
                return new_account
            except errors.SessionPasswordNeededError:
                return "Password"
            except errors.SendCodeUnavailableError:
                return "SendCodeUnavailable"
            except errors.RPCError as e:
                await client.sign_in(phone=phone,
                                     password=password)
                return f"Failed to sign in: {e}"
        else:
            return "No login session found for " + phone

    async def create_session(self, session_name):
        if session_name in self.sessions:
            logger.info(f"Session {session_name} already exists.")

        client = TelegramClient('bot/sessions/' + session_name, self.api_id, self.api_hash)
        await client.connect()
        me = await client.get_me()
        self.sessions[session_name] = client

        # Create account in the database

        account_data = AccountModel(
            id=me.phone,
            username=me.username or me.first_name,
            created_by=1
        )
        new_account = await db_crud.account_crud.create(**account_data.model_dump())
        if new_account:
            logger.info(f"Account created in database for {me.phone}")
        else:
            logger.error(f"Failed to create account in database for {me.phone}")

        # Fetch and save chats for the logged session
        await self.fetch_and_save_chats(client, new_account.id)

        # Start monitoring for the new session
        await self.start_monitoring_for_session(session_name)
        logger.info(f"Session {session_name} created and monitoring started.")

    async def start_monitoring_for_session(self, session_name):
        if session_name in self.monitoring_tasks:
            logger.info(f"Monitoring already started for {session_name}.")
            return
        await db_crud.account_crud.set_active(session_name, True)
        await self.get_client_by_session_name(session_name)
        task = asyncio.create_task(self.monitor_messages(session_name))
        self.monitoring_tasks[session_name] = task

        logger.info(f"Monitoring started for {session_name}.")
        return self.monitoring_tasks

    async def get_client_by_session_name(self, session_name: str) -> TelegramClient | None:
        session_file_path = f"bot/sessions/{session_name}"

        os.makedirs(os.path.dirname(session_file_path), exist_ok=True)

        client = self.sessions.get(session_name)

        if client and not client.is_connected():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect the client for {session_name}: {e}")
            finally:
                del self.sessions[session_name]
                client = None

        if not client:
            try:
                account = await db_crud.account_crud.read(session_name)
                proxy = await db_crud.proxy_crud.read(account.proxy_id) if account else None
                client = TelegramClient(
                    session=session_file_path,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    proxy=(proxy.type, proxy.ip, proxy.port, True, proxy.login, proxy.password) if proxy else None
                )
                await client.connect()
                await client.start()

                if await client.is_user_authorized():
                    me = await client.get_me()
                    self.sessions[me.phone] = client
                    return client
            except Exception as e:
                logger.error(f"Error creating or connecting client for {session_name}: {e}")
                if client:
                    await client.disconnect()
                return None
        return client

    async def monitor_messages(self, session_name):
        if session_name not in self.sessions:
            raise Exception(f"Session {session_name} not found.")
        client = self.sessions[session_name]

        try:
            async with (client):
                @client.on(events.NewMessage)
                async def handler(event):
                    try:
                        chat = await event.get_chat()
                        if isinstance(chat, User):
                            chat_id = chat.id
                            chat_name = chat.first_name
                            if hasattr(chat, 'usernames'):
                                try:
                                    chat_username = chat.usernames[0].username if chat.usernames else chat.first_name
                                except KeyError:
                                    chat_username = chat.first_name
                            else:
                                chat_username = chat.username if hasattr(chat, 'username') else chat.first_name
                            chat_type = 'Private chat'
                        elif isinstance(chat, Chat):
                            chat_id = chat.id
                            chat_name = chat.title if hasattr(chat, 'title') else "Unknown"
                            if hasattr(chat, 'usernames'):
                                try:
                                    chat_username = chat.usernames[0].username if chat.usernames else chat.title
                                except KeyError:
                                    chat_username = chat.title
                            else:
                                chat_username = chat.username if hasattr(chat, 'username') else chat.title
                            chat_type = 'Group'
                        elif isinstance(chat, Channel):
                            chat_id = chat.id
                            chat_name = chat.title if hasattr(chat, 'title') else "Unknown"
                            if hasattr(chat, 'usernames'):
                                try:
                                    chat_username = chat.usernames[0].username if chat.usernames else chat.title
                                except KeyError:
                                    chat_username = chat.title
                            else:
                                chat_username = chat.username if hasattr(chat, 'username') else chat.title
                            chat_type = 'Group' if chat.megagroup else 'Channel'
                        else:
                            chat_id = 0
                            chat_name = 'Unknown'
                            chat_username = 'Unknown'
                            chat_type = 'Unknown'

                    except errors.rpcerrorlist.ChannelPrivateError:
                        return

                    existing_chat = await db_crud.chat_crud.read(chat_id)
                    if not existing_chat:
                        chat_model = ChatModel(id=chat_id,
                                               chat_title=chat_name,
                                               chat_username=chat_username,
                                               chat_type=chat_type)
                        await db_crud.chat_crud.create(**chat_model.model_dump())
                        await db_crud.chat_crud.add_account_to_chat(chat_id, session_name)

                    sender = await event.get_sender()
                    if isinstance(sender, User):
                        sender_username = sender.username if sender else sender.first_name
                    else:
                        sender_username = chat_username
                    # try:
                    #     sender_bot = sender.bot
                    # except AttributeError:
                    #     sender_bot = False
                    if sender is not None:
                        message_text = event.text.replace('\n', '') if event.text else ''
                        if message_text:

                            message_data = {
                                "text": message_text,
                                "chat_id": chat_id,
                                "chat_title": chat_name,
                                "account_id": session_name,
                                "sender_user_id": sender.id if sender else None,
                                "sender_username": sender_username,
                                "message_id": event.message.id,
                            }

                            account = await db_crud.account_crud.read(session_name)
                            user_id = account.created_by
                            user = await db_crud.user_crud.read(user_id)
                            if user.scrape_forward_mode:
                                need_to_forward = await self.compare_events_and_message(message_data,
                                                                                        account.created_by,
                                                                                        user_filters=True)

                                if need_to_forward:
                                    user_raw_forward_chats = user.target_chats.split(",")
                                    for target_chat_id in user_raw_forward_chats:
                                        target_chat = await client.get_entity(int(target_chat_id))
                                        await event.forward_to(target_chat)

                            triggered_events = await self.compare_events_and_message(message_data, account.created_by)
                            if triggered_events:
                                await self.send_event_response(triggered_events)
                            await db_crud.message_crud.create(**message_data)

                await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error in monitoring {session_name}: {str(e)}")

    @staticmethod
    async def send_event_response(triggerd_events):
        for event, user_id, match_details, message in triggerd_events:
            user = await db_crud.user_crud.read(user_id)

            detail_message = " | ".join(match_details)
            notification_message = (f"<b>Event Triggered:</b> {detail_message}\n"
                                    f"\n<b>Message:</b>\n"
                                    f"[{message['sender_username']}]: {message['text']}")

            await db_crud.notification_crud.create(user_id=user_id, event_id=event.id, text=notification_message)

            if user and user.tg_id:
                try:
                    await TGbot.send_message(chat_id=user.tg_id, text=notification_message, parse_mode="HTML")
                except TelegramForbiddenError:
                    await db_crud.user_crud.set_notification_status(user_id, False)
                    await db_crud.notification_crud.create(user_id=user_id,
                                                           event_id=event.id,
                                                           text='You have blocked bot for notifications.')

    @staticmethod
    async def compare_events_and_message(message: dict, user_id: int, user_filters: bool = False) -> list:
        filters_events = await db_crud.userEvent_crud.get_all_by_user_id(user_id)
        if user_filters:
            filters_events = await db_crud.userFilter_crud.get_scrape_and_forward_filters(user_id)

        triggered_events = []

        for event in filters_events:
            match_details = []
            event_data = event.get_data()

            if event_data['username'] and any(
                    username == message["sender_username"] for username in event_data['username']):
                match_details.append(f"username: {event_data['username']}")

            if event_data['chat_title'] and any(
                    chat_title == message["chat_title"] for chat_title in event_data['chat_title']):
                match_details.append(f"chat title: {event_data['chat_title']}")

            if event_data['content'] and any(content in message['text'] for content in event_data['content']):
                match_details.append(f"content match: {event_data['content']} in message")

            if event_data['startswith'] and any(
                    message['text'].startswith(start) for start in event_data['startswith']):
                match_details.append(f"message starts with: {event_data['startswith']}")

            if match_details:
                triggered_events.append((event, event_data['user_id'], match_details, message))

        return triggered_events

    @staticmethod
    async def fetch_and_save_chats(client, account_id):
        async for dialog in client.iter_dialogs():
            chat = dialog.entity
            if isinstance(chat, User):
                chat_id = chat.id
                chat_name = chat.first_name
                if hasattr(chat, 'usernames'):
                    try:
                        chat_username = chat.usernames[0].username if chat.usernames else chat.first_name
                    except KeyError:
                        chat_username = chat.first_name
                else:
                    chat_username = chat.username if hasattr(chat, 'username') else chat.first_name
                chat_type = 'Private chat'
            elif isinstance(chat, Chat):
                chat_id = chat.id
                chat_name = chat.title if hasattr(chat, 'title') else "Unknown"
                if hasattr(chat, 'usernames'):
                    try:
                        chat_username = chat.usernames[0].username if chat.usernames else chat.title
                    except KeyError:
                        chat_username = chat.title
                else:
                    chat_username = chat.username if hasattr(chat, 'username') else chat.title
                chat_type = 'Group'
            elif isinstance(chat, Channel):
                chat_id = chat.id
                chat_name = chat.title if hasattr(chat, 'title') else "Unknown"
                if hasattr(chat, 'usernames'):
                    try:
                        chat_username = chat.usernames[0].username if chat.usernames else chat.title
                    except KeyError:
                        chat_username = chat.title
                else:
                    chat_username = chat.username if hasattr(chat, 'username') else chat.title
                chat_type = 'Group' if chat.megagroup else 'Channel'
            else:
                continue
            chat_data = {
                "id": chat_id,
                "chat_title": chat_name,
                'chat_type': chat_type,
                'chat_username': chat_username,

            }
            await db_crud.chat_crud.create(**chat_data)
            await db_crud.chat_crud.add_account_to_chat(chat_id, account_id)

    async def fetch_all_chats_to_json(self, session_name):
        if session_name not in self.sessions:
            logger.error(f"Session {session_name} not found.")
            return None

        client = self.sessions[session_name]
        chat_data = []

        async with client:
            async for dialog in client.iter_dialogs(limit=3):
                entity = dialog.entity

                # Basic chat information
                chat_info = {
                    "id": entity.id,
                    "name": getattr(entity, 'title', None) or getattr(entity, 'first_name', None),
                    "username": getattr(entity, 'username', None),
                    "type": type(entity).__name__,
                    "is_bot": getattr(entity, 'bot', False),
                    "is_verified": getattr(entity, 'verified', False),
                    "is_restricted": getattr(entity, 'restricted', False),
                    "is_scam": getattr(entity, 'scam', False),
                    "is_fake": getattr(entity, 'fake', False),
                    "is_support": getattr(entity, 'support', False),
                    "access_hash": getattr(entity, 'access_hash', None),
                    "created_at": getattr(entity, 'date', None).isoformat() if getattr(entity, 'date', None) else None,
                    "participants_count": getattr(entity, 'participants_count', None),
                    "admins_count": getattr(entity, 'admins_count', None),
                }
                if isinstance(entity, User):
                    user_details = {
                        "first_name": entity.first_name,
                        "last_name": entity.last_name,
                        "user_id": entity.id,
                        "user_phone": entity.phone,
                    }
                    chat_info.update(user_details)
                elif isinstance(entity, (Chat, Channel)):
                    group_channel_details = {
                        "chat_title": getattr(entity, 'title', None),
                        "chat_members_count": getattr(entity, 'participants_count', None),
                    }
                    chat_info.update(group_channel_details)
                chat_data.append(chat_info)

        json_data = json.dumps(chat_data, ensure_ascii=False, indent=4)
        return json_data

    async def stop_monitoring(self):
        for session_name, task in self.monitoring_tasks.items():
            task.cancel()
            await db_crud.account_crud.set_active(session_name, False)
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Monitoring stopped for {session_name}")

    def list_sessions(self):
        return list(self.sessions.keys())

    async def remove_session(self, session_name):
        try:
            del self.sessions[session_name]
        except KeyError:
            pass

        # Also stop monitoring if it's running
        if session_name in self.monitoring_tasks:
            await self.stop_monitoring_for_session(session_name)

        # Delete account from the database

        await db_crud.account_crud.delete_on_cascade(session_name)
        try:

            os.remove(f'bot/sessions/{session_name}.session')
        except Exception as e:
            logger.error(f'Session not found. {e}')
            return
        logger.info(f"Session {session_name} and associated account removed")
        return True

    async def stop_monitoring_for_session(self, session_name):
        if session_name in self.monitoring_tasks:
            task = self.monitoring_tasks.pop(session_name)
            task.cancel()
            await db_crud.account_crud.set_active(session_name, False)
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Monitoring stopped for {session_name}")

    async def check_deleted_in_chat(self, start_time: int, end_time: int,
                                    chats: list = None, account_id: str = None,
                                    filters: dict = None) -> dict:
        diff = {"deleted": {}, "modified": {}}

        start_time_dt = datetime.fromtimestamp(start_time, tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)
        for chat_id in chats:
            saved_messages = await db_crud.message_crud.get_messages_by_chat_id_and_time(
                chat_id=chat_id,
                start_time=start_time,
                end_time=end_time,
                account_id=account_id
            )
            filtered_saved_messages = await self.apply_filters_to_messages(saved_messages, filters)
            saved_message_dict = {message.message_id: message for message in filtered_saved_messages}

            client = self.sessions.get(account_id, None)
            if client is None:
                client = await self.get_client_by_session_name(account_id)
            current_messages_in_chat = []

            async for message in client.iter_messages(entity=chat_id, offset_date=start_time_dt, reverse=True):
                if message.date.tzinfo is None:
                    message_date_aware = message.date.replace(tzinfo=timezone.utc)
                else:
                    message_date_aware = message.date.astimezone(timezone.utc)

                if message_date_aware < start_time_dt:
                    break
                current_messages_in_chat.append(message)

            filtered_current_messages = await self.apply_filters_to_messages(current_messages_in_chat, filters)
            current_message_dict = {message.id: message for message in filtered_current_messages}

            deleted_message_ids = set(saved_message_dict.keys()) - set(current_message_dict.keys())
            deleted_messages = [saved_message_dict[message_id] for message_id in deleted_message_ids]

            if deleted_messages:
                deleted_message_ids = [message.id for message in deleted_messages]
                updated_deleted_messages = await db_crud.message_crud.set_messages_deleted(ids=deleted_message_ids)
                updated_deleted_messages = [msg.to_dict() for msg in updated_deleted_messages]
                diff["deleted"][chat_id] = updated_deleted_messages

            for message_id, current_message in current_message_dict.items():
                saved_message = saved_message_dict.get(message_id)
                if saved_message and saved_message.text != current_message.text:
                    await db_crud.message_crud.update(saved_message.id, text=current_message.text,
                                                      is_updated=True, before_update_text=saved_message.text)
                    new_message = await db_crud.message_crud.read(saved_message.id)
                    diff["modified"].setdefault(chat_id, []).append(new_message.to_dict())

        return diff

    @staticmethod
    async def apply_filters_to_messages(messages, filters):
        filtered_messages = messages

        if filters:
            if filters.get("username"):
                if isinstance(filters["username"], str):
                    filtered_messages = [msg for msg in filtered_messages if msg.sender_username == filters["username"]]
                elif isinstance(filters["username"], list):
                    filtered_messages = [msg for msg in filtered_messages if msg.sender_username in filters["username"]]

            if filters.get("content"):
                if isinstance(filters["content"], list):
                    filtered_messages = [msg for msg in filtered_messages if
                                         any(content in msg.text for content in filters["content"])]
                elif isinstance(filters["content"], str):
                    filtered_messages = [msg for msg in filtered_messages if filters["content"] in msg.text]

            if filters.get("startswith"):
                if isinstance(filters["startswith"], str):
                    filtered_messages = [msg for msg in filtered_messages if msg.text.startswith(filters["startswith"])]
                elif isinstance(filters["startswith"], list):
                    filtered_messages = [msg for msg in filtered_messages if
                                         any(msg.text.startswith(prefix) for prefix in filters["startswith"])]

        return filtered_messages


if __name__ == '__main__':
    telegram_history = TelegramChatHistory()

    loop = asyncio.get_event_loop()
    for session in telegram_history.find_session_files():
        loop.run_until_complete(telegram_history.create_session(session))
