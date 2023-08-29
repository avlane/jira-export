"""Read connection settings from environment variables."""
import os

URL_VAR = "JIRA_URL"
EMAIL_VAR = "JIRA_EMAIL"
TOKEN_VAR = "JIRA_API_TOKEN"


class ConfigError(Exception):
    pass


def from_env(environ=None):
    """Return (base_url, email, token) or raise ConfigError naming what is missing."""
    env = os.environ if environ is None else environ
    missing = [name for name in (URL_VAR, EMAIL_VAR, TOKEN_VAR) if not env.get(name)]
    if missing:
        raise ConfigError("missing environment variable(s): " + ", ".join(missing))
    base = env[URL_VAR].strip().rstrip("/")
    if not base.startswith("https://"):
        raise ConfigError("{} must start with https:// (got {!r})".format(URL_VAR, base))
    return base, env[EMAIL_VAR].strip(), env[TOKEN_VAR].strip()


def _whole_number(env, name, default):
    raw = env.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("{} must be a whole number (got {!r})".format(name, raw))
    if value < 0:
        raise ConfigError("{} must not be negative".format(name))
    return value


def tuning(environ=None):
    """Optional knobs: JIRA_TIMEOUT (seconds per request) and JIRA_MAX_RETRIES (429 and 5xx retries)."""
    env = os.environ if environ is None else environ
    return {"timeout": _whole_number(env, "JIRA_TIMEOUT", 60), "max_retries": _whole_number(env, "JIRA_MAX_RETRIES", 5)}
