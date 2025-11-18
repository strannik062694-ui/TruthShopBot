# main.py
import telebot
from telebot import types
import sqlite3
import os
import logging
from datetime import datetime

# --- Параметры ---
TOKEN = 8354471373:AAEvhhGRSmsCaNhLedIWppB_FusRZRmNjSM os.getenv("TELEGRAM_BOT_TOKEN")  # токен из переменных окружения
ADMIN_CHAT = "@TruthShop_Net"  # канал куда будут уходить одобренные жалобы
MODERATION_GROUP = os.getenv("MODERATION_GROUP_ID", "")  # ID группы для модерации (нужно будет добавить)

# Список ID администраторов (добавьте свой ID)
ADMIN_IDS = [872762594] # Например: [123456789, 987654321]

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not TOKEN:
    logger.error("❌ ОШИБКА: Не найден TELEGRAM_BOT_TOKEN в переменных окружения!")
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- База данных ---
conn = sqlite3.connect("complaints.db", check_same_thread=False)
cursor = conn.cursor()

# Обновленная структура с полями для модерации
cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    shop TEXT,
    text TEXT,
    photo_file_id TEXT,
    contact TEXT,
    status TEXT DEFAULT 'pending',
    admin_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    moderated_at TEXT
)
""")
conn.commit()

# Временные состояния пользователей
user_state = {}
temp_data = {}

# --- Проверка прав администратора ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Команды ---
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    user_id = msg.from_user.id
    bot.send_message(msg.chat.id,
        f"👋 Привет! Я бот для приёма жалоб на интернет-магазины.\n\n"
        f"Нажми /complaint чтобы оставить жалобу.\n\n"
        f"<i>Ваш ID: <code>{user_id}</code></i>"
    )

@bot.message_handler(commands=['complaint'])
def cmd_complaint(msg):
    chat_id = msg.chat.id
    user_state[chat_id] = "shop"
    temp_data[chat_id] = {}
    bot.send_message(chat_id, "🛒 На какой интернет-магазин жалоба? Введи название или ссылку.")

# --- Админские команды ---
@bot.message_handler(commands=['admin'])
def cmd_admin(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    bot.send_message(msg.chat.id,
        "👨‍💼 <b>Админ-панель</b>\n\n"
        "Доступные команды:\n"
        "/pending - показать необработанные жалобы\n"
        "/approve <id> - одобрить жалобу\n"
        "/reject <id> - отклонить жалобу\n"
        "/stats - статистика по жалобам\n"
        "/complaint_info <id> - детали жалобы"
    )

@bot.message_handler(commands=['pending'])
def cmd_pending(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    cursor.execute("SELECT id, shop, username, created_at FROM complaints WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10")
    pending = cursor.fetchall()
    
    if not pending:
        bot.send_message(msg.chat.id, "✅ Нет необработанных жалоб!")
        return
    
    text = "⏳ <b>Необработанные жалобы:</b>\n\n"
    for complaint_id, shop, username, created in pending:
        text += f"#{complaint_id} - {shop}\n"
        text += f"От: {username} ({created})\n"
        text += f"/complaint_info {complaint_id}\n\n"
    
    bot.send_message(msg.chat.id, text)

@bot.message_handler(commands=['complaint_info'])
def cmd_complaint_info(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    try:
        complaint_id = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "❌ Использование: /complaint_info <id>")
        return
    
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()
    
    if not complaint:
        bot.send_message(msg.chat.id, "❌ Жалоба не найдена.")
        return
    
    complaint_id, user_id, username, shop, text, photo_file_id, contact, status, admin_id, created_at, moderated_at = complaint
    
    msg_text = (
        f"📋 <b>Жалоба #{complaint_id}</b>\n\n"
        f"🛒 <b>Магазин:</b> {shop}\n"
        f"📄 <b>Текст:</b> {text}\n"
        f"👤 <b>Пользователь:</b> {username} (ID: <code>{user_id}</code>)\n"
        f"☎️ <b>Контакт:</b> {contact}\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"📅 <b>Создано:</b> {created_at}\n"
    )
    
    # Inline кнопки для модерации
    markup = types.InlineKeyboardMarkup()
    if status == 'pending':
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{complaint_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{complaint_id}")
        )
    
    bot.send_message(msg.chat.id, msg_text, reply_markup=markup)
    
    if photo_file_id and photo_file_id != "нет":
        try:
            bot.send_photo(msg.chat.id, photo_file_id)
        except:
            pass

@bot.message_handler(commands=['approve'])
def cmd_approve(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    try:
        complaint_id = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "❌ Использование: /approve <id>")
        return
    
    approve_complaint(complaint_id, msg.from_user.id, msg.chat.id)

@bot.message_handler(commands=['reject'])
def cmd_reject(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    try:
        complaint_id = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "❌ Использование: /reject <id>")
        return
    
    reject_complaint(complaint_id, msg.from_user.id, msg.chat.id)

@bot.message_handler(commands=['stats'])
def cmd_stats(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ У вас нет прав администратора.")
        return
    
    cursor.execute("SELECT status, COUNT(*) FROM complaints GROUP BY status")
    stats = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]
    
    text = "📊 <b>Статистика жалоб:</b>\n\n"
    text += f"Всего жалоб: {total}\n\n"
    
    for status, count in stats:
        emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(status, "📋")
        text += f"{emoji} {status}: {count}\n"
    
    bot.send_message(msg.chat.id, text)

# --- Обработка callback-кнопок ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def callback_moderate(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ У вас нет прав администратора.")
        return
    
    action, complaint_id = call.data.split('_')
    complaint_id = int(complaint_id)
    
    if action == 'approve':
        approve_complaint(complaint_id, call.from_user.id, call.message.chat.id)
        bot.answer_callback_query(call.id, "✅ Жалоба одобрена!")
    elif action == 'reject':
        reject_complaint(complaint_id, call.from_user.id, call.message.chat.id)
        bot.answer_callback_query(call.id, "❌ Жалоба отклонена!")
    
    # Обновляем сообщение, убирая кнопки
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# --- Функции модерации ---
def approve_complaint(complaint_id, admin_id, chat_id):
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()
    
    if not complaint:
        bot.send_message(chat_id, "❌ Жалоба не найдена.")
        return
    
    if complaint[7] != 'pending':  # status field
        bot.send_message(chat_id, f"⚠️ Жалоба уже обработана (статус: {complaint[7]})")
        return
    
    # Обновляем статус
    cursor.execute(
        "UPDATE complaints SET status = 'approved', admin_id = ?, moderated_at = ? WHERE id = ?",
        (admin_id, datetime.now().isoformat(), complaint_id)
    )
    conn.commit()
    
    # Отправляем в публичный канал
    user_id, username, shop, text, photo_file_id, contact = complaint[1], complaint[2], complaint[3], complaint[4], complaint[5], complaint[6]
    
    msg_text = (
        f"❗ <b>Новая жалоба #{complaint_id}</b>\n\n"
        f"🛒 <b>Магазин:</b> {shop}\n"
        f"📄 <b>Жалоба:</b> {text}\n"
        f"☎️ <b>Контакт:</b> {contact}\n"
    )
    
    try:
        bot.send_message(ADMIN_CHAT, msg_text)
        if photo_file_id and photo_file_id != "нет":
            bot.send_photo(ADMIN_CHAT, photo_file_id)
        
        # Уведомляем пользователя
        bot.send_message(user_id, 
            f"✅ Ваша жалоба #{complaint_id} была одобрена и опубликована!\n\n"
            f"Спасибо за ваше обращение."
        )
        
        bot.send_message(chat_id, f"✅ Жалоба #{complaint_id} одобрена и опубликована в {ADMIN_CHAT}")
    except Exception as e:
        logger.exception("Ошибка при публикации жалобы: %s", e)
        bot.send_message(chat_id, f"⚠️ Ошибка при публикации: {e}")

def reject_complaint(complaint_id, admin_id, chat_id):
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()
    
    if not complaint:
        bot.send_message(chat_id, "❌ Жалоба не найдена.")
        return
    
    if complaint[7] != 'pending':
        bot.send_message(chat_id, f"⚠️ Жалоба уже обработана (статус: {complaint[7]})")
        return
    
    # Обновляем статус
    cursor.execute(
        "UPDATE complaints SET status = 'rejected', admin_id = ?, moderated_at = ? WHERE id = ?",
        (admin_id, datetime.now().isoformat(), complaint_id)
    )
    conn.commit()
    
    user_id = complaint[1]
    
    try:
        # Уведомляем пользователя
        bot.send_message(user_id, 
            f"❌ Ваша жалоба #{complaint_id} была отклонена модерацией.\n\n"
            f"Возможные причины: недостаточно информации, некорректные данные или жалоба не соответствует правилам."
        )
        bot.send_message(chat_id, f"❌ Жалоба #{complaint_id} отклонена. Пользователь уведомлен.")
    except Exception as e:
        logger.exception("Ошибка при уведомлении: %s", e)
        bot.send_message(chat_id, f"❌ Жалоба #{complaint_id} отклонена, но не удалось уведомить пользователя.")

# --- Обработка входящих сообщений (текст/фото) ---
@bot.message_handler(content_types=['text', 'photo'])
def all_handler(msg):
    chat_id = msg.chat.id
    if chat_id not in user_state:
        return

    state = user_state[chat_id]

    if state == "shop":
        shop = msg.text.strip() if msg.content_type == 'text' else ""
        temp_data[chat_id]['shop'] = shop
        user_state[chat_id] = "text"
        bot.send_message(chat_id, "✍️ Опиши суть жалобы (коротко):")
        return

    if state == "text":
        text = msg.text.strip() if msg.content_type == 'text' else ""
        temp_data[chat_id]['text'] = text
        user_state[chat_id] = "photo"
        bot.send_message(chat_id, "📸 Прикрепи фото/скриншот (или напиши 'нет'):")
        return

    if state == "photo":
        file_id = "нет"
        if msg.content_type == 'photo':
            file_id = msg.photo[-1].file_id
        elif msg.content_type == 'text' and msg.text.lower() == 'нет':
            file_id = "нет"
        else:
            file_id = "нет"

        temp_data[chat_id]['photo'] = file_id
        user_state[chat_id] = "contact"
        bot.send_message(chat_id, "📱 Оставь контакт (номер, email или напиши 'анонимно'):")
        return

    if state == "contact":
        contact = msg.text.strip() if msg.content_type == 'text' else ""
        temp_data[chat_id]['contact'] = contact

        # Сохраняем в БД со статусом pending
        user = msg.from_user
        username = user.username if user.username else f"{user.first_name or ''} {user.last_name or ''}".strip()
        cursor.execute(
            "INSERT INTO complaints (user_id, username, shop, text, photo_file_id, contact, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (chat_id, username, temp_data[chat_id].get('shop', ''),
             temp_data[chat_id].get('text', ''), temp_data[chat_id].get('photo', ''), contact)
        )
        conn.commit()
        complaint_id = cursor.lastrowid

        # Отправляем в модераторскую группу если она указана
        if MODERATION_GROUP:
            msg_text = (
                f"⏳ <b>Новая жалоба #{complaint_id}</b> (ожидает модерации)\n\n"
                f"🛒 <b>Магазин:</b> {temp_data[chat_id].get('shop','(не указано)')}\n"
                f"📄 <b>Жалоба:</b> {temp_data[chat_id].get('text','(пусто)')}\n"
                f"👤 <b>Пользователь:</b> {username} (id: <code>{chat_id}</code>)\n"
                f"☎️ <b>Контакт:</b> {contact}\n"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{complaint_id}"),
                types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{complaint_id}")
            )
            
            try:
                bot.send_message(MODERATION_GROUP, msg_text, reply_markup=markup)
                if temp_data[chat_id].get('photo') and temp_data[chat_id]['photo'] != "нет":
                    bot.send_photo(MODERATION_GROUP, temp_data[chat_id]['photo'])
            except Exception as e:
                logger.exception("Ошибка при отправке в модераторскую группу: %s", e)

        bot.send_message(chat_id, 
            f"✅ Жалоба #{complaint_id} принята и отправлена на модерацию.\n\n"
            f"Мы проверим вашу жалобу и сообщим о результате."
        )
        
        # очистка
        user_state.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        return

# --- Запуск ---
if __name__ == "__main__":
    logger.info("Запуск бота...")
    logger.info(f"Админов в системе: {len(ADMIN_IDS)}")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
