from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta

TOKEN = "8267749053:AAEfuV5vNbZ_rBOjBz2Y65_fDQiGiorJ_qo"
ADMIN_ID = 123456789  # замените на айди @odos567, числовой
CHANNEL_ID = "@ghjuuf"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Хранилище постов и расписания в памяти
pending_posts = {}
scheduled_times = {}

# Временные слоты
time_slots = ["10:00", "13:00", "16:00", "19:00", "22:00"]

# Получение поста от пользователя
@dp.message_handler(content_types=['text', 'photo'])
async def receive_post(message: types.Message):
    post_id = message.message_id
    pending_posts[post_id] = message
    # Кнопки для админа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять ✅", callback_data=f"accept_{post_id}"),
            InlineKeyboardButton(text="Отклонить ❌", callback_data=f"reject_{post_id}")
        ]
    ])
    await bot.send_message(ADMIN_ID, f"Новая заявка от {message.from_user.full_name}", reply_markup=keyboard)

# Обработка нажатий админа
@dp.callback_query_handler(lambda c: c.data.startswith(("accept_", "reject_")))
async def handle_admin_choice(callback_query: types.CallbackQuery):
    data = callback_query.data
    post_id = int(data.split("_")[1])
    message = pending_posts.get(post_id)
    if not message:
        await callback_query.answer("Заявка уже обработана.")
        return

    if data.startswith("accept_"):
        # Создаём кнопки с временем
        keyboard = InlineKeyboardMarkup(row_width=1)
        buttons = []
        for t in time_slots:
            if t in scheduled_times:
                buttons.append(InlineKeyboardButton(text=f"🔴 {t}", callback_data="busy"))
            else:
                buttons.append(InlineKeyboardButton(text=f"🟢 {t}", callback_data=f"schedule_{post_id}_{t}"))
        keyboard.add(@id58222140 (*buttons))
        await callback_query.message.edit_reply_markup(keyboard)
    else:
        await callback_query.message.answer("Напиши причину отклонения:")
        # Ждём причину
        dp.register_message_handler(lambda m: send_rejection_reason(m, post_id), content_types=['text'], state=None)

async def send_rejection_reason(message: types.Message, post_id):
    original_post = pending_posts.get(post_id)
    if original_post:
        await bot.send_message(original_post.from_user.id, f"Ваша заявка отклонена. Причина: {message.text}")
    pending_posts.pop(post_id, None)
    await message.answer("Причина отправлена пользователю.")
    dp.message_handlers.unregister(send_rejection_reason)

# Выбор времени
@dp.callback_query_handler(lambda c: c.data.startswith("schedule_"))
async def schedule_post(callback_query: types.CallbackQuery):
    _, post_id, time_slot = callback_query.data.split("_")
    post_id = int(post_id)
    scheduled_times[time_slot] = pending_posts[post_id]

    # Убираем кнопки
    await callback_query.message.edit_reply_markup()

    # Расчёт времени публикации
    now = datetime.now()
    post_hour, post_minute = map(int, time_slot.split(":"))
    publish_time = now.replace(hour=post_hour, minute=post_minute, second=0, microsecond=0)
    if publish_time < now:
        publish_time += timedelta(days=1)

    delay = (publish_time - now).total_seconds()
    
    # Отправка поста в канал через asyncio.sleep
    message = pending_posts.pop(post_id)
    await callback_query.answer(f"Пост запланирован на {time_slot}")
    
    async def publish():
        await asyncio.sleep(delay)
        if message.content_type == 'photo':
            await bot.send_photo(CHANNEL_ID, photo=message.photo[-1].file_id, caption=message.caption or "")
        else:
            await bot.send_message(CHANNEL_ID, message.text)
        scheduled_times.pop(time_slot, None)

    import asyncio
    asyncio.create_task(publish())

# Обработка занятых кнопок
@dp.callback_query_handler(lambda c: c.data == "busy")




