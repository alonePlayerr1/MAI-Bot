# app/audio_processor.py
import logging
from google.cloud import speech
from google.api_core.exceptions import GoogleAPICallError, InvalidArgument
import config

# Инициализация клиента (без изменений)
speech_client = None
if config.credentials_exist:
    try:
        speech_client = speech.SpeechClient.from_service_account_json(config.GOOGLE_APP_CREDENTIALS)
        logging.info("Google Cloud Speech client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Google Cloud Speech client: {e}", exc_info=True)
        speech_client = None

# ---> Функция теперь принимает sample_rate <---
def transcribe_audio_gcs(gcs_uri: str, sample_rate: int) -> str | None:
    """
    Initiates asynchronous speech recognition for a file in GCS (expects OGG Opus).
    Uses the provided sample_rate.
    Returns the transcript or None if an error occurs.
    """
    if not speech_client:
        logging.error("Cannot transcribe audio: Speech client not initialized.")
        return None
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        logging.error(f"Invalid GCS URI provided for transcription: {gcs_uri}")
        return None
    # Проверка на валидность sample_rate (хотя бы > 0)
    if not sample_rate or sample_rate <= 0:
         logging.error(f"Invalid sample_rate ({sample_rate}) provided for transcription of {gcs_uri}")
         # Можно попробовать стандартное значение или вернуть ошибку
         # sample_rate = 16000 # Вариант: использовать дефолтное, если пришло некорректное
         # logging.warning(f"Using default sample rate {sample_rate} instead.")
         return None # Лучше вернуть ошибку, если частота не определилась

    logging.info(f"Starting transcription request for {gcs_uri} with sample rate {sample_rate} Hz (assuming OGG Opus format)")

    audio = speech.RecognitionAudio(uri=gcs_uri)

    # --- Используем переданную частоту в конфигурации ---
    recognition_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        # ---> Используем переданный sample_rate <---
        sample_rate_hertz=sample_rate,
        language_code="ru-RU",
        enable_automatic_punctuation=True,
        profanity_filter=False,
        # model="latest_long", # Пока уберем модель, чтобы проверить только частоту
    )
    # --- Конец конфигурации ---

    operation = None
    try:
        logging.debug(f"Sending S2T request for {gcs_uri} with config: {recognition_config}")
        operation = speech_client.long_running_recognize(config=recognition_config, audio=audio)
        op_name = operation.operation.name
        logging.info(f"Waiting for transcription operation [{op_name}] to complete...")

        response = operation.result(timeout=5400) # 90 минут
        logging.debug(f"S2T operation [{op_name}] completed for {gcs_uri}")

        if not response.results:
            logging.warning(f"Transcription for {gcs_uri} resulted in no results.")
            return ""

        transcript = "".join(
            result.alternatives[0].transcript for result in response.results if result.alternatives
        )

        if not transcript:
             logging.warning(f"Transcription finished but resulted in empty transcript for {gcs_uri}.")
             return ""

        logging.info(f"Transcription successful for {gcs_uri}. Transcript length: {len(transcript)}")
        return transcript

    except InvalidArgument as e:
        op_name = operation.operation.name if operation else 'N/A'
        # Логируем ошибку и конфигурацию, которая ее вызвала
        logging.error(f"S2T Invalid Argument Error during transcription [{op_name}] for {gcs_uri}: {e}", exc_info=False) # Убрали exc_info для краткости
        logging.error(f"RecognitionConfig used: {recognition_config}")
        if hasattr(e, 'details') and e.details: logging.error(f"S2T Error details: {e.details}")
        return None
    except GoogleAPICallError as e:
        op_name = operation.operation.name if operation else 'N/A'
        logging.error(f"S2T API call error during transcription [{op_name}] for {gcs_uri}: {e}", exc_info=True)
        if hasattr(e, 'details') and e.details: logging.error(f"S2T Error details: {e.details}")
        return None
    except Exception as e:
        op_name = operation.operation.name if operation else 'N/A'
        logging.error(f"An unexpected error occurred during transcription [{op_name}] for {gcs_uri}: {e}", exc_info=True)
        return None