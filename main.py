import asyncio
from aiogram import Bot, Dispatcher, types
import sqlite3

TOKEN = 
TOKEN = "8354471373:AAEvhhGRSmsCaNhLedIWppB_FusRZRmNjSM"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Создание базы (если нет)
conn = sqlite3.connect("complaints.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    shop TEXT,
    description TEXT,
    link TEXT
)
""")
conn.commit()

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "Привет! Отправь жалобу в формате:\n\n"
        "Магазин: название\n"
        "Проблема: описание\n"
        "Ссылка: URL (если есть)"
    )

@dp.message_handler()
async def report(message: types.Message):
    text = message.text
    lines = text.split("\n")

    shop = ""
    description = ""
    link = ""

    for line in lines:
        if line.lower().startswith("магазин:"):
            shop = line.split(":", 1)[1].strip()
        elif line.lower().startswith("проблема:"):
            description = line.split(":", 1)[1].strip()
        elif line.lower().startswith("ссылка:"):
            link = line.split(":", 1)[1].strip()

    if not shop or not description:
        await message.answer("Укажи минимум 'Магазин:' и 'Проблема:'")
        return

    # Сохранение
    cursor.execute(
        "INSERT INTO complaints (user_id, username, shop, description, link) VALUES (?, ?, ?, ?, ?)",
        (message.from_user.id, message.from_user.username, shop, description, link)
    )
    conn.commit()

    # Отправка в канал
    msg = (
        f"❗ *Новая жалоба*\n"
        f"👤 Пользователь: @{message.from_user.username}\n"
        f"🏪 Магазин: {shop}\n"
        f"⚠ Проблема: {description}\n"
        f"🔗 Ссылка: {link}"
    )

    await bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")

    await message.answer("Жалоба отправлена!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
