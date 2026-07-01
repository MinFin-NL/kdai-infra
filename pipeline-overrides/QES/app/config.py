# app/config.py
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
    "QES_DOCKER_PORT": get_env_variable("QES_DOCKER_PORT"),
    "REDIS_URL": get_env_variable("REDIS_URL"),
    "MINIO_HOST": get_env_variable("MINIO_HOST"),
    "MINIO_QES_USER": get_env_variable("MINIO_QES_USER"),
    "MINIO_QES_PASSWORD": get_env_variable("MINIO_QES_PASSWORD"),
    "MINIO_DEBATE_BUCKET_NAME": get_env_variable("MINIO_DEBATE_BUCKET_NAME"),
    "MINIO_PRESIGNED_URL_EXPIRATION": get_env_variable("MINIO_PRESIGNED_URL_EXPIRATION", 3600, int),
    "MINIO_SECURE": get_env_variable("MINIO_SECURE", False, bool),
    "BACKEND_QES_RESULT_URL": get_env_variable("BACKEND_QES_RESULT_URL"),
    "BACKEND_QES_ERROR_URL": get_env_variable("BACKEND_QES_ERROR_URL"),
    "STATIC_API_KEY": get_env_variable("STATIC_API_KEY"),
    # Azure OpenAI (replaces the Ollama LLM_URL / LLM_MODEL). The question extractor calls the
    # chat-completions REST API directly with `requests`, so no SDK is needed.
    "AZURE_OPENAI_ENDPOINT": get_env_variable("AZURE_OPENAI_ENDPOINT"),
    "AZURE_OPENAI_KEY": get_env_variable("AZURE_OPENAI_KEY"),
    "AZURE_OPENAI_DEPLOYMENT": get_env_variable("AZURE_OPENAI_DEPLOYMENT"),
    "AZURE_OPENAI_API_VERSION": get_env_variable("AZURE_OPENAI_API_VERSION", "2024-06-01"),
}
