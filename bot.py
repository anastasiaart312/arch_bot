import random
import sqlite3
import re
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8827573585:AAH9ac0ZS3xfl8D6iayPL1v7yX8cME2Lcao"  # ЗАМЕНИТЕ НА СВОЙ
ADMIN_ID = 1239648336  # ВАШ ID

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logging.basicConfig(level=logging.INFO)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('buildings.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_file_id TEXT,
            name TEXT,
            year INTEGER,
            style TEXT,
            full_caption TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_random_building():
    conn = sqlite3.connect('buildings.db')
    cur = conn.cursor()
    cur.execute('SELECT id, photo_file_id, name, year, style, full_caption FROM buildings ORDER BY RANDOM() LIMIT 1')
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'photo_file_id': row[1],
            'name': row[2],
            'year': row[3],
            'style': row[4],
            'full_caption': row[5]
        }
    return None

def get_style_variants(correct_style):
    conn = sqlite3.connect('buildings.db')
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT style FROM buildings WHERE style != ? ORDER BY RANDOM() LIMIT 2', (correct_style,))
    others = [row[0] for row in cur.fetchall()]
    conn.close()
    
    while len(others) < 2:
        others.append("классицизм")
    
    variants = [correct_style] + others
    random.shuffle(variants)
    return variants

def get_style_fact(style):
    facts = {
        "старорусский стиль": "Примеры: Дворец царя Алексея Михайловича, Церковь Вознесения в Коломенском",
        "русское узорочье": "Примеры: Церковь Рождества Богородицы, Храм Николая Чудотворца",
        "барокко": "Примеры: Храм Священномученика Климента, Богоявленский собор, Дом Апраксиных-Трубецких",
        "неорусский стиль": "Пример: Театр им. Маяковского, 1886 год",
        "эклектика": "Смешение стилей, популярное в XIX веке",
        "модерн": "Стиль конца XIX — начала XX века"
    }
    return facts.get(style, "Интересный архитектурный стиль!")

# ========== СОСТОЯНИЯ ==========
class GameStates(StatesGroup):
    waiting_for_answer = State()

# ========== КОМАНДА /START ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🏛 *Архитектурная угадайка!*\n\n"
        "Я покажу фото здания из моего канала, а ты угадай его стиль.\n"
        "Нажми /play чтобы начать игру.",
        parse_mode="Markdown"
    )

# ========== КОМАНДА /PLAY ==========
@dp.message(Command("play"))
async def cmd_play(message: types.Message, state: FSMContext):
    building = get_random_building()
    if not building:
        await message.answer("❌ В базе пока нет зданий. Добавьте их через команду /add или перешлите пост боту.")
        return
    
    variants = get_style_variants(building['style'])
    
    # Сохраняем данные в состояние
    await state.update_data(
        building_id=building['id'],
        correct_style=building['style'],
        variants=variants,
        name=building['name'],
        year=building['year'],
        full_caption=building['full_caption']
    )
    
    # Создаём кнопки с ЦИФРАМИ (гарантированно без точек и проблем)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"1️⃣ {variants[0]}", callback_data="ans_0")],
            [InlineKeyboardButton(text=f"2️⃣ {variants[1]}", callback_data="ans_1")],
            [InlineKeyboardButton(text=f"3️⃣ {variants[2]}", callback_data="ans_2")]
        ]
    )
    
    await message.answer_photo(
        photo=building['photo_file_id'],
        caption=f"🏛 *Угадай стиль этого здания*\n\nПодсказка: построено в {building['year']} году\n\nВыбери вариант:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    await state.set_state(GameStates.waiting_for_answer)

# ========== ОБРАБОТКА ОТВЕТА ==========
@dp.callback_query(GameStates.waiting_for_answer)
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    correct_style = data.get('correct_style')
    variants = data.get('variants', [])
    name = data.get('name', 'здание')
    year = data.get('year', 'неизвестном')
    full_caption = data.get('full_caption', '')
    
    # Получаем индекс выбранного варианта (0, 1, 2)
    chosen_index = int(callback.data.replace("ans_", ""))
    chosen_style = variants[chosen_index]
    
    if chosen_style == correct_style:
        style_fact = get_style_fact(correct_style)
        await callback.message.edit_caption(
            caption=f"✅ *Правильно!*\n\n"
                    f"Это действительно *{correct_style}*.\n"
                    f"🏛 *{name}*, {year} год.\n\n"
                    f"📚 *Из справки:* {style_fact}\n\n"
                    f"*Оригинальная подпись:*\n{full_caption}",
            parse_mode="Markdown",
            reply_markup=None
        )
    else:
        await callback.message.edit_caption(
            caption=f"❌ *Не угадал!*\n\n"
                    f"Это *{correct_style}*, а ты выбрал *{chosen_style}*.\n"
                    f"🏛 *{name}*, {year} год.\n\n"
                    f"*Оригинальная подпись:*\n{full_caption}",
            parse_mode="Markdown",
            reply_markup=None
        )
    
    await callback.message.answer(
        "🔄 Хочешь попробовать ещё? Нажми /play",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎯 Следующее здание", callback_data="play_again")]]
        )
    )
    await state.clear()

# ========== КНОПКА "ИГРАТЬ СНОВА" ==========
@dp.callback_query(lambda c: c.data == "play_again")
async def play_again(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await cmd_play(callback.message, state)

# ========== КОМАНДА /ADD ДЛЯ АДМИНА ==========
@dp.message(Command("add"))
async def add_building(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 Доступ запрещён")
        return
    
    try:
        parts = message.text.replace('/add ', '').split('|')
        photo_id = parts[0].strip()
        name = parts[1].strip()
        year = int(parts[2].strip())
        style = parts[3].strip()
        full_caption = parts[4].strip()
        
        conn = sqlite3.connect('buildings.db')
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO buildings (photo_file_id, name, year, style, full_caption) VALUES (?, ?, ?, ?, ?)',
            (photo_id, name, year, style, full_caption)
        )
        conn.commit()
        conn.close()
        await message.answer(f"✅ Добавлено: {name} ({style})")
    except Exception as e:
        await message.answer(f"❌ Ошибка! Пример:\n/add AgACAgI...|Театр|1886|неорусский стиль|ваша подпись")

# ========== АВТОДОБАВЛЕНИЕ ПРИ ПЕРЕСЫЛКЕ ==========
@dp.message(lambda msg: msg.forward_from_chat is not None)
async def auto_add_from_channel(message: types.Message):
    if not message.photo:
        await message.answer("📷 Пожалуйста, перешлите пост с ФОТО.")
        return
    
    caption = message.caption or ""
    if "архитектурные заметки" not in caption:
        await message.answer("❌ Это не похоже на пост с архитектурой. Подпись должна содержать '// архитектурные заметки //'")
        return
    
    pattern = r'//\s*архитектурные\s+заметки\s*//\s*(\d+)\s*//\s*(.*?),\s*(\d{4})\s*//\s*(.*?)$'
    match = re.search(pattern, caption, re.DOTALL)
    
    if not match:
        await message.answer("❌ Не удалось распознать формат подписи.\n\n"
                            "Ожидаемый формат:\n"
                            "// архитектурные заметки // 81 // Театр, 1886 // неорусский стиль")
        return
    
    number = match.group(1).strip()
    name = match.group(2).strip()
    year = int(match.group(3))
    style = match.group(4).strip()
    full_caption = caption.strip()
    photo_file_id = message.photo[-1].file_id
    
    try:
        conn = sqlite3.connect('buildings.db')
        cur = conn.cursor()
        
        cur.execute('SELECT id FROM buildings WHERE name = ? AND year = ?', (name, year))
        if cur.fetchone():
            await message.answer(f"⚠️ Здание '{name}' ({year}) уже есть в базе.")
            conn.close()
            return
        
        cur.execute('''
            INSERT INTO buildings (photo_file_id, name, year, style, full_caption)
            VALUES (?, ?, ?, ?, ?)
        ''', (photo_file_id, name, year, style, full_caption))
        
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Добавлено: *{name}* ({year})\n"
                            f"🏛 Стиль: *{style}*",
                            parse_mode="Markdown")
        
        conn = sqlite3.connect('buildings.db')
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM buildings')
        count = cur.fetchone()[0]
        conn.close()
        
        await message.answer(f"📊 Теперь в базе *{count}* зданий. Напиши /play, чтобы играть!",
                            parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {e}")

# ========== ЗАПУСК ==========
async def main():
    init_db()
    print("🤖 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())