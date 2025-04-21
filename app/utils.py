# app/utils.py
import logging
import os
from datetime import datetime
import config # Импортируем для METADATA_SEPARATOR

# Функция setup_logging() удалена, используется setup_logging_aiogram() из config.py

def generate_audio_filename(metadata: dict, original_filename: str | None, output_extension: str = ".ogg") -> str:
    """
    Generates a structured filename for the audio file.
    Uses output_extension for the final file extension.
    """
    try:
        # Ensure all keys exist, provide defaults if necessary
        discipline = metadata.get('discipline', 'UnknownDiscipline')
        teacher = metadata.get('teacher_name', 'UnknownTeacher')
        date_str = metadata.get('lection_date', 'UnknownDate')
        time_str = metadata.get('lection_time', 'UnknownTime')

        # Базовая очистка имен (замена пробелов и потенциально проблемных символов)
        safe_discipline = discipline.replace(" ", "_").replace("/", "-").replace("\\", "-")
        safe_teacher = teacher.replace(" ", "_").replace("/", "-").replace("\\", "-")

        # Форматируем время для имени файла
        safe_time_str = time_str.replace(":", "-")

        # Убеждаемся, что расширение начинается с точки
        if not output_extension.startswith('.'):
            output_extension = '.' + output_extension

        # Собираем базовое имя файла без расширения
        base_filename = config.METADATA_SEPARATOR.join([
            safe_discipline,
            safe_teacher,
            date_str, # Формат даты уже должен быть безопасным
            safe_time_str,
            "audio" # Общий идентификатор, оригинальное расширение уже не так важно
        ])

        filename = base_filename + output_extension

        # Ограничиваем длину имени файла, если нужно (маловероятно с этой структурой)
        max_len = 200 # Максимальная длина имени файла
        if len(filename) > max_len:
             filename = filename[:max_len - len(output_extension)] + output_extension
             logging.warning(f"Generated filename was truncated: {filename}")

        return filename
    except Exception as e:
        logging.error(f"Error generating filename: {e}", exc_info=True)
        # Запасное имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_original = original_filename.replace(" ", "_").replace("/", "-").replace("\\", "-") if original_filename else "audio"
        fallback_ext = output_extension if output_extension else ".ogg"
        return f"fallback_{timestamp}_{safe_original[-50:]}{fallback_ext}" # Ограничиваем часть оригинального имени

# Можно добавить другие общие утилиты сюда в будущем