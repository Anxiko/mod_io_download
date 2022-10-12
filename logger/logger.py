import logging
import sys
from logging import Logger

ROOT_LOGGER_NAME: str = 'mod_io_downloader'


def get_root_logger() -> Logger:
	return logging.getLogger(ROOT_LOGGER_NAME)


def get_logger(name: str) -> Logger:
	return logging.getLogger(f'{ROOT_LOGGER_NAME}.{name}')


def logger_set_up() -> None:
	root_logger: Logger = get_root_logger()
	root_logger.setLevel(logging.DEBUG)

	stdout_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.DEBUG)

	formatter: logging.Formatter = logging.Formatter(
		'[${levelname}]\t[${asctime}]\t[${pathname}:${funcName}():${lineno}]: ${message}',
		datefmt='%Y-%m-%d %H:%M:%S', style='$'
	)
	stdout_handler.setFormatter(formatter)
	root_logger.addHandler(stdout_handler)
