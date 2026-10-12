"""Defaults shared across the package."""

OLLAMA_MODEL = "translategemma:12b"
ANTHROPIC_MODEL = "claude-opus-5-5"
OPENAI_API = "https://api.openai.com/v1"

# Where the keys of the API providers are read from, besides the environment.
ENV_FILE = ".env"
OPENAI_KEY_VARIABLE = "OPENAI_API_KEY"
ANTHROPIC_KEY_VARIABLE = "ANTHROPIC_API_KEY"
