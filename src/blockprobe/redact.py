"""Removal of secrets and personal data from everything BlockProbe emits.

Probe output routinely contains API keys, absolute home paths and e-mail
addresses, and the artefacts it produces (the Markdown report, a pasted
failure message) end up in public bug reports. Every value that leaves the
process - evidence lines, failure messages, environment values - passes
through this module first.

The patterns are compiled once at import time and applied in a fixed order:
secrets first, e-mail addresses next, home paths last, so a path that
happens to contain a token is redacted as a path and not as a token.

Known limitations:

- A Windows user name that contains a space ("C:\\Users\\John Smith\\run.log")
  still leaks the part after the space: the user name pattern stops at
  whitespace, so only "John" is replaced.
- The macOS home directory ("/Users/dan") has no drive letter and is not
  matched by the Windows pattern, nor by the POSIX pattern ("/home/dan").
- The Windows home pattern is case-insensitive. That is safe: Windows paths
  are case-insensitive, "Users" is a fixed segment, and the pattern still
  requires a drive letter, a separator and a user name, so it can only fire
  on something that really is a home path.
"""

import re
from enum import Enum

from pydantic import BaseModel

HOME_PLACEHOLDER = "<HOME>"

# (pattern, replacement) pairs, applied in this order.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # OpenAI-style key, in its modern spellings: "sk-", "sk-proj-",
    # "sk-svcacct-", and any casing. The lower bound of 10 characters
    # admits the short keys that show up in fixtures and test doubles; the
    # left boundary keeps ordinary words that merely end in "sk-"
    # ("task-1234567890") intact.
    (re.compile(r"(?i)(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{10,}"), "<KEY>"),
    # Project key.
    (re.compile(r"atr_[A-Za-z0-9_-]{16,}"), "<KEY>"),
    # GitHub token.
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "<TOKEN>"),
    # Bearer header.
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"), "Bearer <TOKEN>"),
    # "apiKey" assignment, with or without quotes and camel case. The name
    # and the separator are captured and re-emitted, so an environment
    # variable stays readable: "CORTENSOR_API_KEY=secret" becomes
    # "CORTENSOR_API_KEY=<KEY>".
    (re.compile(r"""(?i)(api[-_]?key["']?\s*[:=]\s*["']?)[^"'\s,}]+"""), r"\1<KEY>"),
    # E-mail address.
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    # Windows home directory, in both spellings: "C:\Users\dan" and
    # "C:/Users/dan". Home paths come last so that a path holding a token
    # is redacted as a path.
    (re.compile(r"(?i)[A-Za-z]:[\\/]Users[\\/][^\\/\s]+"), HOME_PLACEHOLDER),
    # POSIX home directory.
    (re.compile(r"/home/[^/\s]+"), HOME_PLACEHOLDER),
)


def redact_text(text: str) -> str:
    """Return *text* with secrets, e-mail addresses and home paths replaced."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: object) -> object:
    """Return *value* with every string it contains redacted.

    Strings are redacted, dictionaries map over their keys and values,
    lists and tuples map over their items, and everything else is returned
    unchanged. Enum members are returned unchanged too: they are string
    subclasses, but their identity is meaningful and redaction would
    quietly turn them into plain strings.
    """
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {redact_value(key): redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value


def redact_model(model: BaseModel) -> BaseModel:
    """Return a redacted deep copy of *model*; the original is untouched.

    Every string the model holds is redacted, including the items of list
    fields and the fields of nested models, so that a summary carrying
    probe results is scrubbed all the way down.

    Redaction preserves types: an enum stays an enum and a list stays a
    list. The copy is deliberate rather than a re-validation - re-running
    the model through ``model_validate`` would reject the unknown-status
    string that the probe runner deliberately tolerates on a probe. The
    models use pydantic's default ``extra="ignore"``, so ``model_extra``
    is always empty and there are no extra fields to redact.
    """
    clone = model.model_copy(deep=True)
    for name in type(clone).model_fields:
        value = getattr(clone, name)
        redacted = _redact_field(value)
        if redacted is not value:
            setattr(clone, name, redacted)
    return clone


def _redact_field(value: object) -> object:
    """Redact one field value, descending into nested models."""
    if isinstance(value, BaseModel):
        return redact_model(value)
    if isinstance(value, list):
        return [_redact_field(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_field(item) for item in value)
    if isinstance(value, dict):
        return {redact_value(key): _redact_field(item) for key, item in value.items()}
    return redact_value(value)
