import json
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка конфигурации из файла config.json
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config.get("token")
ADMINS = config.get("admins", [])

# Шаблоны и тексты сообщений из конфига
ADMIN_GREETING = config.get("admin_greeting")
USER_GREETING = config.get("user_greeting")
USER_MESSAGE_ACCEPTED = config.get("user_message_accepted")
SLOW_MODE_WARNING = config.get("slow_mode_warning")
BAN_INVALID_FORMAT = config.get("ban_invalid_format")
BAN_USAGE = config.get("ban_usage")
USER_ALREADY_BANNED = config.get("user_already_banned")
USER_BANNED = config.get("user_banned")
UNBAN_INVALID_FORMAT = config.get("unban_invalid_format")
UNBAN_USAGE = config.get("unban_usage")
USER_NOT_BANNED = config.get("user_not_banned")
USER_UNBANNED = config.get("user_unbanned")
ADMIN_FORWARD_ERROR = config.get("admin_forward_error")
SLOW_MODE_INTERVAL = config.get("slow_mode_interval", 3600)  # 1 час в секундах

# Словарь для отслеживания времени последнего сообщения от каждого пользователя
last_message_time = {}

# --- Работа с файлом забаненных пользователей ---
def load_banned():
    try:
        with open("banned.json", "r", encoding="utf-8") as f:
            banned_list = json.load(f)
        return banned_list
    except Exception as e:
        logging.error(f"Ошибка загрузки banned.json: {e}")
        return []

def save_banned(banned_list):
    try:
        with open("banned.json", "w", encoding="utf-8") as f:
            json.dump(banned_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка сохранения banned.json: {e}")

banned_users = load_banned()

# --- Работа с файлом message_map ---
def load_message_map():
    try:
        with open("message_map.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        # Преобразуем ключи обратно в tuple
        return {tuple(map(int, key.split(":"))): tuple(value) for key, value in data.items()}
    except Exception as e:
        logging.error(f"Ошибка загрузки message_map.json: {e}")
        return {}

def save_message_map():
    try:
        data = {}
        for key, value in message_mapping.items():
            admin_id, sent_message_id = key
            data[f"{admin_id}:{sent_message_id}"] = list(value)
        with open("message_map.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка сохранения message_map.json: {e}")

message_mapping = load_message_map()

# Инициализация бота с указанием parse_mode через DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def format_header(message: types.Message) -> str:
    """Формирует строку с информацией об отправителе."""
    msg_time = message.date.strftime("%Y-%m-%d %H:%M:%S")
    header = (
        f"<b>Новое сообщение от:</b> <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>\n"
        f"<b>ID:</b> {message.from_user.id}\n"
        f"<b>Время:</b> {msg_time}\n"
    )
    return header

def is_service_message(message: types.Message) -> bool:
    """
    Определяет, является ли сообщение служебным (например, уведомлением о вступлении в чат,
    изменении названия, фото и т.п.).
    """
    return bool(
        message.new_chat_members or
        message.left_chat_member or
        message.new_chat_title or
        message.new_chat_photo or
        message.delete_chat_photo or
        message.group_chat_created or
        message.supergroup_chat_created or
        message.channel_chat_created or
        message.migrate_from_chat_id or
        message.migrate_to_chat_id or
        message.pinned_message
    )

# Команда /start – приветствие для всех пользователей
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id in ADMINS:
        await message.answer(ADMIN_GREETING)
    else:
        await message.answer(USER_GREETING)

# Команда /ban – блокировка пользователя (только для администраторов)
@dp.message(Command("ban"))
async def ban_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    target_id = None
    # Если команда выполнена в ответ на сообщение
    if message.reply_to_message:
        key = (message.chat.id, message.reply_to_message.message_id)
        # Если сообщение является пересланным (есть mapping) – берём ID оригинального пользователя
        if key in message_mapping:
            target_id = message_mapping[key][0]
        else:
            # Если mapping отсутствует – возможно, сообщение не переслано ботом
            target_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) >= 2:
            try:
                target_id = int(parts[1])
            except ValueError:
                await message.answer(BAN_INVALID_FORMAT)
                return
        else:
            await message.answer(BAN_USAGE)
            return

    if target_id in banned_users:
        await message.answer(USER_ALREADY_BANNED)
        return

    banned_users.append(target_id)
    save_banned(banned_users)
    await message.answer(USER_BANNED.format(target_id=target_id))

# Команда /unban – разблокировка пользователя (только для администраторов)
@dp.message(Command("unban"))
async def unban_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    target_id = None
    if message.reply_to_message:
        key = (message.chat.id, message.reply_to_message.message_id)
        if key in message_mapping:
            target_id = message_mapping[key][0]
        else:
            target_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) >= 2:
            try:
                target_id = int(parts[1])
            except ValueError:
                await message.answer(UNBAN_INVALID_FORMAT)
                return
        else:
            await message.answer(UNBAN_USAGE)
            return

    if target_id not in banned_users:
        await message.answer(USER_NOT_BANNED)
        return

    banned_users.remove(target_id)
    save_banned(banned_users)
    await message.answer(USER_UNBANNED.format(target_id=target_id))

# Основной обработчик сообщений
@dp.message()
async def handle_message(message: types.Message):
    # Если сообщение служебное и отправлено обычным пользователем, отправляем приветствие и не пересылаем
    if is_service_message(message) and message.from_user.id not in ADMINS:
        await message.answer(USER_GREETING)
        return

    # Игнорируем сообщения от забаненных пользователей
    if message.from_user.id in banned_users:
        return

    # Если сообщение отправлено обычным пользователем (не администратором)
    if message.from_user.id not in ADMINS:
        current_ts = message.date.timestamp()
        last_ts = last_message_time.get(message.from_user.id)
        if last_ts and (current_ts - last_ts) < SLOW_MODE_INTERVAL:
            await message.answer(SLOW_MODE_WARNING)
            return
        last_message_time[message.from_user.id] = current_ts

        header = format_header(message)
        # Пересылаем сообщение всем администраторам
        for admin_id in ADMINS:
            try:
                if message.content_type == types.ContentType.TEXT:
                    sent = await bot.send_message(
                        admin_id,
                        f"{header}\n<b>Сообщение:</b>\n{message.text}",
                        disable_web_page_preview=True,
                    )
                else:
                    sent = await bot.copy_message(
                        chat_id=admin_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                        caption=header,
                    )
                # Сохраняем соответствие: ключ – (ID чата админа, ID сообщения бота), значение – (ID чата пользователя, ID оригинального сообщения)
                message_mapping[(admin_id, sent.message_id)] = (message.chat.id, message.message_id)
                save_message_map()
            except Exception as e:
                logging.error(ADMIN_FORWARD_ERROR.format(admin_id=admin_id, error=e))
        # Отправляем подтверждение пользователю
        await message.answer(USER_MESSAGE_ACCEPTED)
        return

    # Если сообщение от администратора – проверяем, что это ответ на сообщение пользователя
    if message.from_user.id in ADMINS and message.reply_to_message:
        key = (message.chat.id, message.reply_to_message.message_id)
        if key in message_mapping:
            user_chat_id, user_message_id = message_mapping[key]
            try:
                await bot.send_message(
                    chat_id=user_chat_id,
                    text=message.text,
                    reply_to_message_id=user_message_id,
                )
                logging.info(f"Ответ от админа {message.from_user.id} переслан пользователю {user_chat_id}")
            except Exception as e:
                logging.error(f"Ошибка при отправке ответа пользователю: {e}")

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
