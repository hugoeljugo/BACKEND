import logging.config
import structlog
from pythonjsonlogger import jsonlogger
import coloredlogs

def setup_logging():
    # Define custom color scheme
    FIELD_STYLES = {
        'asctime': {'color': 'green'},
        'levelname': {'bold': True, 'color': 'cyan'},
        'name': {'color': 'white'},
        'message': {'color': 'white'}
    }

    LEVEL_STYLES = {
        'DEBUG': {'color': 'blue'},
        'INFO': {'color': 'green'},
        'WARNING': {'color': 'yellow'},
        'ERROR': {'color': 'red'},
        'CRITICAL': {'bold': True, 'color': 'red'}
    }

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "fmt": "%(levelname)s %(name)s %(timestamp)s %(message)s"
            },
            "colored": {
                "()": coloredlogs.ColoredFormatter,
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                "field_styles": FIELD_STYLES,
                "level_styles": LEVEL_STYLES
            }
        },
        "handlers": {
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json"
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "colored"
            }
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": "INFO"
            }
        }
    }
    
    logging.config.dictConfig(logging_config)
    
    # Configure structlog to use both formatters
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )