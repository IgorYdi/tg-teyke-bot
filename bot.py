import os
import asyncio
import logging
import pytz
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask

# Библиотеки бота
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Планировщик и БД
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- ВЕБ-ЗАГЛУШКА ДЛЯ ХОСТИНГА (чтобы не спал) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# --- НАСТРОЙКИ ---
API_TOKEN = '8702698153:AAHmS-M1VibhAcjsSAvUqTySRnTexB0xX2c'
ADMIN_ID = 7805872198
CHANNEL_ID = -1003106826537
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
TIMES = ["7:00", "08:00", "10:00", "13:00", "16:00", "19:00", "22:00"]

# ВСТАВЬ СВОЮ ССЫЛКУ ИЗ SUPABASE ТУТ:
DB_URL = "postgresql://postgres:triFonov0890@db.benfreggxmmmleypervi.supabase.co:6543/postgres?sslmode=require"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройка планировщика с внешней БД
jobstores = {'default': SQLAlchemyJobStore(url=DB_URL)}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=MOSCOW_TZ)

# --- БАЗА ДАННЫХ ДЛЯ СЛОТОВ ---
Base = declarative_base()
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

class Schedule(Base):
    __tablename__ = 'schedule_slots'
    id = Column(Integer, primary_key=True)
    date_time_key = Column(String, unique=True) # Формат "ГГГГ-ММ-ДД ЧЧ:ММ"

Base.metadata.create_all(engine)

class PostStates(StatesGroup):
    waiting_for_reason = State()

# --- ЛОГИКА ---
async def send_to_channel(photo_id, caption):
    try:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=photo_id, caption=caption or "")
    except Exception as e:
        logging.error(f"Ошибка публикации: {e}")

@dp.message(Command("time"))
async def get_time(message: types.Message):
    now = datetime.now(MOSCOW_TZ)
    await message.answer(f"🕒 Время МСК: {now.strftime('%H:%M:%S')}")

@dp.message(F.photo)
async def handle_post(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="✅ Принять", callback_data="appr_check"))
    builder.row(types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decl_{message.from_user.id}"))
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
                         caption=f"Новая заявка!\n\n{message.caption or ''}", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "appr_check")
async def show_slots(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    session = Session()
    today = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
    
    for t in TIMES:
        key = f"{today} {t}"
        busy = session.query(Schedule).filter_by(date_time_key=key).first()
        icon = "🔴" if busy else "🟢"
        cb = "ignore" if busy else f"time_{t}"
        builder.add(types.InlineKeyboardButton(text=f"{icon} {t}", callback_data=cb))
    
    session.close()
    builder.adjust(2)
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("time_"))
async def set_time(callback: types.CallbackQuery):
    time_str = callback.data.split("_")[1]
    now = datetime.now(MOSCOW_TZ)
    today = now.strftime("%Y-%m-%d")
    key = f"{today} {time_str}"
    
    session = Session()
    if session.query(Schedule).filter_by(date_time_key=key).first():
        session.close()
        return await callback.answer("Занято!")

    # Бронируем
    new_slot = Schedule(date_time_key=key)
    session.add(new_slot)
    session.commit()
    session.close()

    run_time = MOSCOW_TZ.localize(datetime.strptime(key, "%Y-%m-%d %H:%M"))
    if run_time < now: run_time += timedelta(days=1)

    photo_id = callback.message.photo[-1].file_id
    caption = callback.message.caption.replace("Новая заявка!\n\n", "")

    scheduler.add_job(send_to_channel, 'date', run_date=run_time, args=[photo_id, caption], id=f"j_{run_time.timestamp()}")
    await callback.message.edit_caption(caption=f"✅ ПРИНЯТО на {run_time.strftime('%H:%M')} МСК")

# --- ЗАПУСК ---
async def main():
    if not scheduler.running: scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run_web).start() # Запуск веб-заглушки
    asyncio.run(main())






