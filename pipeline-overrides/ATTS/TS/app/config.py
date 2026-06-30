import os
from dotenv import load_dotenv

load_dotenv()

def get_env_variable(name, default=None, cast_type=None):
    """Retrieve an environment variable or raise an exception if not set.
    Optionally, provide a default value and a type to cast the variable."""
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"{name} environment variable is not set")
    if cast_type:
        try:
            value = cast_type(value)
        except ValueError as e:
            raise ValueError(f"Error casting {name} to {cast_type}: {e}")
    return value

CONFIG = {
    "TS_DOCKER_PORT": get_env_variable("TS_DOCKER_PORT", 7020, int),
    "REDIS_URL": get_env_variable("REDIS_URL"),
    "MINIO_HOST": get_env_variable("MINIO_HOST"),
    "MINIO_TS_USER": get_env_variable("MINIO_TS_USER"),
    "MINIO_TS_PASSWORD": get_env_variable("MINIO_TS_PASSWORD"),
    "MINIO_DEBATE_BUCKET_NAME": get_env_variable("MINIO_DEBATE_BUCKET_NAME"),
    "MINIO_PRESIGNED_URL_EXPIRATION": get_env_variable("MINIO_PRESIGNED_URL_EXPIRATION", 3600, int),
    "MINIO_SECURE": get_env_variable("MINIO_SECURE", False, bool),
    # Azure AI Speech (replaces WhisperX / TS_AI_MODEL + TS_THREAD_COUNT)
    "SPEECH_KEY": get_env_variable("SPEECH_KEY"),
    "SPEECH_REGION": get_env_variable("SPEECH_REGION"),
    "SPEECH_LANGUAGE": get_env_variable("SPEECH_LANGUAGE", "nl-NL"),
    "LOCAL_AUDIO_SAVE_DIR": get_env_variable("LOCAL_AUDIO_SAVE_DIR"),
    "AUDIO_FILE_FORMAT": get_env_variable("AUDIO_FILE_FORMAT", "wav"),
}
