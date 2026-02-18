#import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery, Message)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8551976563:AAHJfIQhJiuBE61YRoYobFn9I14VpopzL-o"       # Замените на токен вашего бота
ADMIN_ID = 8198445725                      # Ваш Telegram ID (администратор)

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)

# ===== ИНИЦИАЛИЗАЦИЯ =====
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== ХРАНИЛИЩЕ НАСТРОЕК (в памяти) =====
# Ключ - user_id администратора
config = {
    ADMIN_ID: {
        "source_chat_id": None,
        "target_chat_id": None,
        "forwarding_enabled": False
    }
}

# ===== FSM СОСТОЯНИЯ ДЛЯ НАСТРОЙКИ =====
class ConfigStates(StatesGroup):
    waiting_for_source = State()   # ожидание пересылки из исходной группы
    waiting_for_target = State()   # ожидание пересылки из целевой группы

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С КОНФИГОМ =====
def get_config(user_id):
    """Возвращает настройки пользователя или создаёт по умолчанию"""
    if user_id not in config:
        config[user_id] = {
            "source_chat_id": None,
            "target_chat_id": None,
            "forwarding_enabled": False
        }
    return config[user_id]

# ===== КЛАВИАТУРЫ =====
def main_menu_keyboard(user_id):
    """Главное меню с инлайн-кнопками"""
    cfg = get_config(user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Установить исходную группу", callback_data="set_source")
    builder.button(text="📤 Установить целевую группу", callback_data="set_target")
    builder.button(text="📋 Текущие настройки", callback_data="show_settings")
    if cfg["forwarding_enabled"]:
        builder.button(text="⏸️ Остановить пересылку", callback_data="disable")
    else:
        builder.button(text="▶️ Запустить пересылку", callback_data="enable")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(1)  # по одной кнопке в ряд
    return builder.as_markup()

def cancel_keyboard():
    """Кнопка отмены для режима ожидания"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()

# ===== ОБРАБОТЧИКИ =====

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "👋 Привет! Я бот для пересылки сообщений между группами.\n"
        "Используй кнопки ниже для настройки.",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )

# Команда /cancel (выход из режима ожидания)
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Не в режиме настройки.")
        return
    await state.clear()
    await message.answer(
        "Действие отменено. Возврат в главное меню.",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )

# Обработка инлайн-кнопок
@dp.callback_query(lambda c: True)
async def process_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id != ADMIN_ID:
        await callback.answer("⛔ Нет прав.")
        return

    data = callback.data
    cfg = get_config(user_id)

    if data == "set_source":
        await state.set_state(ConfigStates.waiting_for_source)
        await callback.message.edit_text(
            "📥 Перешлите любое сообщение из группы, которую вы хотите сделать **источником**.\n"
            "Убедитесь, что бот добавлен в эту группу и имеет права на чтение сообщений.\n"
            "Чтобы отменить, нажмите кнопку ниже.",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()

    elif data == "set_target":
        await state.set_state(ConfigStates.waiting_for_target)
        await callback.message.edit_text(
            "📤 Перешлите любое сообщение из группы, в которую вы хотите пересылать сообщения.\n"
            "Убедитесь, что бот добавлен в эту группу.\n"
            "Чтобы отменить, нажмите кнопку ниже.",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()

    elif data == "show_settings":
        source = cfg["source_chat_id"]
        target = cfg["target_chat_id"]
        enabled = cfg["forwarding_enabled"]
        status = "✅ Активна" if enabled else "⏸️ Остановлена"
        source_info = "не задана"
        target_info = "не задан"
        if source:
            try:
                chat = await bot.get_chat(source)
                source_info = f"{chat.title} (ID: {source})"
            except:
                source_info = f"ID: {source} (недоступен)"
        if target:
            try:
                chat = await bot.get_chat(target)
                target_info = f"{chat.title} (ID: {target})"
            except:
                target_info = f"ID: {target} (недоступен)"
        text = (
            f"📋 **Текущие настройки**\n\n"
            f"📥 Исходная группа: {source_info}\n"
            f"📤 Целевая группа: {target_info}\n"
            f"🔄 Пересылка: {status}"
        )
        await callback.message.edit_text(text, parse_mode="Markdown")
        # Возвращаем главное меню через некоторое время или добавляем кнопку "Назад"
        # Для простоты просто пришлём новое сообщение с меню
        await callback.message.answer("Меню управления:", reply_markup=main_menu_keyboard(user_id))
        await callback.answer()

    elif data == "enable":
        if not cfg["source_chat_id"] or not cfg["target_chat_id"]:
            await callback.answer("❌ Сначала задайте исходную и целевую группы.", show_alert=True)
            return
        cfg["forwarding_enabled"] = True
        await callback.message.edit_text("✅ Пересылка запущена.")
        await callback.message.answer("Меню управления:", reply_markup=main_menu_keyboard(user_id))
        await callback.answer()

    elif data == "disable":
        cfg["forwarding_enabled"] = False
        await callback.message.edit_text("⏸️ Пересылка остановлена.")
        await callback.message.answer("Меню управления:", reply_markup=main_menu_keyboard(user_id))
        await callback.answer()

    elif data == "help":
        help_text = (
            "❓ **Помощь**\n\n"
            "1. Добавьте бота в обе группы (источник и назначение).\n"
            "2. В группе-источнике бот должен быть администратором (чтобы читать сообщения).\n"
            "3. Используйте кнопки, чтобы задать группы:\n"
            "   • Нажмите «Установить исходную группу» и перешлите сообщение из неё.\n"
            "   • Нажмите «Установить целевую группу» и перешлите сообщение из неё.\n"
            "4. Запустите пересылку кнопкой «Запустить пересылку».\n\n"
            "Все новые сообщения из исходной группы будут автоматически пересылаться в целевую."
        )
        await callback.message.edit_text(help_text, parse_mode="Markdown")
        await callback.message.answer("Меню управления:", reply_markup=main_menu_keyboard(user_id))
        await callback.answer()

    elif data == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Действие отменено.")
        await callback.message.answer("Меню управления:", reply_markup=main_menu_keyboard(user_id))
        await callback.answer()

# Обработка пересланных сообщений (для установки групп)
@dp.message(ConfigStates.waiting_for_source)
async def process_source_forward(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        # Проверяем, доступен ли чат
        try:
            chat = await bot.get_chat(chat_id)
            config[user_id]["source_chat_id"] = chat_id
            await message.answer(
                f"✅ Исходная группа установлена: {chat.title} (ID: {chat_id})",
                reply_markup=main_menu_keyboard(user_id)
            )
            await state.clear()
        except Exception as e:
            await message.answer(
                f"❌ Не удалось получить информацию о группе. Убедитесь, что бот добавлен в неё.\nОшибка: {e}",
                reply_markup=main_menu_keyboard(user_id)
            )
            await state.clear()
    else:
        await message.answer("❌ Это не пересланное сообщение из группы. Попробуйте ещё раз или нажмите Отмена.")

@dp.message(ConfigStates.waiting_for_target)
async def process_target_forward(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        try:
            chat = await bot.get_chat(chat_id)
            config[user_id]["target_chat_id"] = chat_id
            await message.answer(
                f"✅ Целевая группа установлена: {chat.title} (ID: {chat_id})",
                reply_markup=main_menu_keyboard(user_id)
            )
            await state.clear()
        except Exception as e:
            await message.answer(
                f"❌ Не удалось получить информацию о группе. Убедитесь, что бот добавлен в неё.\nОшибка: {e}",
                reply_markup=main_menu_keyboard(user_id)
            )
            await state.clear()
    else:
        await message.answer("❌ Это не пересланное сообщение из группы. Попробуйте ещё раз или нажмите Отмена.")

# Обработка всех остальных сообщений (пересылка)
@dp.message()
async def forward_messages(message: Message):
    # Проверяем, что сообщение пришло из группы (chat_id < 0)
    if message.chat.type not in ["group", "supergroup"]:
        return

    cfg = config.get(ADMIN_ID)
    if not cfg or not cfg["forwarding_enabled"]:
        return

    # Если сообщение из исходной группы
    if message.chat.id == cfg["source_chat_id"]:
        target_id = cfg["target_chat_id"]
        if target_id:
            try:
                await message.forward(chat_id=target_id)
            except Exception as e:
                logging.error(f"Ошибка пересылки: {e}")
                # Можно уведомить админа (опционально)
                # await bot.send_message(ADMIN_ID, f"Ошибка пересылки: {e}")

# ===== ЗАПУСК =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())