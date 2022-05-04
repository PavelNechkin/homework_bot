import logging
import os
import time
from http import HTTPStatus

import requests
from simplejson.errors import JSONDecodeError
from dotenv import load_dotenv
from telegram import Bot, TelegramError
from logging.handlers import RotatingFileHandler

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class ServerError(Exception):
    """Ошибки сервера."""

    pass


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Message sent')
    except TelegramError:
        logger.error('Bot was unable to send a message')
        raise TelegramError


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except ServerError:
        logger.error('Server is not responding')
    if response.status_code != HTTPStatus.OK:
        logger.error('Server is not responding')
        raise ServerError('сервер не отвечает')
    try:
        home_work_inform = response.json()
    except JSONDecodeError:
        logger.error('Json conversion error')
    return home_work_inform


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        logger.error('Unknown data type')
        raise TypeError('неизвестный тип данных')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logger.error('Unknown data type')
        raise TypeError('неизвестный тип данных')
    if homeworks is None:
        logger.error('API response does not contain a key')
        raise KeyError('Ответ API не содержит ключ')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        logger.error('API response does not contain required information')
        raise KeyError('Ответ API не содержит необходимую информацию')
    if homework_name is None:
        logger.error('API response does not contain required information')
        raise KeyError('Ответ API не содержит необходимую информацию')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    logger.critical('Missing required environment variables')
    return False


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    check_tokens()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != message:
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
