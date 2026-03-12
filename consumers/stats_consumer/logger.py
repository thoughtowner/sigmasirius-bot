import logging

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {'format': '%(asctime)s %(levelname)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'default'},
    },
    'loggers': {
        'stats_consumer_logger': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
}

logger = logging.getLogger('stats_consumer_logger')
