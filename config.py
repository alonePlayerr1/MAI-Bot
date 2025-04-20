# config.py
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file located in the project root
dotenv_path = os.path.join(os.path.dirname(__file__), '.env') # Correctly locate .env
load_dotenv(dotenv_path=dotenv_path)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_APP_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')

# Basic validation
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file.")
if not GOOGLE_APP_CREDENTIALS:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not found in .env file.")
if not GCS_BUCKET_NAME:
    raise ValueError("GCS_BUCKET_NAME not found in .env file.")

# Check credentials file existence only after path is loaded
credentials_exist = os.path.exists(GOOGLE_APP_CREDENTIALS)
if not credentials_exist:
     # Log warning here, but allow startup for potential local testing without cloud
     pass # Logging will be configured later

# Other configurations based on your structure
# Assuming script runs from MAI_bot directory or paths are relative to config.py location
PROJECT_ROOT = os.path.dirname(__file__)
TEMP_FOLDER = os.path.join(PROJECT_ROOT, 'temp/')
LOG_FOLDER = os.path.join(PROJECT_ROOT, 'logs/')
LOG_FILE = os.path.join(LOG_FOLDER, 'bot.log')
LOG_LEVEL = logging.INFO # Change to logging.DEBUG for more details
DATE_FORMAT = "%d.%m.%Y"
TIME_FORMAT = "%H:%M"
DATETIME_SPLIT_CHAR = '-'
METADATA_SEPARATOR = '_'

# Ensure temp and log directories exist
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# Conversation states (can be defined here or in telegram_handler)
STATE_WAITING_DISCIPLINE = 1
STATE_WAITING_TEACHER = 2
STATE_WAITING_DATETIME = 3
STATE_WAITING_AUDIO = 4

# Function to check credentials existence after logging is set up
def check_credentials_file():
    if not credentials_exist:
        logging.warning(f"Credentials file not found at: {GOOGLE_APP_CREDENTIALS}. Google Cloud services may fail.")