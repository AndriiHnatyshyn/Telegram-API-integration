from telethon import TelegramClient, events

# Replace these with your own values
api_id = 2040
api_hash = 'b18441a1ff607e10a989891a5462e627'
session_name = 'blalbla'  # The name of your session file (e.g., "my_session")

# Initialize the Telegram client
client = TelegramClient(session_name, api_id, api_hash)

async def main():
    # Connect to Telegram
    await client.start()

    print("Connected to Telegram! Listening for new messages...")

    # Event handler for new messages
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        sender = await event.get_sender()
        chat = await event.get_chat()
        print(chat)
        chat_id = chat.id
        chat_name = chat.first_name
        if hasattr(chat, 'usernames'):
            try:
                chat_username = chat.usernames[0].username if chat.usernames else chat.first_name
            except KeyError:
                chat_username = chat.first_name
        else:
            chat_username = chat.username if hasattr(chat, 'username') else chat.first_name
        print(chat_id, chat_name, chat_username)

    # Keep the client running
    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())