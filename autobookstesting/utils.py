import logging
from loguru import logger
import sys
from datetime import datetime
#Formatter to remove patterns from log output
class RedactingFormatter:
    def __init__(self, patterns=None, source_fmt=None):
        super().__init__()
        self.patterns = patterns
        self.fmt = source_fmt

    def format(self, record):
        scrubbed = record["message"]
        for pattern in self.patterns:
            scrubbed = scrubbed.replace(pattern, "")
        record["extra"]["scrubbed"] = scrubbed
        return self.fmt

#Handler to intercept logging messages for loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )