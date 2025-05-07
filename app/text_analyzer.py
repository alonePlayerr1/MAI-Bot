# app/text_analyzer.py
import logging
import asyncio
import vertexai # Оставляем
from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold

import config # Нужен для GCP_PROJECT_ID, GCP_LOCATION

# --- Инициализация Vertex AI ---
model = None
vertex_ai_initialized = False
safety_settings_global = None
generation_config_global = None

try:
    if not config.GCP_PROJECT_ID or not config.GCP_LOCATION:
        raise ValueError("GCP_PROJECT_ID или GCP_LOCATION не заданы в config.py. Проверьте эти значения.")

    # ---> УБРАНА ПРОВЕРКА if not vertexai.global_config._project: <---
    # Просто вызываем init. Библиотека сама разберется, была ли уже инициализация.
    vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
    logging.info(f"Vertex AI initialized (or reconfirmed) for project '{config.GCP_PROJECT_ID}' in location '{config.GCP_LOCATION}'.")

    MODEL_NAME = "gemini-2.5-pro-preview-05-06" # Или "gemini-1.5-flash-001"
    model = GenerativeModel(MODEL_NAME)
    logging.info(f"Using Vertex AI model: {MODEL_NAME}")

    safety_settings_global = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
    generation_config_global = GenerationConfig(
        temperature=0.3,
        # max_output_tokens=2048
    )
    vertex_ai_initialized = True

except Exception as e:
    logging.error(f"CRITICAL: Failed to initialize Vertex AI or model: {e}", exc_info=True)
    # model останется None, vertex_ai_initialized останется False

# --- Функция для одного вызова API (синхронная) ---
def _generate_content_sync(prompt_text: str, task_description: str) -> str | None:
    """Выполняет один синхронный запрос к модели Gemini."""
    if not vertex_ai_initialized or not model:
        logging.error(f"Vertex AI model not available for task: {task_description}")
        return None
    try:
        logging.info(f"Sending request to Vertex AI for: {task_description} (prompt length: {len(prompt_text)} chars)")
        response = model.generate_content(
            prompt_text,
            generation_config=generation_config_global,
            safety_settings=safety_settings_global,
        )
        logging.debug(f"Raw response for {task_description}: {response}")

        if not response.candidates or not response.candidates[0].content.parts:
            block_reason_info = "Unknown reason or no content."
            try:
                candidate = response.candidates[0]
                block_reason_info = f"Reason: {candidate.finish_reason}."
                if hasattr(candidate, 'safety_ratings'):
                     block_reason_info += f" Ratings: {candidate.safety_ratings}"
            except Exception: pass # Игнорируем ошибки при попытке получить детали блокировки
            logging.warning(f"Vertex AI response for {task_description} blocked or empty. {block_reason_info}")
            return None

        generated_text = response.text.strip()
        if generated_text:
            logging.info(f"Received response for {task_description} (length: {len(generated_text)} chars)")
            return generated_text
        else:
            logging.warning(f"Received empty text response for {task_description} despite valid candidate.")
            return None
    except Exception as e:
        logging.error(f"Error calling Vertex AI for {task_description}: {e}", exc_info=True)
        return None

# --- Основная функция анализа (синхронная, для to_thread) ---
def analyze_text_sync(transcript: str, discipline_name: str = "не указана") -> dict:
    """
    Анализирует транскрипт: конспекты для преподавателя/студента, ключевые слова.
    """
    # Инициализируем результаты с сообщениями об ошибках по умолчанию
    results = {
        "teacher_summary": "Не удалось создать конспект для преподавателя (ошибка инициализации или API).",
        "student_summary": "Не удалось создать конспект для студента (ошибка инициализации или API).",
        "keywords": ["ошибка анализа"]
    }

    if not vertex_ai_initialized or not model:
        logging.error("Vertex AI model not initialized. Cannot analyze text. Returning default error messages.")
        return results
    if not transcript or not transcript.strip():
        logging.warning("Received empty transcript for analysis.")
        results["teacher_summary"] = "Транскрипт пуст. Конспект не создан."
        results["student_summary"] = "Транскрипт пуст. Конспект не создан."
        results["keywords"] = ["пустой транскрипт"]
        return results

    logging.info(f"Starting text analysis for transcript (discipline: {discipline_name}, length: {len(transcript)} chars)...")

    # Ограничение на длину транскрипта (важно для Gemini, особенно для 1.0 Pro)
    # 1 токен ~ 4 символа en, для ru ~ 1-3 символа. Модель gemini-1.0-pro имеет лимит ~30k токенов.
    # Возьмем лимит символов с запасом, например, 60000 символов (примерно 20-30k токенов)
    # Для gemini-1.5-flash лимит контекста намного больше (до 1М токенов)
    MAX_CHARS_FOR_PROMPT = 60000
    if len(transcript) > MAX_CHARS_FOR_PROMPT:
        logging.warning(f"Transcript length ({len(transcript)}) exceeds limit ({MAX_CHARS_FOR_PROMPT}). Truncating.")
        transcript = transcript[:MAX_CHARS_FOR_PROMPT]
        # Можно добавить сообщение пользователю, что текст был сокращен

    # --- Промпты ---
    prompt_teacher = f"""Транскрипт лекции по дисциплине "{discipline_name}":
---
{transcript}
---
Задание: На основе этого транскрипта составь краткий, структурированный конспект для ПРЕПОДАВАТЕЛЯ.
Основные цели конспекта: быстро напомнить преподавателю ключевые темы, структуру изложения, основные тезисы и выводы лекции.
Стиль: академический, лаконичный, по существу. Выдели основные блоки или разделы.
Конспект для преподавателя:"""

    prompt_student = f"""Транскрипт лекции по дисциплине "{discipline_name}":
---
{transcript}
---
Задание: На основе этого транскрипта составь подробный конспект для СТУДЕНТА.
Цель конспекта: помочь студенту понять и усвоить материал лекции, особенно если он ее пропустил или хочет повторить.
Объясни основные понятия и термины, сохраняй логическую последовательность изложения лектора. Конспект должен быть информативным и легко читаемым.
Конспект для студента:"""

    prompt_keywords = f"""Проанализируй следующий транскрипт лекции по дисциплине "{discipline_name}".
Выдели 5-10 основных ключевых слов или терминов, наиболее точно отражающих содержание лекции.
Представь результат в виде списка, где каждый элемент списка - это одно ключевое слово или короткая фраза, разделенные запятыми.
Транскрипт:
---
{transcript}
---
Ключевые слова/темы:"""

    # --- Выполнение запросов ---
    teacher_summary_res = _generate_content_sync(prompt_teacher, "teacher summary")
    student_summary_res = _generate_content_sync(prompt_student, "student summary")
    keywords_str_res = _generate_content_sync(prompt_keywords, "keywords")

    if teacher_summary_res: results["teacher_summary"] = teacher_summary_res
    if student_summary_res: results["student_summary"] = student_summary_res
    if keywords_str_res:
        results["keywords"] = [kw.strip() for kw in keywords_str_res.split(',') if kw.strip()]
    else:
        results["keywords"] = ["не удалось извлечь"] # Явное указание на ошибку

    logging.info("Text analysis finished.")
    return results

# --- Асинхронная обертка ---
async def analyze(transcript: str, discipline_name: str = "не указана") -> dict:
    """Асинхронная обертка для запуска синхронного анализа текста в потоке."""
    logging.debug(f"Calling analyze_text_sync for discipline '{discipline_name}' via asyncio.to_thread")
    analysis_result = await asyncio.to_thread(analyze_text_sync, transcript, discipline_name)
    return analysis_result