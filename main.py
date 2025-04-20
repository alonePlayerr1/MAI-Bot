# main.py
import telebot
import logging
import config # Use config directly
from app import utils
from app import telegram_handler # Import the handlers module

if __name__ == "__main__":
    # Setup logging first - reads config internally
    utils.setup_logging()
    logging.info("Starting MAI Bot...")

    # Validate config essentials needed for startup
    if not config.TELEGRAM_BOT_TOKEN:
         logging.critical("Telegram Bot Token is missing. Check .env file. Exiting.")
         exit(1)
    # Credentials file existence check happens in utils.setup_logging() via config

    # Initialize Bot
    try:
        bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)
        bot_info = bot.get_me()
        logging.info(f"TeleBot instance created for bot: {bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logging.critical(f"Failed to initialize TeleBot: {e}", exc_info=True)
        exit(1)


    # Register Handlers from the dedicated module
    telegram_handler.register_handlers(bot)

    # Start Polling
    logging.info("Bot polling started...")
    try:
        # Use non_stop=True for continuous running, interval for polling frequency
        # Consider adding exception handling within polling loop if needed
        bot.polling(non_stop=True, interval=1, timeout=60)
    except Exception as e:
        logging.critical(f"Bot polling failed critically: {e}", exc_info=True)
        # Consider adding restart logic here if needed or notifying admin