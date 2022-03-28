import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException

from exceptions import BadResponseException, EmptyListException

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()
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


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
        logger.info(f'Сообщение "{message}" удачно отправлено')
    except telegram.TelegramError() as error:
        logger.error(error, exc_info=True)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error('Сервер не отвечает')
            raise BadResponseException('Сервер не отвечает. Попробуйте позже.')
        try:
            return response.json()
        except JSONDecodeError as error:
            logger.error(error, exc_info=True)
    except RequestException:
        logger.error('Произошёл сбой при запросе к API')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is not dict:
        raise TypeError('API возвращает не словарь')
    homeworks = response.get('homeworks')
    if type(homeworks) is not list:
        raise TypeError('API домашних работ возвращает не список.')
    if len(homeworks) == 0:
        raise EmptyListException('Список домашних заданий пуст.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if ('homework_name' or 'status') not in homework:
        raise KeyError('Отсутствует ключ homework_name/status')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Неизвестный статус')
        raise KeyError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Проверьте доступность всех токенов')
        raise PermissionError('Проверьте доступность всех токенов')
    status_homework = None
    previous_error = None
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            homework = homeworks[0]
            message = parse_status(homework)
            if status_homework != homework.get('status'):
                send_message(bot, message)
                status_homework = homework.get('status')
            else:
                logger.debug('Статус домашней работы не изменён')
            current_timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if previous_error != message:
                send_message(bot, message)
                previous_error = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
