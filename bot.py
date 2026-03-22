import logging
import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

# ====== CONFIG ======
TOKEN = os.getenv("8267749053:AAEfuV5vNbZ_rBOjBz2Y65_fDQiGiorJ_qo")
ADMIN_USERNAME = "@odos567"
CHANNEL_ID = os.getenv("@ghjuuf")

# ====== INIT ======
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# ====== DB ======
conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    content_type TEXT,
    file_id TEXT,
    text TEXT,
    status TEXT,
    scheduled_time TEXT,
    rejection_reason TEXT
)
""")
conn.commit()

# ====== TIME SLOTS ======
TIME_SLOTS = ["10:00", "13:00", "16:00", "19:00", "22:00"]

# ====== HELPERS ======
def is_admin(user: types.User):
    return user.username == ADMIN_USERNAME.replace("@", "")

def get_busy_slots(date):
    cursor.execute("SELECT scheduled_time FROM posts WHERE scheduled_time LIKE ?", (f"{date}%",))
    return [row[0].split(" ")[1] for row in cursor.fetchall()]

# ====== USER SEND POST ======
@dp.message_handler(content_types=['text', 'photo'])
async def handle_post(message: types.Message):
    file_id = None
    text = message.text

    if message.photo:
        file_id = message.photo[-1].file_id
        text = message.caption

    cursor.execute("""
    INSERT INTO posts (user_id, username, content_type, file_id, text, status)
    VALUES (?, ?, ?, ?, ?, 'pending')
    """, (message.from_user.id, message.from_user.username, message.content_type, file_id, text))
    conn.commit()

    post_id = cursor.lastrowid

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Принять ✅", callback_data=f"accept_{post_id}"),
        InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{post_id}")
    )

    await bot.send_message(ADMIN_USERNAME, f"Новая заявка #{post_id}")
    await message.forward(ADMIN_USERNAME)
    await bot.send_message(ADMIN_USERNAME, "Выбери действие:", reply_markup=kb)

    await message.answer("Пост отправлен на модерацию")

# ====== ACCEPT ======
@dp.callback_query_handler(lambda c: c.data.startswith("accept"))
async def accept(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return

    post_id = int(callback.data.split("_")[1])
    today = datetime.now().strftime("%Y-%m-%d")
    busy = get_busy_slots(today)

    kb = InlineKeyboardMarkup(row_width=2)

    for t in TIME_SLOTS:
        if t in busy:
            kb.insert(InlineKeyboardButton(f"{t} 🔴", callback_data="busy"))
        else:
            kb.insert(InlineKeyboardButton(f"{t} 🟢", callback_data=f"time_{post_id}_{t}"))

    await callback.message.answer("Выбери время:", reply_markup=kb)

# ====== SELECT TIME ======
@dp.callback_query_handler(lambda c: c.data.startswith("time"))
async def set_time(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return

    _, post_id, time = callback.data.split("_")
    post_id = int(post_id)

    today = datetime.now().strftime("%Y-%m-%d")
    full_time = f"{today} {time}"

    cursor.execute("""
    UPDATE posts SET status='scheduled', scheduled_time=?
    WHERE id=?
    """, (full_time, post_id))
    conn.commit()

    await callback.message.answer(f"Пост запланирован на {full_time}")

# ====== REJECT ======
waiting_reject = {}

@dp.callback_query_handler(lambda c: c.data.startswith("reject"))
async def reject(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return

    post_id = int(callback.data.split("_")[1])
    waiting_reject[callback.from_user.id] = post_id

    await callback.message.answer("Напиши причину отказа (обязательно)")

# ====== REASON ======
@dp.message_handler()
async def handle_reason(message: types.Message):
    if message.from_user.id not in waiting_reject:
        r


eturn

    reason = message.text.strip()
    if not reason:
        await message.answer("Причина обязательна!")
        return

    post_id = waiting_reject.pop(message.from_user.id)

    cursor.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
    user_id = cursor.fetchone()[0]

    cursor.execute("""
    UPDATE posts SET status='rejected', rejection_reason=?
    WHERE id=?
    """, (reason, post_id))
    conn.commit()

    await bot.send_message(user_id, f"Ваш пост отклонён:\n\nПричина: {reason}")
    await message.answer("Отказ отправлен")

# ====== SCHEDULER ======
async def scheduler():
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
        SELECT id, content_type, file_id, text
        FROM posts
        WHERE status='scheduled' AND scheduled_time=?
        """, (now,))
        posts = cursor.fetchall()

        for p in posts:
            post_id, content_type, file_id, text = p

            if content_type == "text":
                await bot.send_message(CHANNEL_ID, text)
            else:
                await bot.send_photo(CHANNEL_ID, file_id, caption=text)

            cursor.execute("UPDATE posts SET status='posted' WHERE id=?", (post_id,))
            conn.commit()

        await asyncio.sleep(30)

# ====== MAIN ======
async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
