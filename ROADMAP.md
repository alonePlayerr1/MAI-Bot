# Roadmap проекта MAI Telegram Bot

Этот документ отслеживает статус реализации основных функций бота.
*Последнее обновление: 21.04.2025*

## Основные модули и функции

### 1. Базовая структура и Telegram-интерфейс (на Aiogram)
* [✅] Модульная структура проекта (`app/`, `config.py`, `main.py`)
* [✅] Настройка логирования (`config.py`)
* [✅] Внешняя конфигурация (`config.py`, `.env`)
* [✅] Регистрация и запуск бота (`main.py` с `aiogram`)
* [✅] Обработка команд `/start`, `/help`, `/reset` (`app/telegram_handler_aiogram.py`)
* [✅] Пошаговый диалог FSM для сбора метаданных (дисциплина, преподаватель, дата/время) (`app/telegram_handler_aiogram.py`)
* [✅] Прием **ссылки** на Google Drive (`app/telegram_handler_aiogram.py`)
* [✅] Валидация формата ссылки Google Drive (`app/telegram_handler_aiogram.py`)
* [✅] Базовая обработка ошибок и улучшенная обратная связь с пользователем (статусы, эмодзи) (`app/telegram_handler_aiogram.py`)
* [✅] Добавлена команда /retry для возврата к началу ввода данных (`app/telegram_handler_aiogram.py`, `config.py`)
* [✅] Реагирование на команды /start, /reset, /retry, /help независимо от состояния процесса (`app/telegram_handler_aiogram.py`)
* [✅] Подтверждение корректности введённых пользователем данных и возможность исправить некорректно введённые данные (`app/telegram_handler_aiogram.py`)
* [✅] Подключён обработчик неизвестных сообщений (`app/telegram_handler_aiogram.py`)
* [✅] Повышена дружелюбность интерфейса к пользователю (`app/telegram_handler_aiogram.py`)
* [✅] Добавлена инструкция по загрузке файла на Google Drive и настройке доступа к нему по ссылке (`app/telegram_handler_aiogram.py`)

### 2. Работа с облаком (Google Cloud)
* [✅] Аутентификация с Google Cloud через сервисный аккаунт
* [✅] Включение Google Drive API в Google Cloud Console
* [✅] Интеграция с Google Cloud Storage (GCS) (`app/cloud_storage.py`)
* [✅] Загрузка обработанного (`.ogg`) аудиофайла в GCS
* [✅] Реализация скачивания файла из Google Drive по ссылке (`app/drive_handler.py`)
* [✅] Инициализация клиента Google Cloud Speech-to-Text (`app/audio_processor.py`)
* [✅] Включение Vertex AI API в Google Cloud Console
* [✅] Инициализация клиента Vertex AI (`app/text_analyzer.py`)

### 3. Обработка аудио (После скачивания из Google Drive)
* [✅] Конвертация аудио в Opus/Ogg (`pydub`)
* [✅] Приведение к моно-каналу
* [✅] Ресемплинг аудио до 16кГц
* [✅] Вызов Google Cloud Speech-to-Text API для транскрибации файла из GCS
    * [✅] Настройка `RecognitionConfig` (кодек, язык, авто-пунктуация)
    * [✅] Передача корректной частоты дискретизации (16кГц)
    * [✅] Обработка ответа `long_running_recognize` (получение транскрипта)
    * [⏳] Улучшенная обработка специфических ошибок S2T API (пока базовая)

### 4. Анализ текста (NLP)
* [✅] Базовая структура модуля (`app/text_analyzer.py` с вызовом Vertex AI)
* [⏳] Реализация алгоритма саммаризации (вызов Gemini для 2х конспектов, качество требует настройки промптов)
* [⏳] Реализация алгоритма выделения ключевых слов/тем (вызов Gemini, качество требует настройки промптов)
* [❌] (Опционально) Реализация механизма выявления потенциальных "галлюцинаций" или неточностей ИИ

### 5. Генерация документов
* [✅] Базовая структура модуля (`app/doc_generator.py`)
* [⏳] Генерация документа в формате **TXT** с включением:
    * [✅] Метаданных лекции
    * [✅] Конспектов и ключевых слов (из `text_analyzer.py`)
    * [✅] Полного транскрипта
* [❌] Переход на генерацию `.docx` (`python-docx`)
* [❌] (Опционально) Конвертация в PDF
* [❌] (Опционально) Генерация TXT/RTF версий (если TXT отличается от текущей заглушки)

### 6. Отправка результатов
* [✅] Отправка текстовых статусов во время обработки
* [✅] Отправка сгенерированных файлов документов (TXT-заглушки) пользователю

### 7. Тестирование
* [❌] Настройка среды для тестов (`tests/`)
* [❌] Написание Unit-тестов
* [❌] Написание Mock-тестов для внешних API
* [❌] Написание интеграционных тестов

### 8. Прочее
* [✅] Режим разработчика для обработки TXT (`/dev_process_txt`)
* [⏳] Улучшение обработки ошибок и пользовательского опыта (нужно больше специфики)
* [❌] Документация кода (Docstrings)
* [❌] (Возможно) Интеграция с БД для хранения состояний (вместо `MemoryStorage`) или результатов

---
**Легенда:**
* ✅ Сделано / Реализовано
* ⏳ В процессе / Частично сделано / Реализовано как заглушка
* ❌ Не начато
