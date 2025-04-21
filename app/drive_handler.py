# app/drive_handler.py
import io
import logging
import os
import re
import tempfile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

import config

# Область доступа для Google Drive API (только чтение)
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def _get_drive_service():
    """Инициализирует и возвращает сервис Google Drive API."""
    try:
        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_APP_CREDENTIALS, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds, static_discovery=False)
        logging.info("Google Drive service initialized successfully.")
        return service
    except Exception as e:
        logging.error(f"Failed to initialize Google Drive service: {e}", exc_info=True)
        return None

def extract_file_id_from_link(link: str) -> str | None:
    """Извлекает ID файла из различных форматов ссылок Google Drive."""
    # Паттерны для извлечения ID
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)', # /file/d/ID/...
        r'id=([a-zA-Z0-9_-]+)',     # ?id=ID или open?id=ID
        r'/d/([a-zA-Z0-9_-]+)/'     # /d/ID/edit...
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            file_id = match.group(1)
            logging.info(f"Extracted Google Drive File ID: {file_id}")
            return file_id
    logging.warning(f"Could not extract File ID from link: {link}")
    return None

def download_file_from_drive(drive_link: str) -> str | None:
    """
    Скачивает файл из Google Drive по ссылке и сохраняет во временный файл.
    Возвращает путь к временному файлу или None в случае ошибки.
    """
    service = _get_drive_service()
    if not service:
        return None

    file_id = extract_file_id_from_link(drive_link)
    if not file_id:
        logging.error("Invalid Google Drive link: File ID could not be extracted.")
        return None

    # Создаем временный файл для скачивания
    try:
        # Используем NamedTemporaryFile, чтобы получить имя, но управляем удалением вручную
        with tempfile.NamedTemporaryFile(mode='wb', suffix="_drive_download", dir=config.TEMP_FOLDER, delete=False) as f:
            temp_file_path = f.name
            logging.info(f"Attempting to download Drive file ID {file_id} to {temp_file_path}")

            request = service.files().get_media(fileId=file_id)
            # Используем MediaIoBaseDownload для скачивания больших файлов чанками
            downloader = MediaIoBaseDownload(f, request, chunksize=10*1024*1024) # Чанк 10MB

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logging.info(f"Download progress: {int(status.progress() * 100)}%")
                else:
                    logging.info("Preparing download...") # Статус может быть None в начале

            logging.info(f"Successfully downloaded file from Google Drive to {temp_file_path}")
            return temp_file_path

    except HttpError as error:
        logging.error(f"An HttpError occurred while downloading from Drive: {error}", exc_info=True)
        # Пытаемся удалить временный файл, если он был создан и произошла ошибка
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
             try: os.remove(temp_file_path)
             except OSError: pass
        if error.resp.status == 404:
            logging.error(f"File not found on Google Drive (ID: {file_id}). Check the link and permissions.")
        elif error.resp.status == 403:
            logging.error(f"Permission denied for Google Drive file (ID: {file_id}). Ensure 'Anyone with the link can view' or share with service account: {config.GOOGLE_APP_CREDENTIALS}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during Drive download: {e}", exc_info=True)
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
             try: os.remove(temp_file_path)
             except OSError: pass
        return None