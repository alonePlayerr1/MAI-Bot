# app/telegram_handler.py
import logging
import os
import tempfile
from telebot import TeleBot
from telebot.types import Message
from datetime import datetime

import config # Use config directly
from app import utils
from app import cloud_storage
from app import audio_processor
# Import text_analyzer and doc_generator when they are ready
# from app import text_analyzer
# from app import doc_generator

# Simple in-memory store for user states and data.
# Consider using a database (Redis, PostgreSQL) for persistence/scaling
user_states = {} # {chat_id: {'state': state_const, 'data': {}}}

# --- Handler Registration Function ---
def register_handlers(bot: TeleBot):
    """Registers all message handlers for the bot."""

    # --- Command Handlers ---
    @bot.message_handler(commands=['start', 'reset'])
    def handle_start(message: Message):
        chat_id = message.chat.id
        logging.info(f"Received /start or /reset command from chat_id {chat_id}")
        user_states[chat_id] = {'state': config.STATE_WAITING_DISCIPLINE, 'data': {}}
        bot.send_message(chat_id, "Let's start the procedure of lection registration.")
        bot.send_message(chat_id, "1. What is the discipline of the lection?")

    @bot.message_handler(commands=['help'])
    def handle_help(message: Message):
        chat_id = message.chat.id
        logging.info(f"Received /help command from chat_id {chat_id}")
        help_text = (
            "This bot processes lecture audio recordings.\n"
            "1. Use /start to begin the process.\n"
            "2. Follow the prompts to provide:\n"
            "   - Discipline name\n"
            "   - Teacher's surname (no spaces, e.g., IvanovII)\n"
            f"   - Start Time & Date ({config.TIME_FORMAT}{config.DATETIME_SPLIT_CHAR}{config.DATE_FORMAT})\n"
            "   - The audio file of the lecture.\n"
            "3. The bot will upload the audio, transcribe it, and (in future) provide analysis and documents.\n"
            "Use /reset to restart the process if you get stuck."
        )
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['pashalka'])
    def handle_pashalka(message: Message):
        logging.info(f"Received /pashalka command from chat_id {message.chat.id}")
        bot.reply_to(message, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ') # Classic :)

    # --- State-Based Message Handlers ---
    @bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == config.STATE_WAITING_DISCIPLINE)
    def handle_discipline(message: Message):
        chat_id = message.chat.id
        logging.debug(f"Handling discipline input from chat_id {chat_id}")
        if message.text and message.text.strip():
            discipline_name = message.text.strip()
            user_states[chat_id]['data']['discipline'] = discipline_name
            user_states[chat_id]['state'] = config.STATE_WAITING_TEACHER
            logging.info(f"Discipline '{discipline_name}' received for chat_id {chat_id}")
            bot.send_message(chat_id, f"OK: Discipline '{discipline_name}'.\n2. What is the teacher's surname and initials? (No spaces, e.g., IvanovII)")
        else:
            bot.send_message(chat_id, "Please enter the discipline name as text.")

    @bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == config.STATE_WAITING_TEACHER)
    def handle_teacher_name(message: Message):
        chat_id = message.chat.id
        logging.debug(f"Handling teacher name input from chat_id {chat_id}")
        if message.text and message.text.strip():
            teacher_name = message.text.strip()
            if ' ' in teacher_name:
                 bot.send_message(chat_id, "Format error: Please send surname and initials *without spaces* (e.g., IvanovII). Try again!")
                 return
            user_states[chat_id]['data']['teacher_name'] = teacher_name
            user_states[chat_id]['state'] = config.STATE_WAITING_DATETIME
            logging.info(f"Teacher '{teacher_name}' received for chat_id {chat_id}")
            bot.send_message(chat_id, f"OK: Teacher '{teacher_name}'.\n3. What is the time and date of the lection start? Send it like `{config.TIME_FORMAT}{config.DATETIME_SPLIT_CHAR}{config.DATE_FORMAT}` (e.g., 14:45-20.04.2025)")
        else:
            bot.send_message(chat_id, "Please enter the teacher's name as text.")

    @bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == config.STATE_WAITING_DATETIME)
    def handle_datetime(message: Message):
        chat_id = message.chat.id
        logging.debug(f"Handling datetime input from chat_id {chat_id}")
        if message.text and message.text.strip():
            datetime_input = message.text.strip()
            try:
                time_str, date_str = datetime_input.split(config.DATETIME_SPLIT_CHAR)
                # Validate formats strictly
                valid_time = datetime.strptime(time_str, config.TIME_FORMAT)
                valid_date = datetime.strptime(date_str, config.DATE_FORMAT)

                user_states[chat_id]['data']['lection_time'] = time_str
                user_states[chat_id]['data']['lection_date'] = date_str
                user_states[chat_id]['state'] = config.STATE_WAITING_AUDIO
                logging.info(f"DateTime '{datetime_input}' received for chat_id {chat_id}")
                bot.send_message(chat_id, f"OK: Starts at {time_str} on {date_str}.\n4. Now send me the audio file of the lection!")
            except ValueError:
                logging.warning(f"Invalid datetime format received from chat_id {chat_id}: {datetime_input}")
                bot.send_message(chat_id, f"Format error: Please use exactly `{config.TIME_FORMAT}{config.DATETIME_SPLIT_CHAR}{config.DATE_FORMAT}` (e.g., 14:45-20.04.2025). Try again!")
            except Exception as e:
                 logging.error(f"Error parsing datetime from chat_id {chat_id}: {e}", exc_info=True)
                 bot.send_message(chat_id, "An error occurred processing the date and time. Please try again or use /reset.")
        else:
            bot.send_message(chat_id, "Please enter the date and time as text.")

    @bot.message_handler(content_types=['audio'], func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == config.STATE_WAITING_AUDIO)
    def handle_audio(message: Message):
        """Handles the received audio file, uploads it, and initiates processing."""
        chat_id = message.chat.id
        if chat_id not in user_states or 'data' not in user_states[chat_id]:
             logging.warning(f"Received audio from chat_id {chat_id} but no user state/data found. Ignoring.")
             bot.send_message(chat_id, "Please start the process with /start first.")
             return

        user_data = user_states[chat_id]['data']
        logging.info(f"Received audio file from chat_id {chat_id}. Metadata: {user_data}")
        # --- Start processing logic (integrated from previous logic.py) ---
        temp_file_path = None # Ensure variable exists for finally block
        try:
            if not message.audio: # Should not happen with content_types filter, but safe check
                logging.warning(f"Audio handler triggered but no audio object for chat_id {chat_id}")
                bot.send_message(chat_id, "An internal error occurred (code TGH-NA). Please try sending the audio again.")
                return

            # 1. Download the audio file
            bot.send_message(chat_id, f"Audio received ({message.audio.duration}s, {message.audio.mime_type or 'N/A'}). Downloading...")
            logging.debug(f"Attempting to download file_id {message.audio.file_id}")
            file_info = bot.get_file(message.audio.file_id)
            downloaded_file_bytes = bot.download_file(file_info.file_path)
            logging.debug(f"Downloaded {len(downloaded_file_bytes)} bytes for chat_id {chat_id}")

            # 2. Generate filename and save temporarily
            original_filename = message.audio.file_name if message.audio.file_name else "audio.oga"
            structured_filename = utils.generate_audio_filename(user_data, original_filename)
            logging.info(f"Generated filename: {structured_filename}")

            # Use tempfile for safer temporary storage within the designated folder
            # Create a temporary file directly, easier cleanup
            fd, temp_file_path = tempfile.mkstemp(suffix=f"_{structured_filename}", dir=config.TEMP_FOLDER)
            logging.info(f"Audio saving temporarily to {temp_file_path} for chat_id {chat_id}")
            with os.fdopen(fd, 'wb') as temp_audio_file:
                temp_audio_file.write(downloaded_file_bytes)
            # Don't close fd directly, fdopen handles it

            # 3. Upload to GCS
            bot.send_message(chat_id, "Uploading to secure storage...")
            gcs_uri = cloud_storage.upload_to_gcs(temp_file_path, structured_filename)

            if not gcs_uri:
                logging.error(f"GCS upload failed for chat_id {chat_id}, file: {structured_filename}")
                bot.send_message(chat_id, "Sorry, there was an error uploading your file. Please check logs or try again.")
                # State remains STATE_WAITING_AUDIO for retry
                return # Exit handler, keep state

            logging.info(f"File uploaded to {gcs_uri} for chat_id {chat_id}")
            bot.send_message(chat_id, f"File successfully uploaded: `{structured_filename}`. Starting analysis...")

            # 4. Initiate Transcription
            transcript = audio_processor.transcribe_audio_gcs(gcs_uri)

            if transcript is None: # Check for None, indicating error
                logging.error(f"Transcription failed for {gcs_uri} (chat_id {chat_id})")
                bot.send_message(chat_id, "Sorry, there was an error during the audio analysis (transcription).")
                # State remains STATE_WAITING_AUDIO for potential future retry logic? Or reset?
                # For now, let's reset the state
                del user_states[chat_id]
                logging.info(f"User state reset for chat_id {chat_id} after transcription error.")
                return # Exit handler

            # --- Transcription Success ---
            logging.info(f"Transcription result received for chat_id {chat_id}. Length: {len(transcript)}")
            bot.send_message(chat_id, f"Transcription complete!")

            # --- Placeholder for Analysis ---
            logging.info(f"Placeholder: Analyzing transcript for chat_id {chat_id}...")
            bot.send_message(chat_id, "Analyzing transcript (placeholder)...")
            # analysis_results = text_analyzer.analyze(transcript) # Call when ready

            # --- Placeholder for Doc Generation ---
            logging.info(f"Placeholder: Generating documents for chat_id {chat_id}...")
            bot.send_message(chat_id, "Generating documents (placeholder)...")
            # generated_docs = doc_generator.generate(analysis_results, user_data) # Call when ready

            # --- Send Results (Example: sending transcript chunk) ---
            # For now, just send a part of the transcript
            max_len = 4000 # Telegram message limit roughly
            summary_text = f"**Analysis Complete (Placeholders)**\n\n**Transcript Preview:**\n```\n{transcript[:max_len]}\n```"
            if len(transcript) > max_len:
                summary_text += "\n...(transcript truncated)"

            bot.send_message(chat_id, summary_text, parse_mode='Markdown')

            # Add sending of generated files here when ready
            # for doc_path in generated_docs:
            #    try:
            #        with open(doc_path, 'rb') as doc_file:
            #             bot.send_document(chat_id, doc_file)
            #        logging.info(f"Sent document {os.path.basename(doc_path)} to chat_id {chat_id}")
            #    except Exception as e:
            #        logging.error(f"Failed to send document {doc_path} to chat_id {chat_id}: {e}", exc_info=True)
            #        bot.send_message(chat_id, f"Failed to send document: {os.path.basename(doc_path)}")

            # --- End Placeholders ---

            # Reset state after successful processing
            del user_states[chat_id]
            logging.info(f"User state cleared for chat_id {chat_id} after successful processing.")

        except Exception as e:
            logging.error(f"An error occurred processing audio for chat_id {chat_id}: {e}", exc_info=True)
            try:
                bot.send_message(chat_id, "An unexpected internal error occurred during processing. Please use /reset and try again.")
            except Exception as send_e:
                logging.error(f"Failed to send error message to chat_id {chat_id}: {send_e}")
            # Optionally reset state on error
            if chat_id in user_states:
                del user_states[chat_id]
        finally:
             # --- Cleanup Temporary File ---
             if temp_file_path and os.path.exists(temp_file_path):
                 try:
                     os.remove(temp_file_path)
                     logging.info(f"Cleaned up temporary file: {temp_file_path}")
                 except OSError as e:
                     logging.error(f"Error deleting temporary file {temp_file_path}: {e}", exc_info=True)


    # --- Catch-all for unexpected messages/states ---
    @bot.message_handler(func=lambda message: True) # Catch everything else
    def handle_unknown(message: Message):
        chat_id = message.chat.id
        current_state_info = user_states.get(chat_id)
        state_val = current_state_info.get('state') if current_state_info else None
        logging.debug(f"Received unexpected message type '{message.content_type}' from chat_id {chat_id} in state {state_val}")

        if state_val == config.STATE_WAITING_DISCIPLINE:
            bot.send_message(chat_id, "Please send the discipline name as text, or use /reset.")
        elif state_val == config.STATE_WAITING_TEACHER:
            bot.send_message(chat_id, "Please send the teacher's name (no spaces), or use /reset.")
        elif state_val == config.STATE_WAITING_DATETIME:
            bot.send_message(chat_id, f"Please send the date and time in the format `{config.TIME_FORMAT}{config.DATETIME_SPLIT_CHAR}{config.DATE_FORMAT}`, or use /reset.")
        elif state_val == config.STATE_WAITING_AUDIO:
             if message.content_type == 'text':
                 bot.send_message(chat_id, "I'm waiting for the audio file. Please send the audio recording, or use /reset.")
             else:
                  bot.send_message(chat_id, f"I'm waiting for the audio file, but received '{message.content_type}'. Please send the audio, or use /reset.")
        else: # No state or unknown state
             bot.send_message(chat_id, "Not sure what you mean. Please use /start to begin processing a lecture.")

    logging.info("Telegram handlers registered.")