# config.py
import os
import logging
from dotenv import load_dotenv
from aiogram.fsm.state import State, StatesGroup # Убедись, что это импортировано

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_APP_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
# ---> Добавь сюда свои Project ID и Location для Vertex AI <---
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', "canvas-figure-456707-v1") # Замени или добавь в .env
GCP_LOCATION = os.getenv('GCP_LOCATION', "us-central1") # Замени или добавь в .env

if not TELEGRAM_BOT_TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN не найден")
if not GOOGLE_APP_CREDENTIALS: raise ValueError("GOOGLE_APPLICATION_CREDENTIALS не найден")
if not GCS_BUCKET_NAME: raise ValueError("GCS_BUCKET_NAME не найден")
if not GCP_PROJECT_ID: raise ValueError("GCP_PROJECT_ID не найден")
if not GCP_LOCATION: raise ValueError("GCP_LOCATION не найден")


credentials_exist = False
if GOOGLE_APP_CREDENTIALS:
    credentials_exist = os.path.exists(GOOGLE_APP_CREDENTIALS)

PROJECT_ROOT = os.path.dirname(__file__)
TEMP_FOLDER = os.path.join(PROJECT_ROOT, 'temp/')
LOG_FOLDER = os.path.join(PROJECT_ROOT, 'logs/')
LOG_FILE = os.path.join(LOG_FOLDER, 'bot.log')
LOG_LEVEL = logging.INFO
DATE_FORMAT = "%d.%m.%Y"
TIME_FORMAT = "%H:%M"
DATETIME_SPLIT_CHAR = '-'
METADATA_SEPARATOR = '_'
SKIP_S2T_FOR_DEBUG = True # Флаг для пропуска S2T

os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# --- Состояния для основного процесса регистрации ---
class LectureRegistration(StatesGroup):
    waiting_discipline = State()
    waiting_teacher = State()
    waiting_datetime = State()
    waiting_drive_link = State()
    waiting_confirmation = State()
    waiting_correction_choice = State()
    correcting_discipline = State()
    correcting_teacher = State()
    correcting_datetime = State()

# ---> КЛАСС СОСТОЯНИЙ ДЛЯ РЕЖИМА РАЗРАБОТЧИКА <---
class DevProcessing(StatesGroup):
    waiting_dev_discipline = State()
    waiting_dev_teacher = State()
    waiting_dev_datetime = State()
    waiting_transcript_txt = State()
# -------------------------------------------------------

def setup_logging_aiogram():
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
        handlers=[ logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()] )
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('pydub').setLevel(logging.INFO)
    if not GOOGLE_APP_CREDENTIALS: logging.warning("Путь к GOOGLE_APPLICATION_CREDENTIALS не указан.")
    elif not credentials_exist: logging.warning(f"Файл учетных данных не найден: {GOOGLE_APP_CREDENTIALS}.")
    else: logging.info(f"Файл учетных данных найден: {GOOGLE_APP_CREDENTIALS}")
    logging.info("="*20 + " Aiogram Logging setup complete " + "="*20)
