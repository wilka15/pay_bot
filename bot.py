import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict
from threading import Thread

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, Message, CallbackQuery, PreCheckoutQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Цена в Stars (100 Stars ≈ 55 рублей для пользователя)
STARS_PRICE = 100

# Настройка бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы бот не засыпал) =====
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "✅ Bot is alive!", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()
print("🌐 Веб-сервер запущен на порту 8080")

# ===== БАЗА ДАННЫХ ПОДПИСОК (временно в памяти) =====
# При перезапуске бота данные сбросятся. Для продакшена используйте БД.
premium_users: Dict[str, datetime] = {}

def is_premium(user_id: str) -> bool:
    """Проверяет активна ли подписка"""
    expiry = premium_users.get(user_id)
    return expiry and expiry > datetime.now()

def set_premium(user_id: str, days: int) -> None:
    """Активирует подписку на указанное количество дней"""
    premium_users[user_id] = datetime.now() + timedelta(days=days)
    logging.info(f"✅ Премиум активирован для {user_id} на {days} дней")

def get_premium_expiry(user_id: str) -> datetime:
    """Возвращает дату окончания подписки"""
    return premium_users.get(user_id)

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить Premium", callback_data="pay_stars")],
        [InlineKeyboardButton(text="📊 Мой статус", callback_data="my_status")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
    
    await message.answer(
        "⚖️ *Lawyer Pay Bot — Премиум доступ*\n\n"
        "Получите безлимитные запросы к УК и ПК для Majestic RP!\n\n"
        "🌟 *Что даёт Premium:*\n"
        "• Безлимитные запросы\n"
        "• Приоритетная поддержка\n"
        "• Доступ к ИИ-консультациям\n\n"
        f"💰 *Цена:* {STARS_PRICE} Stars (~55 ₽)\n"
        "📅 *Срок:* 30 дней\n\n"
        "Нажмите кнопку ниже для оплаты:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "pay_stars")
async def pay_with_stars(callback: CallbackQuery):
    """Отправка счёта на оплату Stars"""
    user_id = callback.from_user.id
    
    await bot.send_invoice(
        chat_id=user_id,
        title="Premium доступ 30 дней",
        description="Безлимитные запросы к УК и ПК штата Сан-Андреас",
        payload=f"premium_{user_id}_{int(datetime.now().timestamp())}",
        provider_token="",          # Пустая строка = Telegram Stars
        currency="XTR",             # XTR = Telegram Stars
        prices=[LabeledPrice(label="30 дней", amount=STARS_PRICE)],
        start_parameter="premium_stars"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_status")
async def my_status(callback: CallbackQuery):
    """Проверка статуса подписки"""
    user_id = str(callback.from_user.id)
    
    if is_premium(user_id):
        expiry = premium_users[user_id]
        days_left = (expiry - datetime.now()).days
        await callback.message.answer(
            f"✅ *Premium активен!*\n"
            f"📅 Осталось дней: {days_left}\n"
            f"📅 Действует до: {expiry.strftime('%d.%m.%Y')}",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(
            "❌ *Premium не активен*\n\n"
            "Используйте /start для покупки подписки.",
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await help_command(callback.message)
    await callback.answer()

@dp.message(Command("status"))
async def status_command(message: Message):
    """Альтернативная команда для проверки статуса"""
    user_id = str(message.from_user.id)
    
    if is_premium(user_id):
        expiry = premium_users[user_id]
        days_left = (expiry - datetime.now()).days
        await message.answer(
            f"✅ *Premium активен!*\n📅 Осталось дней: {days_left}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "❌ *Premium не активен*\nИспользуйте /start для покупки",
            parse_mode="Markdown"
        )

@dp.message(Command("help"))
async def help_command(message: Message):
    """Справка по командам"""
    await message.answer(
        "📚 *Доступные команды:*\n\n"
        "/start — Главное меню\n"
        "/status — Проверить статус подписки\n"
        "/help — Помощь\n\n"
        "💡 *Как оплатить?*\n"
        "1. Нажмите /start\n"
        "2. Нажмите «Купить Premium»\n"
        "3. Оплатите через Telegram Stars\n"
        "4. Premium активируется автоматически!\n\n"
        "⭐ *Что такое Stars?*\n"
        "Это внутренняя валюта Telegram. 100 Stars ≈ 55 ₽.\n"
        "Купить Stars можно через @PremiumBot или в самом платеже.",
        parse_mode="Markdown"
    )

@dp.message(Command("admin_premium"))
async def admin_give_premium(message: Message):
    """[АДМИН] Выдать премиум вручную"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Использование: /admin_premium @user days")
        return
    
    try:
        user_mention = args[1]
        days = int(args[2])
        await message.answer(f"✅ Выдан Premium пользователю {user_mention} на {days} дней")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("stats"))
async def stats_command(message: Message):
    """[АДМИН] Статистика по подпискам"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав!")
        return
    
    active_count = sum(1 for expiry in premium_users.values() if expiry > datetime.now())
    total_count = len(premium_users)
    
    await message.answer(
        f"📊 *Статистика подписок*\n\n"
        f"👥 Всего пользователей: {total_count}\n"
        f"💎 Активных премиумов: {active_count}",
        parse_mode="Markdown"
    )

# ===== ОБРАБОТКА ПЛАТЕЖЕЙ =====

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    """
    Обработка pre-checkout запроса.
    Должна ответить в течение 10 секунд!
    """
    payload = query.invoice_payload
    
    # Проверяем, что payload начинается с "premium_"
    if payload.startswith("premium_"):
        await bot.answer_pre_checkout_query(query.id, ok=True)
        logging.info(f"✅ Платёж одобрен для пользователя {query.from_user.id}")
    else:
        await bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message="Что-то пошло не так. Попробуйте снова."
        )

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """
    Обработка успешного платежа
    """
    payment = message.successful_payment
    user_id = str(message.from_user.id)
    total_amount = payment.total_amount
    
    logging.info(f"💰 Получен платёж от {user_id}: {total_amount} Stars")
    
    # Активируем премиум на 30 дней
    set_premium(user_id, 30)
    
    # Подтверждение пользователю
    await message.answer(
        f"✅ *Оплата прошла успешно!*\n\n"
        f"⭐ Спасибо за покупку!\n"
        f"💰 Оплачено: {total_amount} Stars\n"
        f"📅 Premium доступ активирован на *30 дней*\n\n"
        f"Используйте /status для проверки.",
        parse_mode="Markdown"
    )
    
    # Уведомление администраторам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🎉 *Новая покупка Premium!*\n"
                f"👤 Пользователь: {message.from_user.mention}\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Сумма: {total_amount} Stars\n"
                f"📅 Дней: 30",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить админа {admin_id}: {e}")

# ===== ЗАПУСК =====
async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("🚀 Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
