import os
import time
import random
import logging
import requests

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

# СПИСОК ID КАРТИНОК, которые ты загрузил вручную в альбом.
# Формат: photo{owner_id}_{photo_id}
# Пример: photo-239232916_456240550
# Вставь сюда свои ID, которые скопировал из адресной строки ВК.
PHOTOS_LIST = [
    "photo-239232916_456239526",
    "photo-239232916_456239525",
    "photo-239232916_456239524",
    # Добавь сюда еще сколько нужно
]

def post_text_with_photo():
    """Постит текст с готовой картинкой из списка"""
    if not PHOTOS_LIST:
        logger.error("❌ Список картинок пуст! Заполни переменную PHOTOS_LIST в коде.")
        return False

    # Выбираем случайную картинку из списка
    attachment = random.choice(PHOTOS_LIST)
    
    message = "Привет! Это пост от бота. 📸 Картинка уже была загружена вручную в альбом."

    try:
        r = requests.post("https://api.vk.com/method/wall.post",
                          params={
                              "owner_id": GROUP_ID,
                              "message": message,
                              "attachment": attachment,  # <-- Вот тут магия: просто подставляем ID
                              "access_token": VK_TOKEN,
                              "v": "5.131"
                          },
                          timeout=10)
        
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

def main():
    logger.info("🚀 Бот запущен. Начинаем цикл работы...")
    
    while True:
        try:
            # Постим текст + готовую картинку
            post_text_with_photo()
            
            # Ждем 60 секунд перед следующим постом
            logger.info("⏳ Пауза 60 сек...")
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception as e:
            logger.exception("⚠️ Ошибка в цикле, пробуем снова через 10 сек...")
            time.sleep(10)

if __name__ == "__main__":
    main()
