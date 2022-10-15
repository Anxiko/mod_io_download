import logging
import os
import sys
from logging import Logger
from logging.handlers import RotatingFileHandler

ROOT_LOGGER_NAME: str = 'mod_io_downloader'
_LOGGER_FILE_NAME: str = 'mod_io_downloader.log'


def get_root_logger() -> Logger:
	return logging.getLogger(ROOT_LOGGER_NAME)


def get_logger(name: str) -> Logger:
	return logging.getLogger(f'{ROOT_LOGGER_NAME}.{name}')


def logger_set_up() -> None:
	root_logger: Logger = get_root_logger()
	root_logger.setLevel(logging.DEBUG)

	detailed_formatter: logging.Formatter = logging.Formatter(
		'[${levelname}]\t[${asctime}]\t[${pathname}:${funcName}():${lineno}]: ${message}',
		datefmt='%Y-%m-%d %H:%M:%S', style='$'
	)
	basic_formatter: logging.Formatter = logging.Formatter(
		'[${levelname}]\t[${asctime}]: ${message}',
		datefmt='%Y-%m-%d %H:%M:%S', style='$'
	)

	stdout_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.INFO)
	stdout_handler.setFormatter(basic_formatter)

	file_handler: RotatingFileHandler = RotatingFileHandler(
		_LOGGER_FILE_NAME, encoding="utf8",
		maxBytes=(1 * 1024 ** 2),  # 1MiB
		backupCount=10
	)
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(detailed_formatter)

	root_logger.addHandler(stdout_handler)

	if os.getenv("MODIO_LOG_TO_FILE") == 1:
		root_logger.addHandler(file_handler)
