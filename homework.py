import logging
import os
import sys
import time
import requests
import telegram

from dotenv import load_dotenv

from requests import RequestException

from http import HTTPStatus

from logging import StreamHandler

from exceptions import BadResponseException, EmptyListException

load_dotenv()
# В переменной __name__ хранится имя пакета;
# это же имя будет присвоено логгеру.
# Это имя будет передаваться в логи, в аргумент %(name)
logger = logging.getLogger(__name__)
# Устанавливаем уровень, с которого логи будут сохраняться в файл
logger.setLevel(logging.DEBUG)
# Создаем форматер
# asctime — время, levelname — уровень важности, message — текст сообщения
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Указываем обработчик логов
handler = StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 5
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
    except Exception:
        logger.error(f'Сообщение "{message}" не отправлено')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error('Сервер не отвечает')
            raise BadResponseException('Сервер не отвечает. Попробуйте позже.')
        return response.json()
    except RequestException:
        logger.error('Произошёл сбой при запросе к API')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response['homeworks']) != list:
        raise TypeError('API возвращает не список.')
    if len(response.get('homeworks')) == 0:
        raise EmptyListException('Список домашних заданий пуст.')
    else:
        return response.get('homeworks')


def parse_status(homeworks):
    """Извлекает статус домашней работы."""
    homework_name = homeworks.get('homework_name')
    homework_status = homeworks.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Неизвестный статус')
        raise KeyError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    logging.critical('Проверьте доступность всех токенов')
    return False


def main():
    """Основная логика работы бота."""
    check_tokens()
    status_homework = None
    previous_error = None
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks[0])
            if status_homework != homeworks[0].get('status'):
                send_message(bot, message)
                status_homework = homeworks[0].get('status')
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
