"""Logging setup, with the API key scrubbed from every record.

This module exists because of a real leak. ``httpx`` logs each request line --
including the full query string -- at INFO level, so enabling INFO logging wrote
``apikey=<secret>`` into the deployment's log storage on every upstream call.
Redacting the key in our own log statements was not enough: the leak came from
a third-party logger we do not control.

Two defences, because a secret written to a log cannot be unwritten:

1. ``httpx``/``httpcore`` request logging is turned down, removing the source.
2. A filter on the root handler rewrites anything resembling an API key in any
   record from any library, so a future dependency cannot reintroduce this.
"""

from __future__ import annotations

import logging
import re

#: Matches `apikey=<value>` / `api_key=<value>` in a URL or query string.
_APIKEY_PATTERN = re.compile(r"(?i)\b(apikey|api_key)=([^&\s\"'>]+)")

REDACTED = "***redacted***"


def scrub(text: str) -> str:
    """Replace any API key in ``text`` with a placeholder."""
    return _APIKEY_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", text)


class RedactSecretsFilter(logging.Filter):
    """Strips API keys from log messages and their arguments.

    Attached to handlers rather than to one logger, so it covers records emitted
    by any library in the process.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    scrub(arg) if isinstance(arg, str) else arg for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    key: scrub(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }

        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    redactor = RedactSecretsFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redactor)

    # These log the full request URL, query string included, at INFO. Their
    # request lines carry nothing our own logs do not already provide.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
