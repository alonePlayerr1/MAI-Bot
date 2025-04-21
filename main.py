# main.py
import asyncio
import logging
import sys

# --- Aiogram Imports ---
from aiogram import Bot, Dispatcher
# ---> Добавляем импорт DefaultBotProperties <---
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# --- Project Imports ---
import config
from app import telegram_handler_aiogram

async def main():
    # Настройка логирования
    config.setup_logging_aiogram()
    logging.info("="*20 + " Starting MAI Bot (aiogram)... " + "="*20)

    # Проверка токена
    if not config.TELEGRAM_BOT_TOKEN:
        logging.critical("Telegram Bot Token is missing in .env file. Exiting.")
        sys.exit(1)

    # Инициализация бота и диспетчера
    storage = MemoryStorage()

    # ---> ИЗМЕНЕННАЯ СТРОКА ИНИЦИАЛИЗАЦИИ BOT <---
    # Устанавливаем parse_mode через DefaultBotProperties
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML") # Используем HTML по умолчанию
    )
    # ---> КОНЕЦ ИЗМЕНЕНИЯ <---

    dp = Dispatcher(storage=storage)

    # Регистрация обработчиков (роутеров)
    await telegram_handler_aiogram.register_aiogram_handlers(dp, bot)

    # Удаление вебхука перед запуском поллинга
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook deleted successfully or was not set.")
    except Exception as e:
        logging.warning(f"Could not delete webhook: {e}. Skipping.")

    # Запуск поллинга
    logging.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        logging.info("Polling stopped. Closing bot session...")
        await bot.session.close()
        logging.info("Bot session closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually!")
    except Exception as e:
        logging.critical(f"Bot failed critically outside main loop: {e}", exc_info=True)
        sys.exit(1)