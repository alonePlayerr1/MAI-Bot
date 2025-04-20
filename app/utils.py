# app/utils.py
import logging
import os
import sys
from datetime import datetime
import config # Import the config module directly

def setup_logging():
    """Configures logging for the application."""
    # Ensure log directory exists (redundant if config does it, but safe)
    os.makedirs(config.LOG_FOLDER, exist_ok=True)

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s', # Added module/line info
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout) # Also print logs to console
        ]
    )
    # Quieten noisy libraries
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO) # Adjust if needed for telebot

    logging.info("="*20 + " Logging setup complete " + "="*20)
    # Now check credentials file existence after logger is ready
    config.check_credentials_file()


def generate_audio_filename(metadata: dict, original_filename: str | None) -> str:
    """Generates a structured filename for the audio file."""
    try:
        # Ensure all keys exist, provide defaults if necessary
        discipline = metadata.get('discipline', 'UnknownDiscipline')
        teacher = metadata.get('teacher_name', 'UnknownTeacher')
        date_str = metadata.get('lection_date', 'UnknownDate')
        time_str = metadata.get('lection_time', 'UnknownTime')

        # Basic sanitization (replace spaces and potentially problematic chars)
        safe_discipline = discipline.replace(" ", "_").replace("/", "-").replace("\\", "-")
        safe_teacher = teacher.replace(" ", "_").replace("/", "-").replace("\\", "-")

        if original_filename:
             base_name, extension = os.path.splitext(original_filename)
             if not extension:
                 extension = '.oga' # Default extension if Telegram doesn't provide one or filename missing
        else:
             extension = '.oga' # Default if original filename is None

        # Format time string consistently for filename
        safe_time_str = time_str.replace(":", "-")

        filename = config.METADATA_SEPARATOR.join([
            safe_discipline,
            safe_teacher,
            date_str, # Date format should be filename-safe already
            safe_time_str,
            f"original{extension}" # Keep original extension
        ])
        # Limit filename length if necessary (though unlikely with this structure)
        max_len = 200
        if len(filename) > max_len:
             filename = filename[:max_len-len(extension)] + extension
             logging.warning(f"Generated filename was truncated: {filename}")

        return filename
    except Exception as e:
        logging.error(f"Error generating filename: {e}", exc_info=True)
        # Fallback filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_original = original_filename.replace(" ", "_").replace("/", "-").replace("\\", "-") if original_filename else "audio.oga"
        return f"fallback_{timestamp}_{safe_original[-50:]}" # Limit original name part in fallback