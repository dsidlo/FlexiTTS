#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

LOG_FILE = Path('/tmp/FlexiTTS.log')


def setup_script_logging(name: str) -> logging.Logger:
    """Configure a script logger that always appends to /tmp/FlexiTTS.log.

    GPU-specific loggers are intentionally not configured here.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    handler.setFormatter(logging.Formatter(f'%(asctime)s [%(levelname)s] [{name}] %(message)s'))
    logger.addHandler(handler)
    return logger


class _StreamToLogger:
    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self._buffer = ''

    def write(self, message: str) -> int:
        if not message:
            return 0
        self._buffer += message
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            line = line.rstrip()
            if line:
                self.logger.log(self.level, line)
        return len(message)

    def flush(self) -> None:
        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.strip())
        self._buffer = ''


def redirect_std_streams(logger: logging.Logger) -> None:
    sys.stdout = _StreamToLogger(logger, logging.INFO)
    sys.stderr = _StreamToLogger(logger, logging.ERROR)
