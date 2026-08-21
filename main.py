import os
import time
import random
import logging
import requests
from datetime import datetime, timezone, timedelta
from collections import deque

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получаем переменные
VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not VK_TOKEN or not GROUP_ID:
    logger.error("❌ Не заданы переменные окружения!")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID)
except ValueError:
    logger.error("❌ GROUP_ID должен быть числом")
    exit(1)

logger.info(f"✅ Переменные загружены. ID группы: {GROUP_ID}")

# СПИСОК ID КАРТИНОК (твой список)
PHOTOS_LIST = [
    "photo-239232916_456239539",
    "photo-239232916_456239540",
    "photo-239232916_456239541",
    "photo-239232916_456239542",
    "photo-239232916_456239543",
    "photo-239232916_456239544",
    "photo-239232916_456239545",
    "photo-239232916_456239546",
    "photo-239232916_456239547",
    "photo-239232916_456239548",
    "photo-239232916_456239549",
    "photo-239232916_456239550",
    "photo-239232916_456239551",
    "photo-239232916_456239552",
    "photo-239232916_456239553",
    "photo-239232916_456239554",
    "photo-239232916_456239555",
    "photo-239232916_456239556",
    "photo-239232916_456239557",
    "photo-239232916_456239558",
    "photo-239232916_456239559",
    "photo-239232916_456239560",
    "photo-239232916_456239561",
    "photo-239232916_456239562",
    "photo-239232916_456239563",
    "photo-239232916_456239564",
    "photo-239232916_456239565",
    "photo-239232916_456239566",
    "photo-239232916_456239567",
    "photo-239232916_456239568",
    "photo-239232916_456239569",
    "photo-239232916_456239570",
    "photo-239232916_456239571",
    "photo-239232916_456239572",
    "photo-239232916_456239573",
    "photo-239232916_456239574",
    "photo-239232916_456239575",
    "photo-239232916_456239576",
    "photo-239232916_456239577",
    "photo-239232916_456239578",
    "photo-239232916_456239579",
    "photo-239232916_456239580",
    "photo-239232916_456239581",
    "photo-239232916_456239582",
    "photo-239232916_456239583",
    "photo-239232916_456239584",
    "photo-239232916_456239585",
    "photo-239232916_456239586",
    "photo-239232916_456239587",
    "photo-239232916_456239588",
    "photo-239232916_456239589",
    "photo-239232916_456239590",
    "photo-239232916_456239591",
    "photo-239232916_456239592",
    "photo-239232916_456239593",
    "photo-239232916_456239594",
    "photo-239232916_456239595",
    "photo-239232916_456239596",
    "photo-239232916_456239597",
    "photo-239232916_456239598",
    "photo-239232916_456239599",
    "photo-239232916_456239600",
    "photo-239232916_456239601",
    "photo-239232916_456239602",
    "photo-239232916_456239603",
    "photo-239232916_456239604",
    "photo-239232916_456239605",
    "photo-239232916_456239606",
    "photo-239232916_456239607",
    "photo-239232916_456239608",
    "photo-239232916_456239609",
    "photo-239232916_456239610",
    "photo-239232916_456239611",
    "photo-239232916_456239612",
    "photo-239232916_456239613",
    "photo-239232916_456239614",
    "photo-239232916_456239615",
    "photo-239232916_456239616",
    "photo-239232916_456239617",
    "photo-239232916_456239618",
    "photo-239232916_456239619",
    "photo-239232916_456239620"
]

# Хранилище последних 10 картинок (очередь FIFO)
last_10_photos = deque(maxlen=10)

def get_unique_photo():
    """Выбирает картинку, которой не было в последних 10 публикациях"""
    if len(PHOTOS_LIST) <= 10:
        # Если картинок мало — просто берём случайную, иначе вообще не сможем выбрать
        return random.choice(PHOTOS_LIST)

    available = [p for p in PHOTOS_LIST if p not in last_10_photos]
    if not available:
        # На всякий случай, если вдруг все картинки в истории (маловероятно) — берём любую
        logger.warning("⚠️ Все картинки в истории последних 10, берём случайную.")
        return random.choice(PHOTOS_LIST)
    
    attachment = random.choice(available)
    last_10_photos.append(attachment)
    return attachment

def post_text_with_photo():
    """Постит текст с готовой картинкой из списка"""
    if not PHOTOS_LIST:
        logger.error("❌ Список картинок пуст! Заполни переменную PHOTOS_LIST в коде.")
        return False

    # Выбираем уникальную картинку (не из последних 10)
    attachment = get_unique_photo()
    
    # Новый текст поста
    message = (
        "Среди всех дел и «надо» я теперь каждый день оставляю одно доброе слово себе — "
        "моя маленькая фраза‑«обнимашка».\n\n"
        "Сегодня вот эта.\n\n"
        "Сохрани её, чтобы возвращаться, когда внутренний критик снова начнёт шептать «могла бы лучше». "
        "Пусть эта фраза будет твоим противовесом.\n\n"
        "Поставь ❤️, если тебе хочется в ленте чего‑то бережного, без давления.\n\n"
        "Перешли подруге, которой сегодня важно просто услышать: ты молодец.\n\n"
        "Делись своими фразами в комментариях — собираем копилку опоры. 🤍"
    )

    try:
        r = requests.post(
            "https://api.vk.com/method/wall.post",
            params={
                "owner_id": GROUP_ID,
                "message": message,
                "attachment": attachment,
                "access_token": VK_TOKEN,
                "v": "5.131"
            },
            timeout=10
        )
        
        result = r.json()
        
        if "error" in result:
            logger.error(f"❌ Ошибка публикации: {result['error']}")
            return False
        else:
            post_id = result["response"]["post_id"]
            logger.info(f"✅ УСПЕХ! Пост опубликован. ID: {post_id}, Картинка: {attachment}")
            return True

    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        return False

def get_moscow_time():
    """Возвращает текущее время по Москве (UTC+3)"""
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)

def main():
    logger.info("🚀 Бот запущен. Ожидаем 06:00 МСК для публикации...")
    
    last_posted_date = None  # чтобы не постить дважды в один день

    while True:
        try:
            now = get_moscow_time()
            current_date = now.date()
            current_hour = now.hour
            current_minute = now.minute

            # Проверяем: сейчас 06:00 и это новый день (не публиковали сегодня)
            if current_hour == 6 and current_minute == 0 and last_posted_date != current_date:
                logger.info("⏰ Время публикации: 06:00 МСК. Начинаем пост...")
                post_text_with_photo()
                last_posted_date = current_date
                # После публикации ждём до следующего 06:00 (чтобы не постить ещё раз в эту же минуту)
                time.sleep(60)
                continue

            # Если уже публиковали сегодня — просто ждём дальше
            if last_posted_date == current_date:
                time.sleep(30)
                continue

            # В остальное время — спим 30 секунд и проверяем снова
            time.sleep(30)

        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception as e:
            logger.exception("⚠️ Ошибка в цикле, пробуем снова через 10 сек...")
            time.sleep(10)

if __name__ == "__main__":
    main()
