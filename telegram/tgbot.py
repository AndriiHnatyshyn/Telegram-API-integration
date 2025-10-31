import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from db.facade import DB
from dotenv import load_dotenv


db_crud = DB()
load_dotenv()

TOKEN = os.getenv("TOKEN")

dp = Dispatcher()
TGbot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    data = message.text.split(' ')[1]
    token, user_id = data.split('_')
    tg_id = message.from_user.id
    user = await DB.user_crud.read(id=user_id)
    if user and user.verification_token == token:
        await DB.user_crud.update(id=user_id, tg_id=tg_id)
        await message.answer('Verified, notifications will be sent to this chat')
    else:
        await message.answer('Something went wrong')


async def main() -> None:
    # And the run events dispatching
    await dp.start_polling(TGbot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
