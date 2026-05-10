import asyncio
import logging
import os
from aiohttp import web
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from models.database import init_db
from handlers import register, catalog, cart, orders_client, profile
from handlers import admin_orders, admin_products, admin_clients, admin_settings, admin_invoice

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Простий HTTP сервер щоб Render думав що сервіс живий
async def health(request):
    return web.Response(text="SuperCRM Bot is running!")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ HTTP сервер запущено на порту {port}")

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не вказано у .env файлі!")

    await init_db()
    logger.info("✅ База даних ініціалізована")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(register.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(orders_client.router)
    dp.include_router(profile.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_products.router)
    dp.include_router(admin_clients.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_invoice.router)

    # Запускаємо HTTP сервер і бота одночасно
    await start_web()
    logger.info("🚀 SuperCRM Bot запущено!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
