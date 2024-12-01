import logging.config
import structlog
from pythonjsonlogger import jsonlogger

def setup_logging():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "fmt": "%(levelname)s %(name)s %(timestamp)s %(message)s"
            }
        },
        "handlers": {
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json"
            }
        },
        "loggers": {
            "": {
                "handlers": ["json"],
                "level": "INFO"
            }
        }
    }
    
    logging.config.dictConfig(logging_config)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    ) 