import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

posts = {}
scheduled = {}

TIME_SLOTS = ["10:00", "13:00", "16:00", "19:00", "22:00"]

# Получение поста от пользователя
@dp.message_handler(content_types=['text', 'photo'])
async def handle_post(message: types.Message):
    post_id = message.message_id
    posts[post_id] = message

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Принять ✅", callback_data=f"accept_{post_id}"),
        InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{post_id}")
    )

    await bot.send_message(
        ADMIN_ID,
        "Новая заявка:",
    )
    await message.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, "Выбери действие:", reply_markup=kb)

# Принятие поста
@dp.callback_query_handler(lambda c: c.data.startswith("accept"))
async def accept_post(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[1])

    kb = InlineKeyboardMarkup(row_width=2)

    for t in TIME_SLOTS:
        if t in scheduled:
            kb.insert(InlineKeyboardButton(f"{t} 🔴", callback_data="busy"))
        else:
            kb.insert(InlineKeyboardButton(f"{t} 🟢", callback_data=f"time_{post_id}_{t}"))

    await callback.message.answer("Выбери время:", reply_markup=kb)

# Выбор времени
@dp.callback_query_handler(lambda c: c.data.startswith("time"))
async def set_time(callback: types.CallbackQuery):
    _, post_id, time = callback.data.split("_")
    post_id = int(post_id)

    scheduled[time] = post_id

    await callback.message.answer(f"Запланировано на {time}")

# Отклонение
@dp.callback_query_handler(lambda c: c.data.startswith("reject"))
async def reject_post(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    posts[post_id] = {"status": "waiting_reason"}

    await callback.message.answer("Напиши причину отказа")

# Причина отказа
@dp.message_handler()
async def reason_handler(message: types.Message):
    for k, v in posts.items():
        if isinstance(v, dict) and v.get("status") == "waiting_reason":
            await bot.send_message(k, f"Ваш пост отклонён:\n{message.text}")
            posts[k] = None
            await message.answer("Отправлено пользователю")
            break

# Публикация (каждую минуту проверка)
async def scheduler():
    while True:
        now = asyncio.get_event_loop().time()
        for t, post_id in list(scheduled.items()):
            msg = posts.get(post_id)
            if msg:
                if msg.content_type == "text":
                    await bot.send_message(CHANNEL_ID, msg.text)
                elif msg.content_type == "photo":
                    await bot.send_photo(CHANNEL_ID, msg.photo[-1].file_id, caption=msg.caption)
                scheduled.pop(t)
        await asyncio.sleep(60)

async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
