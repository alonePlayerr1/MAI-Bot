# app/doc_generator.py
import logging
import os
import config # Нужен для TEMP_FOLDER

def generate(analysis_results: dict, metadata: dict) -> list[str]:
    """
    Генерирует текстовый файл с метаданными, ДВУМЯ конспектами,
    ключевыми словами и ПОЛНЫМ транскриптом.
    (Пока это заглушка, в будущем будет генерировать DOCX/PDF).
    """
    logging.info("Placeholder: generate function called.")
    # Получаем данные из переданных словарей
    discipline = metadata.get('discipline', 'N/A')
    teacher = metadata.get('teacher_name', 'N/A')
    date_str = metadata.get('lection_date', 'N/A')
    time_str = metadata.get('lection_time', 'N/A')
    # Получаем транскрипт из metadata (куда мы его добавили в telegram_handler)
    transcript = metadata.get('transcript', 'Транскрипт не найден.')
    # Получаем результаты анализа
    teacher_summary = analysis_results.get('teacher_summary', 'Конспект для преподавателя не создан.')
    student_summary = analysis_results.get('student_summary', 'Конспект для студента не создан.')
    keywords_list = analysis_results.get('keywords', [])
    keywords_str = ", ".join(keywords_list) if keywords_list else "Ключевые слова не найдены."


    # Формируем имя файла
    filename_base = f"Report_{discipline}_{teacher}_{date_str}_{time_str}".replace(" ", "_").replace(":", "-")
    output_filename = f"{filename_base}.txt"
    output_filepath = os.path.join(config.TEMP_FOLDER, output_filename)

    try:
        # Записываем информацию в файл
        with open(output_filepath, "w", encoding='utf-8') as f:
            f.write(f"Отчет по лекции\n")
            f.write("="*20 + "\n")
            f.write(f"Дисциплина: {discipline}\n")
            f.write(f"Преподаватель: {teacher}\n")
            f.write(f"Дата: {date_str}\n")
            f.write(f"Время: {time_str}\n")
            f.write("="*20 + "\n\n")

            f.write("Конспект для преподавателя:\n")
            f.write("-" * 20 + "\n")
            f.write(teacher_summary + "\n")
            f.write("-" * 20 + "\n\n")

            f.write("Конспект для студента:\n")
            f.write("-" * 20 + "\n")
            f.write(student_summary + "\n")
            f.write("-" * 20 + "\n\n")

            f.write("Ключевые слова/темы:\n")
            f.write("-" * 20 + "\n")
            f.write(keywords_str + "\n")
            f.write("-" * 20 + "\n\n")

            f.write("Полный транскрипт:\n")
            f.write("-" * 50 + "\n")
            f.write(transcript if transcript else "Транскрипт пуст.")
            f.write("\n" + "-" * 50 + "\n")


        logging.info(f"Создан файл отчета (заглушка): {output_filepath}")
        return [output_filepath] # Возвращаем список с путем к файлу
    except Exception as e:
        logging.error(f"Не удалось создать файл отчета (заглушка): {e}", exc_info=True)
        return []