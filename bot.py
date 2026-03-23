mport asyncio
import sqlite3
from datetime import datetime, time, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- КОНФИГ ---
TOKEN = "8267749053:AAEfuV5vNbZ_rBOjBz2Y65_fDQiGiorJ_qo"
ADMIN_ID = @odos567  # <--- ЗАМЕНИ НА СВОЙ ID (ЧИСЛА)
CHANNEL_ID = "@ghjuuf"
TIMES = ["10:00", "13:00", "16:00", "19:00", "22:00"]

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler()

# База в оперативной памяти (сбросится при перезагрузке, как ты и хотел)
db = sqlite3.connect(":memory:", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE slots (date TEXT, time TEXT)")
cur.execute("CREATE TABLE queue (id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, file_id TEXT, caption TEXT)")
db.commit()

class PostStates(StatesGroup):
    waiting_for_reason = State()

# --- ЛОГИКА ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Пришли пост (текст или фото с подписью).")

# Прием постов от пользователей
@dp.message(F.chat.type == "private")
async def handle_submission(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Ты админ, но посты присылай как обычный юзер для теста.")
    
    m_type = "photo" if message.photo else "text"
    file_id = message.photo[-1].file_id if message.photo else ""
    caption = message.caption or message.text or ""
    
    cur.execute("INSERT INTO queue (user_id, type, file_id, caption) VALUES (?, ?, ?, ?)", 
                (message.from_user.id, m_type, file_id, caption))
    db.commit()
    post_id = cur.lastrowid

    kb = InlineKeyboardBuilder()
    kb.button(text="Принять ✅", callback_data=f"accept_{post_id}")
    kb.button(text="Отклонить ❌", callback_data=f"reject_{post_id}")
    
    await bot.send_message(ADMIN_ID, f"⚡️ Новая заявка #{post_id}")
    await message.copy_to(ADMIN_ID, reply_markup=kb.as_markup())
    await message.answer("Отправил админу!")

# Кнопка "Отклонить"
@dp.callback_query(F.data.startswith("reject_"))
async def reject_callback(callback: types.CallbackQuery, state: FSMContext):
    post_id = callback.data.split("_")[1]
    await state.update_data(reject_post_id=post_id)

    await state.set_state(PostStates.waiting_for_reason)
    await callback.message.answer("Напиши причину отказа:")
    await callback.answer()

# Обработка текста причины отказа
@dp.message(PostStates.waiting_for_reason)
async def send_rejection(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("reject_post_id")
    
    cur.execute("SELECT user_id FROM queue WHERE id = ?", (post_id,))
    res = cur.fetchone()
    if res:
        await bot.send_message(res[0], f"❌ Твой пост отклонен.\nПричина: {message.text}")
        await message.answer("Пользователь уведомлен.")
    await state.clear()

# Кнопка "Принять" -> Выбор времени
@dp.callback_query(F.data.startswith("accept_"))
async def show_times(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    today = datetime.now().strftime("%Y-%m-%d")
    
    cur.execute("SELECT time FROM slots WHERE date = ?", (today,))
    taken_times = [row[0] for row in cur.fetchall()]
    
    kb = InlineKeyboardBuilder()
    for t in TIMES:
        is_taken = t in taken_times
        status = "🔴" if is_taken else "🟢"
        cb_data = "ignore" if is_taken else f"sched_{post_id}_{t}"
        kb.button(text=f"{status} {t}", callback_data=cb_data)
    
    kb.adjust(1)
    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())

# Выбор конкретного времени и постановка в очередь
@dp.callback_query(F.data.startswith("sched_"))
async def schedule_post(callback: types.CallbackQuer


y):
    _, post_id, post_time = callback.data.split("_")
    today = datetime.now().strftime("%Y-%m-%d")
    
    cur.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (today, post_time))
    cur.execute("SELECT user_id, type, file_id, caption FROM queue WHERE id = ?", (post_id,))
    data = cur.fetchone()
    db.commit()

    # Считаем когда постить
    target_time = time.fromisoformat(post_time)
    run_date = datetime.combine(datetime.now().date(), target_time)
    
    if run_date < datetime.now():
        run_date += timedelta(days=1) # Если время уже прошло сегодня, шлем завтра

    scheduler.add_job(
        send_to_channel, 
        "date", 
        run_date=run_date, 
        args=[data[1], data[2], data[3]]
    )
    
    await callback.message.edit_text(f"✅ Запланировано на {post_time}")
    await bot.send_message(data[0], f"✅ Твой пост опубликуют в {post_time}")

# Сама функция отправки в канал
async def send_to_channel(m_type, file_id, caption):
    try:
        if m_type == "photo":
            await bot.send_photo(CHANNEL_ID, photo=file_id, caption=caption)
        else:
            await bot.send_message(CHANNEL_ID, text=caption)
    except Exception as e:
        print(f"Ошибка при публикации: {e}")

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



1 сообщение






