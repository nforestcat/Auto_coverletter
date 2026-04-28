import logging
import os
from logging.handlers import RotatingFileHandler # 추가된 부분

def get_logger(name: str):
    """콘솔과 파일에 동시에 로그를 남기는 로거를 반환합니다."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # 일반 FileHandler 대신 RotatingFileHandler 사용
        # maxBytes: 5MB 단위로 끊기, backupCount: 이전 로그 3개까지 유지
        file_handler = RotatingFileHandler(
            "app_log.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
        )
        file_formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger