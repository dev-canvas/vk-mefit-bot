import os
import time
import json
import re
import random
import logging
import threading
import requests
from datetime import datetime, timezone, timedelta
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Переменные окружения ──────────────────────────────
VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")

if not VK_TOKEN or not GROUP_ID:
    logger.error("❌ Не заданы переменные окружения!")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID)
except ValueError:
    logger.error("❌ GROUP_ID должен быть числом")
    exit(1)

if not AUTH_TOKEN:
    logger.warning("⚠️ AUTH_TOKEN не задан! Авторизация отключена — кто угодно может менять время.")

logger.info(f"✅ Переменные загружены. ID группы: {GROUP_ID}")

# ── Хранилище времени публикации ─────────────────────
SCHEDULE_FILE = "schedule.json"

def load_schedule():
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("publish_time", "06:00")
    except (FileNotFoundError, json.JSONDecodeError):
        return "06:00"

def save_schedule(time_str):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump({"publish_time": time_str}, f, ensure_ascii=False)

# ── Flask-сервер ─────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://dev-canvas.github.io",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
        "supports_credentials": True,
    }
})

def check_auth():
    """Проверяет заголовок X-Auth-Token. Возвращает True если совпадает или токен не задан."""
    if not AUTH_TOKEN:
        return True
    token = request.headers.get("X-Auth-Token", "")
    return token == AUTH_TOKEN

@app.route("/api/schedule/publish_time", methods=["GET"])
def get_publish_time():
    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401
    response = jsonify({"publish_time": load_schedule()})
    response.headers["Access-Control-Allow-Origin"] = "https://dev-canvas.github.io"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token"
    return response

@app.route("/api/schedule/publish_time", methods=["POST", "OPTIONS"])
def set_publish_time():
    # Обработка preflight (OPTIONS)
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers["Access-Control-Allow-Origin"] = "https://dev-canvas.github.io"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token"
        return response

    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401

    data = request.get_json(silent=True)
    if not data or "time" not in data:
        time_str = request.form.get("time")
    else:
        time_str = data["time"]

    if not time_str:
        return jsonify({"error": "Параметр 'time' обязателен"}), 400

    if not re.match(r"^(?\d|2[0-3]):[0-5]\d\$", time_str):
        return jsonify({"error": "Неверный формат. Используйте HH:MM (24ч)"}), 400

    save_schedule(time_str)
    logger.info(f"⏰ Время публикации обновлено: {time_str}")

    response = jsonify({"status": "ok", "publish_time": time_str})
    response.headers["Access-Control-Allow-Origin"] = "https://dev-canvas.github.io"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token"
    return response

# ── Список ID картинок ────────────────────────────────
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
    "photo-239232916_456239620",
]

last_10_photos = deque(maxlen=10)

def get_unique_photos(count=3):
    if len(PHOTOS_LIST) <= 10:
        return random.sample(PHOTOS_LIST, min(count, len(PHOTOS_LIST)))
    available = [p for p in PHOTOS_LIST if p not in last_10_photos]
    if len(available) < count:
        logger.warning("⚠️ Недостаточно уникальных картинок, берём сколько есть.")
        return random.sample(available, len(available)) if available else [random.choice(PHOTOS_LIST)]
    chosen = random.sample(available, count)
    for photo in chosen:
        last_10_photos.append(photo)
    return chosen

def post_text_with_photo():
    if not PHOTOS_LIST:
        logger.error("❌ Список картинок пуст!")
        return False
    attachments = get_unique_photos(3)
    message = (
        "Листай  👉\n"
        "Выбери 1 или 2 или 3  👉\n"
        "Твоя опора на сегодня ❤️"
    )
    try:
        r = requests.post(
            "https://api.vk.com/method/wall.post",
            params={
                "owner_id": GROUP_ID,
                "message": message,
                "attachment": ",".join(attachments),
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
            logger.info(f"✅ УСПЕХ! Пост опубликован. ID: {post_id}, Картинки: {', '.join(attachments)}")
            return True
    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        return False

def get_moscow_time():
    return datetime.now(timezone(timedelta(hours=3)))

def bot_loop():
    logger.info("🚀 Бот запущен. Читаем время из schedule.json...")
    last_posted_date = None

    while True:
        try:
            now = get_moscow_time()
            current_date = now.date()
            current_hm = f"{now.hour:02d}:{now.minute:02d}"

            publish_time = load_schedule()

            if current_hm == publish_time and last_posted_date != current_date:
                logger.info(f"⏰ Время публикации: {publish_time} МСК. Начинаем пост...")
                post_text_with_photo()
                last_posted_date = current_date
                time.sleep(60)
                continue

            if last_posted_date == current_date:
                time.sleep(30)
                continue

            time.sleep(30)

        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception as e:
            logger.exception("⚠️ Ошибка в цикле, пробуем снова через 10 сек...")
            time.sleep(10)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    logger.info("📡 Бот запущен в фоновом потоке.")

    port = int(os.getenv("PORT", 5000))
    logger.info(f"🌐 Flask-сервер слушает порт {port}")
    app.run(host="0.0.0.0", port=port)
