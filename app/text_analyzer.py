# app/text_analyzer.py
import logging
import asyncio
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold

import config # Нужен для GCP_PROJECT_ID, GCP_LOCATION

# --- Инициализация Vertex AI ---
model = None
try:
    # Используем значения из config.py
    if not config.GCP_PROJECT_ID or not config.GCP_LOCATION:
        raise ValueError("GCP_PROJECT_ID или GCP_LOCATION не заданы в config.py")

    vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
    logging.info(f"Vertex AI initialized for project '{config.GCP_PROJECT_ID}' in location '{config.GCP_LOCATION}'.")

    # Выбираем модель (gemini-1.0-pro или gemini-1.5-flash-001)
    # Убедись, что она доступна в твоем регионе config.GCP_LOCATION
    MODEL_NAME = "gemini-1.0-pro"
    model = GenerativeModel(MODEL_NAME)
    logging.info(f"Using Vertex AI model: {MODEL_NAME}")

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
    generation_config = GenerationConfig(temperature=0.3)

except Exception as e:
    logging.error(f"Failed to initialize Vertex AI or model: {e}", exc_info=True)
    # model останется None

# --- Функция для вызова API (синхронная) ---
def generate_content_sync(prompt: str, description: str) -> str | None:
    """Выполняет один запрос к модели Gemini."""
    if not model: return None # Если модель не инициализировалась
    try:
        logging.info(f"Sending request to Vertex AI for: {description}")
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        logging.debug(f"Raw response for {description}: {response}") # Логируем полный ответ для отладки

        # Проверка на блокировку контента или пустой ответ
        if not response.candidates or not response.candidates[0].content.parts:
            try:
                block_reason = response.candidates[0].finish_reason
                safety_ratings = response.candidates[0].safety_ratings
                logging.warning(f"Vertex AI response for {description} blocked or empty. Reason: {block_reason}. Ratings: {safety_ratings}")
            except Exception:
                logging.warning(f"Received unexpected empty response structure for {description}. Response: {response}")
            return None # Возвращаем None при блокировке или пустом ответе

        generated_text = response.text.strip()
        if generated_text:
            logging.info(f"Received response for {description} (length: {len(generated_text)} chars)")
            return generated_text
        else:
            logging.warning(f"Received empty text response for {description} despite valid candidate.")
            return None

    except Exception as e:
        logging.error(f"Error calling Vertex AI for {description}: {e}", exc_info=True)
        return None # Возвращаем None при ошибке API

# --- Основная функция анализа (синхронная, для вызова через to_thread) ---
def analyze_text_sync(transcript: str) -> dict:
    """Анализирует транскрипт: конспекты для преподавателя/студента, ключевые слова."""
    results = {
        "teacher_summary": None, # Используем None для индикации ошибки
        "student_summary": None,
        "keywords": None
    }
    if not model:
        logging.error("Vertex AI model not initialized. Cannot analyze text.")
        return results
    if not transcript or not transcript.strip():
        logging.warning("Received empty transcript for analysis.")
        return results # Нет смысла анализировать пустоту

    logging.info(f"Starting text analysis for transcript (length: {len(transcript)} chars)...")

    # Ограничение на длину транскрипта (примерное, зависит от модели, 1.0 Pro обычно ~30k токенов)
    # Один токен примерно 4 символа на английском, на русском может быть меньше (1-2 символа)
    # Возьмем с запасом, например, 80 000 символов (~32k токенов)
    MAX_CHARS = 80000
    if len(transcript) > MAX_CHARS:
         logging.warning(f"Transcript length ({len(transcript)}) exceeds limit ({MAX_CHARS}). Truncating.")
         transcript = transcript[:MAX_CHARS]

    # --- Промпты ---
    # (Можно вынести их в отдельный файл или константы)
    prompt_teacher = f"""Создай краткий конспект (summary) следующего транскрипта лекции для преподавателя. Выдели основные темы, структуру и ключевые выводы."""