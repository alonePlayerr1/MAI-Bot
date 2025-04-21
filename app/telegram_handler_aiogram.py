# app/telegram_handler_aiogram.py

import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime

# --- Aiogram Imports ---
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove, FSInputFile, Document
from aiogram.enums import ChatAction # Для send_chat_action

# --- Project Imports ---
import config
# Импортируем ОБА класса состояний
from config import LectureRegistration, DevProcessing
from app import utils
from app import drive_handler # Нужен для основного режима
from app import cloud_storage # Нужен для основного режима
from app import audio_processor # Нужен для основного режима
from app import text_analyzer # Нужен для обоих режимов
from app import doc_generator # Нужен для обоих режимов

# --- pydub Imports ---
# Нужен для основного режима
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

# --- Создаем Роутеры ---
common_router = Router(name="common_commands")
registration_router = Router(name="lecture_registration_fsm")
dev_router = Router(name="developer_tools")

# --- Обработчики общих команд (common_router) ---
@common_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    chat_id = message.chat.id; logging.info(f"/start from {chat_id}")
    await state.clear()
    await message.answer("Привет! Давайте зарегистрируем вашу лекцию (основной режим).", reply_markup=ReplyKeyboardRemove())
    await message.answer("1. Напишите название дисциплины:")
    await state.set_state(LectureRegistration.waiting_discipline)

@common_router.message(Command("reset"))
async def handle_reset(message: Message, state: FSMContext):
    chat_id = message.chat.id; current_state = await state.get_state()
    logging.info(f"/reset from {chat_id}. State: {current_state}")
    if current_state is not None:
        await state.clear(); await message.answer("Состояние сброшено. Используйте /start или /dev_process_txt.")
    else: await message.answer("Нет активного процесса для сброса.")

@common_router.message(Command("help"))
async def handle_help(message: Message):
    chat_id = message.chat.id; logging.info(f"/help from {chat_id}")
    help_text = (
        "Привет! Я бот для обработки аудиозаписей лекций.\n\n"
        "<b>Основной режим:</b>\n"
        "1. Начните с /start.\n"
        "2. Введите: Дисциплину -> Преподавателя -> Дату/Время -> Ссылку Google Drive.\n"
        "3. Бот скачает, обработает аудио и пришлет отчет.\n\n"
        "<b>Режим разработчика (для теста NLP/DocGen):</b>\n"
        "1. Начните с /dev_process_txt.\n"
        "2. Введите: Дисциплину -> Преподавателя -> Дату/Время.\n"
        "3. Отправьте файл <b>.txt</b> с готовым транскриптом.\n"
        "4. Бот пропустит обработку аудио и сразу запустит анализ/генерацию отчета.\n\n"
        "Используйте /reset для сброса в любом режиме."
    )
    await message.reply(help_text)

# --- Обработчики состояний FSM (Основной режим - registration_router) ---

@registration_router.message(StateFilter(LectureRegistration.waiting_discipline), F.text)
async def handle_discipline(message: Message, state: FSMContext):
    discipline_name = message.text.strip()
    if not discipline_name: await message.answer("Название не может быть пустым."); return
    logging.info(f"Discipline '{discipline_name}' received (main flow)")
    await state.update_data(discipline=discipline_name)
    await message.answer(f"Отлично! Дисциплина: '{discipline_name}'.\n2. Введите ФИО преподавателя (слитно):")
    await state.set_state(LectureRegistration.waiting_teacher)

@registration_router.message(StateFilter(LectureRegistration.waiting_discipline))
async def handle_discipline_incorrect_type(message: Message): await message.answer("Введите название текстом.")

@registration_router.message(StateFilter(LectureRegistration.waiting_teacher), F.text)
async def handle_teacher_name(message: Message, state: FSMContext):
    teacher_name = message.text.strip()
    if not teacher_name: await message.answer("Имя не может быть пустым."); return
    if ' ' in teacher_name: await message.answer("Ошибка: без пробелов (ИвановИИ)."); return
    logging.info(f"Teacher '{teacher_name}' received (main flow)")
    await state.update_data(teacher_name=teacher_name)
    await message.answer(f"Принято! Преподаватель: '{teacher_name}'.\n3. Введите дату и время (ЧЧ:ММ-ДД.ММ.ГГГГ):")
    await state.set_state(LectureRegistration.waiting_datetime)

@registration_router.message(StateFilter(LectureRegistration.waiting_teacher))
async def handle_teacher_incorrect_type(message: Message): await message.answer("Введите ФИО текстом без пробелов.")

@registration_router.message(StateFilter(LectureRegistration.waiting_datetime), F.text)
async def handle_datetime(message: Message, state: FSMContext):
    datetime_input = message.text.strip()
    if not datetime_input: await message.answer("Дата/время не могут быть пустыми."); return
    try:
        time_str, date_str = datetime_input.split(config.DATETIME_SPLIT_CHAR)
        datetime.strptime(time_str, config.TIME_FORMAT); datetime.strptime(date_str, config.DATE_FORMAT)
        logging.info(f"DateTime '{datetime_input}' received (main flow)")
        await state.update_data(lection_time=time_str, lection_date=date_str)
        await message.answer(f"Понял! {time_str} ({date_str}).\n4. Отправьте <b>ссылку Google Drive</b> (доступ 'Всем').")
        await state.set_state(LectureRegistration.waiting_drive_link)
    except (ValueError, TypeError):
        await message.answer(f"Ошибка формата: нужен ЧЧ:ММ{config.DATETIME_SPLIT_CHAR}ДД.ММ.ГГГГ.")

@registration_router.message(StateFilter(LectureRegistration.waiting_datetime))
async def handle_datetime_incorrect_type(message: Message): await message.answer("Введите дату/время текстом.")


# ---> НАЧАЛО ПОЛНОЙ ВЕРСИИ ФУНКЦИИ handle_drive_link <---
@registration_router.message(StateFilter(LectureRegistration.waiting_drive_link), F.text)
async def handle_drive_link(message: Message, state: FSMContext, bot: Bot):
    """
    Основной обработчик: Ссылка Drive -> Скачивание -> Конверт -> GCS -> S2T -> NLP -> DocGen
    """
    chat_id = message.chat.id
    drive_link = message.text.strip() if message.text else None
    user_data = await state.get_data()

    downloaded_drive_file_path = None
    converted_temp_file_path = None
    generated_doc_path = None
    detected_sample_rate = 0
    structured_filename = None # Определяем здесь

    # --- 1. Валидация ссылки ---
    if not drive_link or not re.search(r'drive.google.com/(file/d/|open\?id=|/d/)', drive_link):
        logging.warning(f"Получена невалидная ссылка Google Drive от chat_id {chat_id}: {drive_link}")
        await message.answer("❌ Пожалуйста, отправьте корректную ссылку на файл в Google Drive.")
        return

    logging.info(f"Получена ссылка Google Drive от chat_id {chat_id}: {drive_link}")
    await message.answer(f"✅ Ссылка получена!")

    try:
        # --- 2. Скачивание файла из Google Drive ---
        await message.answer(f"📥 Начинаю скачивание файла из Google Drive...")
        await bot.send_chat_action(chat_id, action=ChatAction.TYPING) # Используем ChatAction
        logging.info(f"Запуск скачивания из Drive для chat_id {chat_id}")

        downloaded_drive_file_path = await asyncio.to_thread(
            drive_handler.download_file_from_drive, drive_link
        )

        if not downloaded_drive_file_path:
            logging.error(f"Ошибка скачивания файла из Google Drive для chat_id {chat_id}")
            await message.answer("❌ Не удалось скачать файл из Google Drive. Проверьте ссылку и права доступа ('Всем, у кого есть ссылка'). Используйте /reset.")
            await state.clear(); return

        logging.info(f"Файл скачан из Drive в {downloaded_drive_file_path} для chat_id {chat_id}")
        await message.answer("👍 Файл из Google Drive успешно скачан.")
        await bot.send_chat_action(chat_id, action=ChatAction.TYPING)

        # --- 3. ОПРЕДЕЛЕНИЕ ЧАСТОТЫ и Конвертация аудио ---
        await message.answer("⚙️ Готовлю аудиофайл (конвертирую в формат Opus)...")
        logging.info(f"Запуск определения частоты и конвертации аудио для chat_id {chat_id}")
        output_extension = ".ogg"
        structured_filename = utils.generate_audio_filename(user_data, None, output_extension)

        # Вспомогательная функция для синхронных операций с аудио
        def process_audio_sync(input_path, output_dir, filename):
            """Загружает аудио, приводит к моно, ресемплирует до 16кГц и экспортирует в Ogg/Opus."""
            temp_path_conv = None
            TARGET_SAMPLE_RATE = 16000 # Целевая частота для S2T
            try:
                audio = AudioSegment.from_file(input_path)
                original_rate = audio.frame_rate
                logging.info(f"Аудио загружено: {audio.duration_seconds:.2f} сек, Исходная частота: {original_rate} Гц, {audio.channels} канал(а)")

                if audio.channels > 1:
                    logging.info("Конвертирую аудио в моно...")
                    audio = audio.set_channels(1)

                if original_rate != TARGET_SAMPLE_RATE:
                    logging.info(f"Изменяю частоту дискретизации с {original_rate} Гц на {TARGET_SAMPLE_RATE} Гц...")
                    try:
                        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
                        logging.info(f"Частота успешно изменена на {audio.frame_rate} Гц.")
                    except Exception as resample_e:
                        logging.error(f"Ошибка при ресемплинге до {TARGET_SAMPLE_RATE} Гц: {resample_e}", exc_info=True)
                        raise ValueError(f"Ошибка изменения частоты на {TARGET_SAMPLE_RATE} Гц") from resample_e

                final_rate = audio.frame_rate
                if final_rate <= 0:
                    raise ValueError(f"Некорректная финальная частота дискретизации ({final_rate} Гц)")

                with tempfile.NamedTemporaryFile(mode='wb', suffix=output_extension, dir=output_dir, delete=False) as conv_temp_f:
                    temp_path_conv = conv_temp_f.name
                    logging.info(f"Экспорт аудио в OGG Opus в {temp_path_conv} с частотой {final_rate} Гц")
                    audio.export(temp_path_conv, format="ogg", codec="libopus", bitrate="48k")

                logging.info(f"Аудио успешно конвертировано: {temp_path_conv}")
                return temp_path_conv, final_rate
            except CouldntDecodeError as e:
                 logging.error(f"Pydub не смог декодировать файл: {input_path}. {e}", exc_info=True)
                 raise
            except Exception as e:
                 logging.error(f"Ошибка во время обработки аудио {input_path}: {e}", exc_info=True)
                 if temp_path_conv and os.path.exists(temp_path_conv):
                     try: os.remove(temp_path_conv)
                     except OSError: pass
                 raise

        # Запускаем обработку аудио в потоке
        try:
            converted_temp_file_path, detected_sample_rate = await asyncio.to_thread(
                process_audio_sync, downloaded_drive_file_path, config.TEMP_FOLDER, structured_filename
            )
            logging.info(f"Определенная/целевая частота дискретизации: {detected_sample_rate} Гц")
        except ValueError as ve:
             logging.error(f"Ошибка определения/изменения частоты: {ve}", exc_info=True)
             await message.answer("❌ Не удалось подготовить аудиофайл (проблема с частотой дискретизации). Используйте /reset.")
             await state.clear(); return
        except CouldntDecodeError:
             await message.answer("❌ Не удалось обработать скачанный аудиофайл (ошибка декодирования). Используйте /reset.")
             await state.clear(); return
        except Exception as proc_e:
             logging.error(f"Неожиданная ошибка обработки аудио: {proc_e}", exc_info=True)
             await message.answer("❌ Произошла ошибка во время подготовки аудиофайла. Используйте /reset.")
             await state.clear(); return

        if not detected_sample_rate or detected_sample_rate <= 0:
             logging.error(f"Финальная частота дискретизации некорректна ({detected_sample_rate}). Прерывание.")
             await message.answer("❌ Ошибка: Не удалось получить корректную частоту дискретизации аудио. Используйте /reset.")
             await state.clear(); return

        await message.answer(f"👍 Аудио подготовлено (формат .ogg, частота: {detected_sample_rate} Гц).")
        await bot.send_chat_action(chat_id, action=ChatAction.UPLOAD_DOCUMENT) # Используем ChatAction

        # --- 4. Загрузка в GCS ---
        await message.answer("☁️⬆️ Загружаю файл в облачное хранилище...")
        logging.info(f"Запуск загрузки в GCS для chat_id {chat_id}: {structured_filename}")
        gcs_uri = await asyncio.to_thread(
            cloud_storage.upload_to_gcs, converted_temp_file_path, structured_filename
        )
        if not gcs_uri:
             await message.answer("❌ К сожалению, произошла ошибка при загрузке файла в облачное хранилище. Используйте /reset.")
             await state.clear(); return
        logging.info(f"Файл загружен в {gcs_uri} для chat_id {chat_id}")
        await message.answer(f"👍 Файл успешно загружен в облако.")
        await bot.send_chat_action(chat_id, action=ChatAction.TYPING)

        # --- 5. Запуск S2T (с правильной частотой) ---
        await message.answer("🧠 Запускаю распознавание речи (это может занять длительное время)...")
        logging.info(f"Запуск S2T для chat_id {chat_id} с частотой {detected_sample_rate} Гц")
        transcript = await asyncio.to_thread(
            audio_processor.transcribe_audio_gcs, gcs_uri, detected_sample_rate
        )

        if transcript is None:
            await message.answer("❌ К сожалению, произошла ошибка во время распознавания речи. Используйте /reset.")
            await state.clear(); return

        logging.info(f"S2T завершено для chat_id {chat_id}. Длина транскрипта: {len(transcript)}")
        await message.answer("✅ Распознавание речи успешно завершено!")

        # --- 6. Анализ текста (Заглушка) ---
        # --- 6. Анализ текста ---
        await message.answer("📊 Анализирую текст...")  # Обновил сообщение
        logging.info(f"Запуск анализа текста для chat_id {chat_id}")
        # Вызываем обновленную функцию analyze
        analysis_results = await asyncio.to_thread(text_analyzer.analyze, transcript)
        logging.info(f"Результат анализа для chat_id {chat_id}: {analysis_results}")
        await bot.send_chat_action(chat_id, action=ChatAction.TYPING)

        # --- 7. Генерация документа ---
        await message.answer("✍️ Создаю отчет...")  # Обновил сообщение
        logging.info(f"Запуск генерации документа для chat_id {chat_id}")
        # Передаем user_data (метаданные) и analysis_results (конспекты, ключи)
        # Также передаем транскрипт, чтобы генератор мог его использовать
        user_data_with_transcript = {**user_data, "transcript": transcript}
        generated_doc_paths = await asyncio.to_thread(
            doc_generator.generate, analysis_results, user_data_with_transcript
        )
        # ... (остальной код обработки generated_doc_paths) ...
        if generated_doc_paths:
             generated_doc_path = generated_doc_paths[0]
             logging.info(f"Документ сгенерирован (заглушка): {generated_doc_path}")
        else:
             logging.error(f"Генерация документа (заглушка) не вернула путь для chat_id {chat_id}")
             await message.answer("⚠️ Не удалось создать файл отчета (заглушка).")
             # Продолжаем без файла

        await bot.send_chat_action(chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        # --- 8. Отправка результатов ---
        await message.answer("✨ Обработка полностью завершена!")

        # Отправляем сгенерированный документ (если он был создан)
        if generated_doc_path and os.path.exists(generated_doc_path):
            try:
                doc_to_send = FSInputFile(path=generated_doc_path, filename=os.path.basename(generated_doc_path))
                await message.answer_document(document=doc_to_send, caption="Ваш отчет готов (пока содержит только полный транскрипт).")
                logging.info(f"Сгенерированный документ {generated_doc_path} отправлен chat_id {chat_id}")
            except Exception as send_doc_e:
                 logging.error(f"Ошибка отправки документа {generated_doc_path}: {send_doc_e}", exc_info=True)
                 await message.answer("⚠️ Не удалось отправить файл с отчетом.")
        elif not generated_doc_paths: pass # Сообщение об ошибке генерации уже было
        else:
             logging.error(f"Сгенерированный файл отчета не найден: {generated_doc_path}")
             await message.answer("⚠️ Не удалось найти сгенерированный файл отчета.")

        logging.info(f"Полный цикл обработки успешно завершен для chat_id {chat_id}")
        await state.clear() # Очищаем состояние FSM

    except Exception as e: # Общий обработчик ошибок для всей функции
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА в handle_drive_link для chat_id {chat_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла непредвиденная ошибка во время обработки вашего запроса. Пожалуйста, используйте /reset и попробуйте снова.")
        await state.clear() # Сбрасываем состояние при критической ошибке
    finally:
        # --- Очистка Временных Файлов ---
        async def cleanup_file(f_path):
            if f_path and os.path.exists(f_path):
                try:
                    await asyncio.to_thread(os.remove, f_path)
                    logging.info(f"Очищен временный файл: {f_path}")
                except OSError as e:
                    logging.error(f"Ошибка удаления временного файла {f_path}: {e}", exc_info=True)
        await asyncio.gather(
            cleanup_file(downloaded_drive_file_path),
            cleanup_file(converted_temp_file_path),
            cleanup_file(generated_doc_path)
        )
# ---> КОНЕЦ ПОЛНОЙ ВЕРСИИ ФУНКЦИИ handle_drive_link <---


@registration_router.message(StateFilter(LectureRegistration.waiting_drive_link))
async def handle_drive_link_incorrect_type(message: Message):
    await message.answer("Пожалуйста, отправьте ссылку на Google Drive текстом.")


# --- Обработчики для режима разработчика (dev_router) ---

@dev_router.message(Command("dev_process_txt"))
async def handle_dev_start(message: Message, state: FSMContext):
    """Начинает диалог для тестовой обработки TXT файла."""
    chat_id = message.chat.id
    logging.info(f"DEV MODE: Received /dev_process_txt from chat_id {chat_id}")
    await state.clear()
    await message.answer("⚙️ Режим разработчика: Обработка TXT.\n1. Введите название дисциплины:")
    await state.set_state(DevProcessing.waiting_dev_discipline)

@dev_router.message(StateFilter(DevProcessing.waiting_dev_discipline), F.text)
async def handle_dev_discipline(message: Message, state: FSMContext):
    discipline_name = message.text.strip();
    if not discipline_name: await message.answer("Название не может быть пустым."); return
    logging.info(f"DEV MODE: Discipline '{discipline_name}' received.")
    await state.update_data(discipline=discipline_name)
    await message.answer(f"DEV: Дисциплина '{discipline_name}'.\n2. Введите ФИО преподавателя (слитно):")
    await state.set_state(DevProcessing.waiting_dev_teacher)

@dev_router.message(StateFilter(DevProcessing.waiting_dev_discipline))
async def handle_dev_discipline_incorrect(message: Message): await message.answer("DEV: Введите название текстом.")

@dev_router.message(StateFilter(DevProcessing.waiting_dev_teacher), F.text)
async def handle_dev_teacher(message: Message, state: FSMContext):
    teacher_name = message.text.strip()
    if not teacher_name: await message.answer("Имя не может быть пустым."); return
    if ' ' in teacher_name: await message.answer("DEV: Ошибка: без пробелов (ИвановИИ)."); return
    logging.info(f"DEV MODE: Teacher '{teacher_name}' received.")
    await state.update_data(teacher_name=teacher_name)
    await message.answer(f"DEV: Преподаватель '{teacher_name}'.\n3. Введите дату и время (ЧЧ:ММ-ДД.ММ.ГГГГ):")
    await state.set_state(DevProcessing.waiting_dev_datetime)

@dev_router.message(StateFilter(DevProcessing.waiting_dev_teacher))
async def handle_dev_teacher_incorrect(message: Message): await message.answer("DEV: Введите ФИО текстом без пробелов.")

@dev_router.message(StateFilter(DevProcessing.waiting_dev_datetime), F.text)
async def handle_dev_datetime_dev(message: Message, state: FSMContext): # Изменено имя функции
    datetime_input = message.text.strip()
    if not datetime_input: await message.answer("Дата/время не могут быть пустыми."); return
    try:
        time_str, date_str = datetime_input.split(config.DATETIME_SPLIT_CHAR)
        datetime.strptime(time_str, config.TIME_FORMAT); datetime.strptime(date_str, config.DATE_FORMAT)
        logging.info(f"DEV MODE: DateTime '{datetime_input}' received.")
        await state.update_data(lection_time=time_str, lection_date=date_str)
        await message.answer("✅ DEV: Метаданные собраны.\n4. Теперь отправьте файл <b>.txt</b> с готовым транскриптом лекции.")
        await state.set_state(DevProcessing.waiting_transcript_txt)
    except (ValueError, TypeError):
        await message.answer(f"DEV: Ошибка формата: нужен ЧЧ:ММ{config.DATETIME_SPLIT_CHAR}ДД.ММ.ГГГГ.")

@dev_router.message(StateFilter(DevProcessing.waiting_dev_datetime))
async def handle_dev_datetime_incorrect(message: Message): await message.answer("DEV: Введите дату/время текстом.")


@dev_router.message(StateFilter(DevProcessing.waiting_transcript_txt), F.document)
async def handle_dev_transcript_txt(message: Message, state: FSMContext, bot: Bot):
    """Получает TXT файл, читает транскрипт и запускает NLP/DocGen."""
    chat_id = message.chat.id
    document = message.document
    temp_txt_path = None
    generated_doc_path = None
    user_data = await state.get_data()

    if not document.file_name or not document.file_name.lower().endswith('.txt') or document.mime_type != 'text/plain':
        await message.answer("❌ Пожалуйста, отправьте файл именно в формате <b>.txt</b>.")
        return

    await message.answer(f"✅ DEV: Файл {document.file_name} получен ({document.file_size} байт). Читаю транскрипт...")
    await bot.send_chat_action(chat_id, action=ChatAction.TYPING)

    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix=".txt", dir=config.TEMP_FOLDER, delete=False) as temp_f:
            temp_txt_path = temp_f.name
            # Используем download объекта файла
            await bot.download(file=document.file_id, destination=temp_txt_path)
            logging.info(f"DEV MODE: Transcript TXT downloaded to {temp_txt_path}")

        with open(temp_txt_path, 'r', encoding='utf-8') as f:
            transcript = f.read()

        if not transcript or not transcript.strip():
            logging.warning(f"DEV MODE: Uploaded TXT file {temp_txt_path} is empty.")
            await message.answer("❌ Отправленный TXT файл пуст. Пожалуйста, отправьте файл с текстом.")
            await state.clear(); return

        logging.info(f"DEV MODE: Transcript loaded from TXT. Length: {len(transcript)}")

        # --- Пропускаем шаги 2, 3, 4, 5 (Drive, Convert, GCS, S2T) ---
        # --- Сразу переходим к шагам 6, 7, 8 ---

        await message.answer("⚙️ DEV: Запускаю обработку транскрипта...")

        # --- 6. Анализ текста ---
        await message.answer("📊 Анализирую текст (заглушка)...")
        logging.info(f"DEV MODE: Запуск анализа текста для chat_id {chat_id}")
        analysis_results = await asyncio.to_thread(text_analyzer.analyze, transcript)
        logging.info(f"DEV MODE: Результат анализа (заглушка): {analysis_results}")
        await bot.send_chat_action(chat_id, action=ChatAction.TYPING)

        # --- 7. Генерация документа ---
        await message.answer("✍️ Создаю отчет (заглушка)...")
        logging.info(f"DEV MODE: Запуск генерации документа для chat_id {chat_id}")
        user_data_with_transcript = {**user_data, "transcript": transcript}
        generated_doc_paths = await asyncio.to_thread(
            doc_generator.generate, analysis_results, user_data_with_transcript
        )
        if generated_doc_paths:
             generated_doc_path = generated_doc_paths[0]
             logging.info(f"DEV MODE: Документ сгенерирован (заглушка): {generated_doc_path}")
        else:
             logging.error(f"DEV MODE: Генерация документа (заглушка) не вернула путь")
             await message.answer("⚠️ Не удалось создать файл отчета (заглушка).")

        await bot.send_chat_action(chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        # --- 8. Отправка результатов ---
        await message.answer("✨ DEV MODE: Обработка TXT завершена!")

        if generated_doc_path and os.path.exists(generated_doc_path):
            try:
                doc_to_send = FSInputFile(path=generated_doc_path, filename=os.path.basename(generated_doc_path))
                await message.answer_document(document=doc_to_send, caption="Ваш DEV отчет готов.")
                logging.info(f"DEV MODE: Сгенерированный документ {generated_doc_path} отправлен chat_id {chat_id}")
            except Exception as send_doc_e:
                 logging.error(f"DEV MODE: Ошибка отправки документа {generated_doc_path}: {send_doc_e}", exc_info=True)
                 await message.answer("⚠️ Не удалось отправить файл с отчетом.")
        elif not generated_doc_paths: pass
        else:
             logging.error(f"DEV MODE: Сгенерированный файл отчета не найден: {generated_doc_path}")
             await message.answer("⚠️ Не удалось найти сгенерированный файл отчета.")

        logging.info(f"DEV MODE: Цикл обработки TXT успешно завершен для chat_id {chat_id}")
        await state.clear()

    except Exception as e:
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА в handle_dev_transcript_txt для chat_id {chat_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла непредвиденная ошибка в DEV режиме. Используйте /reset.")
        await state.clear()
    finally:
        if temp_txt_path and os.path.exists(temp_txt_path):
            try:
                await asyncio.to_thread(os.remove, temp_txt_path)
                logging.info(f"DEV MODE: Очищен временный TXT файл: {temp_txt_path}")
            except OSError as e:
                logging.error(f"DEV MODE: Ошибка удаления временного TXT файла {temp_txt_path}: {e}", exc_info=True)

@dev_router.message(StateFilter(DevProcessing.waiting_transcript_txt))
async def handle_dev_txt_incorrect_type(message: Message):
    await message.answer("Пожалуйста, отправьте именно файл с расширением .txt")


# --- Обработчик неизвестных сообщений (common_router) ---
@common_router.message()
async def handle_unknown(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logging.debug(f"Received unknown message type '{message.content_type}' from chat_id {message.chat.id} in state {current_state}")
    # Проверяем основной FSM
    if current_state == LectureRegistration.waiting_discipline: await message.answer("Режим лекции: Введите название дисциплины или /reset.")
    elif current_state == LectureRegistration.waiting_teacher: await message.answer("Режим лекции: Введите ФИО преподавателя или /reset.")
    elif current_state == LectureRegistration.waiting_datetime: await message.answer(f"Режим лекции: Введите дату/время (ЧЧ:ММ-ДД.ММ.ГГГГ) или /reset.")
    elif current_state == LectureRegistration.waiting_drive_link: await message.answer("Режим лекции: Жду ссылку Google Drive или /reset.")
    # Проверяем DEV FSM
    elif current_state == DevProcessing.waiting_dev_discipline: await message.answer("DEV Режим: Введите название дисциплины или /reset.")
    elif current_state == DevProcessing.waiting_dev_teacher: await message.answer("DEV Режим: Введите ФИО преподавателя или /reset.")
    elif current_state == DevProcessing.waiting_dev_datetime: await message.answer(f"DEV Режим: Введите дату/время или /reset.")
    elif current_state == DevProcessing.waiting_transcript_txt: await message.answer("DEV Режим: Жду TXT файл или /reset.")
    else: await message.answer("Неизвестная команда или состояние. Используйте /start или /dev_process_txt.")


# --- Функция регистрации роутеров ---
async def register_aiogram_handlers(dp: Dispatcher, bot: Bot):
    """Регистрирует все роутеры в главном диспетчере."""
    # Важен порядок: сначала специфичные FSM, потом общие команды
    dp.include_router(registration_router) # Основной FSM
    dp.include_router(dev_router)          # FSM для разработчика
    dp.include_router(common_router)       # Общие команды и catch-all
    logging.info("Aiogram command, FSM, and DEV handlers registered.")