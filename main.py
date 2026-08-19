import os
import time
import logging
import requests
from PIL import Image

# Настройка логов (Bothost покажет их в панели)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получаем переменные из панели Bothost
VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID_STR = os.getenv("GROUP_ID")

if not VK_TOKEN or not GROUP_ID_STR:
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Не заданы переменные VK_TOKEN или GROUP_ID в панели Bothost!")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID_STR)
except ValueError:
    logger.error("❌ GROUP_ID должен быть числом (например, -123456789)")
    exit(1)

logger.info(f"✅ Переменные загружены. ID группы: {GROUP_ID}")

def generate_image(filename="temp_img.png"):
    """Создает простой цветной квадрат вместо сложной генерации"""
    try:
        # Цвет фона (пастельный синий)
        img = Image.new('RGB', (1080, 1080), color=(70, 130, 180))
        img.save(filename)
        logger.info(f"🖼️ Картинка создана: {filename}")
        return filename
    except Exception as e:
        logger.error(f"❌ Ошибка создания картинки: {e}")
        return None

def post_to_vk(image_path):
    """Логика постинга с исправлением ошибки 'method unavailable'"""
    if not image_path:
        return False

    try:
        group_id_abs = abs(GROUP_ID)

        # 1. Получаем сервер загрузки (самый надежный метод)
        r = requests.post("https://api.vk.com/method/photos.getUploadServer",
                          params={"group_id": group_id_abs, "access_token": VK_TOKEN, "v": "5.131"})
        data = r.json()
        if "error" in data:
            logger.error(f"❌ Ошибка сервера загрузки: {data['error']}")
            return False
        
        upload_url = data["response"]["upload_url"]

        # 2. Загружаем файл
        with open(image_path, "rb") as f:
            files = {"file": f}
            r = requests.post(upload_url, files=files)
        
        photo_data = r.json()
        if "error" in photo_data:
            logger.error(f"❌ Ошибка загрузки файла: {photo_data['error']}")
            return False

        # 3. Сохраняем фото в альбоме группы
        r = requests.post("https://api.vk.com/method/photos.save",
                          params={
                              "server": photo_data["server"],
                              "photo": photo_data["photo"],
                              "hash": photo_data["hash"],
                              "group_id": group_id_abs,
                              "access_token": VK_TOKEN,
                              "v": "5.131"
                          })
        save_data = r.json()
        if "error" in save_data:
            logger.error(f"❌ Ошибка сохранения фото: {save_data['error']}")
            return False

        photo_id = save_data["response"][0]["id"]
        owner_id = save_data["response"][0]["owner_id"]
        attachment = f"photo{owner_id}_{photo_id}"
        logger.info(f"✅ Фото сохранено. Attachment: {attachment}")

        # 4. Постим на стену
        r = requests.post("https://api.vk.com/method/wall.post",
                          params={
                              "owner_id": GROUP_ID,
                              "message": "Привет! Это тестовый пост от бота на Bothost. 🎉\nКартинка сгенерирована кодом.",
                              "attachment": attachment,
                              "access_token": VK_TOKEN,
                              "v": "5.131"
                          })
        
        result = r.json()
        if "error" in result:
            logger.error(f"❌ Ошибка публикации поста: {result['error']}")
            return False
        else:
            post_id = result["response"]["post_id"]
            logger.info(f"✅ УСПЕХ! Пост опубликован. ID: {post_id}")
            return True

    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        return False

def main():
    logger.info("🚀 Бот запущен. Начинаем цикл работы...")
    
    while True:
        try:
            # Генерируем картинку
            img_file = generate_image()
            
            if img_file:
                # Постим её
                post_to_vk(img_file)
                
                # Удаляем временный файл (экономим место на хостинге)
                if os.path.exists(img_file):
                    os.remove(img_file)
            
            # Ждем 60 секунд перед следующим постом (для теста)
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
