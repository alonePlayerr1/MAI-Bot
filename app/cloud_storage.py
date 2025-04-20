# app/cloud_storage.py
import logging
from google.cloud import storage
from google.api_core.exceptions import GoogleAPICallError, NotFound
import config

# Initialize client only if credentials file exists
storage_client = None
if config.credentials_exist:
    try:
        storage_client = storage.Client.from_service_account_json(config.GOOGLE_APP_CREDENTIALS)
        logging.info("Google Cloud Storage client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Google Cloud Storage client: {e}", exc_info=True)
        storage_client = None # Ensure it's None if init fails

def upload_to_gcs(source_file_path: str, destination_blob_name: str) -> str | None:
    """Uploads a file to the GCS bucket specified in config."""
    if not storage_client:
        logging.error("Cannot upload to GCS: Storage client not initialized (check credentials path and permissions).")
        return None

    try:
        bucket = storage_client.bucket(config.GCS_BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        logging.info(f"Attempting to upload '{source_file_path}' to 'gs://{config.GCS_BUCKET_NAME}/{destination_blob_name}'")
        blob.upload_from_filename(source_file_path)
        logging.info(f"Successfully uploaded to GCS.")

        gcs_uri = f"gs://{config.GCS_BUCKET_NAME}/{destination_blob_name}"
        return gcs_uri

    except NotFound:
        logging.error(f"GCS Bucket '{config.GCS_BUCKET_NAME}' not found or no permissions.")
        return None
    except GoogleAPICallError as e:
        logging.error(f"GCS API call error during upload: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during GCS upload: {e}", exc_info=True)
        return None

# Add other GCS functions if needed (e.g., delete_blob, download_blob)