import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Загружаем переменные окружения
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

STARS_AMOUNT = 100  # 100 Stars ≈ 55 ₽

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# WEBHOOK настройки для Render
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost')}{WEBHOOK_PATH}"

# Простая база подписок (в реальном проекте используйте БД)
premium_users = {}  # user_id -> expiry_date

def is_premium(user_id: str) -> bool:
    if user_id not in premium_users:
        return False
    expiry = premium_users[user_id]
    return expiry > datetime.now()

def add_premium(user_id: str, days: int):
    expiry = datetime.now() + timedelta(days=days)
    premium_users[user_id] = expiry
    print(f"💎 Премиум выдан {user_id} до {expiry.strftime('%Y-%m-%d')}")

# === ОБРАБОТЧИКИ КОМАНД ===

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "⚖️ *Юридический помощник для Majestic RP*\n\n"
        "📚 *Команды:*\n"
        "/premium - Купить Premium доступ (30 дней)\n"
        "/status - Проверить статус\n"
        "/help - Помощь",
        parse_mode="Markdown"
    )

@dp.message(Command("premium"))
async def premium_subscription(message: Message):
    user_id = message.from_user.id
    
    prices = [LabeledPrice(label="Premium доступ 30 дней", amount=STARS_AMOUNT)]
    
    await bot.send_invoice(
        chat_id=user_id,
        title="💎 Premium доступ",
        description="Безлимитные запросы к УК и ПК на 30 дней",
        payload=f"premium_{user_id}_{int(datetime.now().timestamp())}",
        provider_token="",
        currency="XTR",
        prices=prices,
        need_name=False,
        need_phone_number=False,
        need_email=False,
        start_parameter="premium_payment"
    )

@dp.pre_checkout_query(lambda query: True)
async def pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = str(message.from_user.id)
    payment_info = message.successful_payment
    
    add_premium(user_id, 30)
    
    await message.answer(
        f"✅ *Оплата прошла успешно!*\n"
        f"Premium доступ активирован на 30 дней.\n"
        f"Списано: {payment_info.total_amount // 100} Stars\n\n"
        f"Используйте /status для проверки подписки.",
        parse_mode="Markdown"
    )
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🎉 Пользователь {message.from_user.mention} купил Premium!\nID: {user_id}")
        except:
            pass

@dp.message(Command("status"))
async def check_status(message: Message):
    user_id = str(message.from_user.id)
    
    if is_premium(user_id):
        expiry = premium_users[user_id]
        days_left = (expiry - datetime.now()).days
        await message.answer(f"✅ *Premium активен*\n📅 Осталось дней: {days_left}", parse_mode="Markdown")
    else:
        await message.answer("❌ *Premium не активен*\nИспользуйте /premium для оплаты.", parse_mode="Markdown")

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📚 *Доступные команды:*\n\n"
        "/start - Начать\n"
        "/premium - Купить Premium (100 Stars ≈ 55 ₽)\n"
        "/status - Проверить статус\n"
        "/help - Помощь",
        parse_mode="Markdown"
    )

@dp.message(Command("admin_premium"))
async def admin_give_premium(message: Message):
    """Скрытая команда для выдачи премиума админом (только для ADMIN_IDS)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав")
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Использование: /admin_premium @пользователь 30")
        return
    
    # Здесь логика выдачи премиума по username
    await message.answer("✅ (Добавьте логику выдачи по username)")

# === НАСТРОЙКА WEBHOOK ДЛЯ RENDER ===

async def on_startup():
    """При запуске бота устанавливаем webhook"""
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown():
    """При остановке бота удаляем webhook"""
    await bot.delete_webhook()
    print("❌ Webhook удалён")

def main():
    # Запуск веб-приложения с webhook
    app = web.Application()
    
    # Обработчик webhook
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настройка событий старта/остановки
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Запуск веб-сервера
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
