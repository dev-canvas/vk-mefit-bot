import os
import time
import json
import re
import random
import logging
import tempfile
import threading
import requests
from datetime import datetime, timezone, timedelta
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Логи ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Переменные окружения ──────────────────────────────
VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID_RAW = os.getenv("GROUP_ID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")

if not VK_TOKEN or not GROUP_ID_RAW:
    logger.error("❌ Не заданы VK_TOKEN или GROUP_ID!")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID_RAW)
except ValueError:
    logger.error("❌ GROUP_ID должен быть числом")
    exit(1)

if not AUTH_TOKEN:
    logger.warning("⚠️ AUTH_TOKEN не задан! Авторизация отключена — кто угодно может менять настройки.")

logger.info(f"✅ Переменные загружены. ID группы: {GROUP_ID}")

# ── Конфиг ────────────────────────────────────────────
SCHEDULE_FILE = "schedule.json"
MAX_PHOTOS = 10_000
POST_TEXT_MAX = 4000
MAX_PHOTOS_PER_POST = 10  # лимит ВКонтакте

DEFAULT_POST_TEXT = (
    "Листай  👉\n"
    "Выбери 1 или 2 или 3  👉\n"
    "Твоя опора на сегодня ❤️"
)

DEFAULT_CONFIG = {
    "publish_time": "06:00",
    "photo_first_id": "photo-239232916_456239539",
    "photo_last_id": "photo-239232916_456239620",
    "post_text": DEFAULT_POST_TEXT,
    "photo_mode": "random",       # "random" | "sequential"
    "photos_per_post": 4,          # сколько фото на пост (для sequential)
    "seq_cursor": 0,               # позиция для sequential-режима
}

PHOTO_ID_RE = re.compile(r"^photo(-?\d+)_(\d+)$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_config_lock = threading.Lock()


def load_config() -> dict:
    """Читает конфиг с диска, дополняя значениями по умолчанию."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        with _config_lock, open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Конфиг повреждён ({e}), использую значения по умолчанию")
    return cfg


def save_config(cfg: dict) -> None:
    """Атомарная запись: tmp-файл + os.replace."""
    with _config_lock:
        fd, tmp_path = tempfile.mkstemp(
            prefix=SCHEDULE_FILE + ".", suffix=".tmp", dir="."
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, SCHEDULE_FILE)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise


# ── Генерация списка фото ─────────────────────────────
def generate_photos(first_id: str, last_id: str) -> list:
    """
    Генерирует список фото из первого и последнего ID.
    Формат: photo<owner>_<number>, например photo-239232916_456239539
    """
    m_first = PHOTO_ID_RE.match(first_id or "")
    m_last = PHOTO_ID_RE.match(last_id or "")

    if not m_first or not m_last:
        raise ValueError("ID фото должны быть в формате photo<owner>_<id>")

    owner_first, num_first = m_first.group(1), int(m_first.group(2))
    owner_last, num_last = m_last.group(1), int(m_last.group(2))

    if owner_first != owner_last:
        raise ValueError("У первого и последнего фото должен совпадать owner")

    if num_first > num_last:
        raise ValueError("Первый ID не может быть больше последнего")

    total = num_last - num_first + 1
    if total > MAX_PHOTOS:
        raise ValueError(
            f"Слишком большой диапазон: {total} фото (максимум {MAX_PHOTOS})"
        )

    return [f"photo{owner_first}_{i}" for i in range(num_first, num_last + 1)]


# ── Динамическое состояние ────────────────────────────
class PhotoState:
    """Хранит список фото, очередь последних использованных и курсор для sequential-режима."""

    def __init__(self):
        self._lock = threading.Lock()
        self._photos: list = []
        self._last_used: deque = deque(maxlen=10)
        self._seq_cursor: int = 0

    def set_photos(self, photos: list) -> int:
        """Устанавливает список фото, сбрасывает историю и курсор."""
        with self._lock:
            self._photos = list(photos)
            self._last_used.clear()
            self._seq_cursor = 0
        return len(self._photos)

    def refresh(self, first_id: str, last_id: str) -> int:
        """Пересобирает список фото. Возвращает новое количество."""
        photos = generate_photos(first_id, last_id)
        return self.set_photos(photos)

    def restore_cursor(self, cfg: dict) -> None:
        """Восстанавливает курсор из конфига (после перезапуска)."""
        with self._lock:
            n = len(self._photos)
            saved = cfg.get("seq_cursor", 0)
            if n > 0:
                self._seq_cursor = saved % n
            else:
                self._seq_cursor = 0

    def get_cursor(self) -> int:
        with self._lock:
            return self._seq_cursor

    def get_unique(self, count: int = 3) -> list:
        """Случайный режим: выбирает уникальные фото."""
        with self._lock:
            photos = self._photos
            last_used = self._last_used

            if not photos:
                return []

            count = min(count, len(photos))

            if len(photos) <= last_used.maxlen:
                chosen = random.sample(photos, count)
            else:
                available = [p for p in photos if p not in last_used]
                if len(available) >= count:
                    chosen = random.sample(available, count)
                elif available:
                    logger.warning("⚠️ Недостаточно уникальных картинок, берём сколько есть.")
                    chosen = random.sample(available, len(available))
                else:
                    chosen = random.sample(photos, count)

            for p in chosen:
                last_used.append(p)
            return chosen

    def get_next_batch(self, count: int) -> list:
        """
        Sequential-режим: берёт следующие count фото по порядку.
        Если дошли до конца — зацикливается с начала.
        """
        with self._lock:
            photos = self._photos
            if not photos:
                return []

            n = len(photos)
            count = min(count, n)

            cursor = self._seq_cursor
            batch = []
            for i in range(count):
                batch.append(photos[(cursor + i) % n])

            self._seq_cursor = (cursor + count) % n
            return batch

    def get_for_post(self, count: int, mode: str) -> list:
        """Главный метод: выбирает фото в зависимости от режима."""
        if mode == "sequential":
            return self.get_next_batch(count)
        return self.get_unique(count)

    def size(self) -> int:
        with self._lock:
            return len(self._photos)

    def preview(self, limit: int = 3) -> dict:
        with self._lock:
            photos = list(self._photos)
        if not photos:
            return {"count": 0, "first": None, "last": None, "sample": []}
        return {
            "count": len(photos),
            "first": photos[0],
            "last": photos[-1],
            "sample": photos[:limit],
        }


photo_state = PhotoState()

# Применяем конфиг с диска
_initial_cfg = load_config()
try:
    photo_state.refresh(_initial_cfg["photo_first_id"], _initial_cfg["photo_last_id"])
    photo_state.restore_cursor(_initial_cfg)
    logger.info(
        f"🖼️ Загружено {photo_state.size()} фото "
        f"({_initial_cfg['photo_first_id']} ... {_initial_cfg['photo_last_id']}), "
        f"режим: {_initial_cfg['photo_mode']}, курсор: {photo_state.get_cursor()}"
    )
except ValueError as e:
    logger.error(f"❌ Ошибка генерации списка фото из конфига: {e}")
    exit(1)


# ── Flask ─────────────────────────────────────────────
app = Flask(__name__)

CORS(app, resources={
    r"/api/.*": {
        "origins": [
            "https://dev-canvas.github.io",
            r"http://localhost:\d+",
            r"http://127\.0\.0\.1:\d+",
        ],
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "X-Auth-Token"],
        "methods": ["GET", "POST", "OPTIONS"],
        "expose_headers": ["Content-Type"],
        "max_age": 86400,
    }
})


@app.before_request
def _handle_preflight():
    """Универсальный ответ на preflight (OPTIONS) для всех /api/* маршрутов."""
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        return ("", 200)


def check_auth() -> bool:
    if not AUTH_TOKEN:
        return True
    return request.headers.get("X-Auth-Token", "") == AUTH_TOKEN


def _config_response(cfg: dict = None) -> dict:
    cfg = cfg or load_config()
    preview = photo_state.preview()
    return {
        "publish_time": cfg["publish_time"],
        "photo_first_id": cfg["photo_first_id"],
        "photo_last_id": cfg["photo_last_id"],
        "post_text": cfg["post_text"],
        "post_text_max": POST_TEXT_MAX,
        "photos_count": preview["count"],
        "photos_first": preview["first"],
        "photos_last": preview["last"],
        "photos_sample": preview["sample"],
        "photo_mode": cfg.get("photo_mode", "random"),
        "photos_per_post": cfg.get("photos_per_post", 4),
    }


# ── API: весь конфиг ──────────────────────────────────
@app.route("/api/schedule", methods=["GET", "OPTIONS"])
def api_get_schedule():
    if request.method == "OPTIONS":
        return ("", 200)
    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401
    return jsonify(_config_response())


# ── API: время публикации ─────────────────────────────
@app.route("/api/schedule/publish_time", methods=["GET", "OPTIONS"])
def api_get_publish_time():
    if request.method == "OPTIONS":
        return ("", 200)
    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401
    return jsonify({"publish_time": load_config()["publish_time"]})


@app.route("/api/schedule/publish_time", methods=["POST", "OPTIONS"])
def api_set_publish_time():
    if request.method == "OPTIONS":
        return ("", 200)

    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401

    data = request.get_json(silent=True) or {}
    time_str = data.get("time") or request.form.get("time")

    if not time_str:
        return jsonify({"error": "Параметр 'time' обязателен"}), 400

    if not TIME_RE.fullmatch(time_str):
        return jsonify({"error": "Неверный формат. Используйте HH:MM (24ч)"}), 400

    cfg = load_config()
    cfg["publish_time"] = time_str
    save_config(cfg)
    logger.info(f"⏰ Время публикации обновлено: {time_str}")

    return jsonify(_config_response(cfg))


# ── API: текст поста ──────────────────────────────────
@app.route("/api/schedule/post_text", methods=["GET", "OPTIONS"])
def api_get_post_text():
    if request.method == "OPTIONS":
        return ("", 200)
    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401
    return jsonify({"post_text": load_config()["post_text"]})


@app.route("/api/schedule/post_text", methods=["POST", "OPTIONS"])
def api_set_post_text():
    if request.method == "OPTIONS":
        return ("", 200)

    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401

    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if text is None:
        text = request.form.get("text")

    if text is None:
        return jsonify({"error": "Параметр 'text' обязателен"}), 400

    if not isinstance(text, str):
        return jsonify({"error": "Параметр 'text' должен быть строкой"}), 400

    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip()

    if len(text) > POST_TEXT_MAX:
        return jsonify({
            "error": f"Текст слишком длинный: {len(text)} символов (максимум {POST_TEXT_MAX})"
        }), 400

    cfg = load_config()
    cfg["post_text"] = text
    save_config(cfg)
    logger.info(f"📝 Текст поста обновлён ({len(text)} символов)")

    return jsonify(_config_response(cfg))


# ── API: диапазон фото ────────────────────────────────
@app.route("/api/schedule/photos", methods=["POST", "OPTIONS"])
def api_set_photos():
    if request.method == "OPTIONS":
        return ("", 200)

    if not check_auth():
        return jsonify({"error": "Нет авторизации"}), 401

    data = request.get_json(silent=True) or {}
    first_id = (data.get("first_id") or request.form.get("first_id") or "").strip()
    last_id = (data.get("last_id") or request.form.get("last_id") or "").strip()

    if not first_id or not last_id:
        return jsonify({"error": "Параметры 'first_id' и 'last_id' обязательны"}), 400

    # ── Режим выбора фото ──
    photo_mode = (data.get("photo_mode") or request.form.get("photo_mode") or "random").strip()
    if photo_mode not in ("random", "sequential"):
        return jsonify({"error": "photo_mode должен быть 'random' или 'sequential'"}), 400

    photos_per_post = 3
    if photo_mode == "sequential":
        raw_n = data.get("photos_per_post") or request.form.get("photos_per_post")
        try:
            photos_per_post = int(raw_n) if raw_n is not None else 4
        except (ValueError, TypeError):
            return jsonify({"error": "photos_per_post должен быть числом"}), 400
        if photos_per_post < 1:
            return jsonify({"error": "photos_per_post должен быть минимум 1"}), 400
        if photos_per_post > MAX_PHOTOS_PER_POST:
            return jsonify({"error": f"photos_per_post не может превышать {MAX_PHOTOS_PER_POST} (лимит ВК)"}), 400

    try:
        photos = generate_photos(first_id, last_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    cfg = load_config()
    cfg["photo_first_id"] = first_id
    cfg["photo_last_id"] = last_id
    cfg["photo_mode"] = photo_mode
    cfg["photos_per_post"] = photos_per_post
    cfg["seq_cursor"] = 0  # новый диапазон — курсор в начало
    save_config(cfg)

    count = photo_state.set_photos(photos)  # сбрасывает и курсор, и историю

    logger.info(
        f"🖼️ Диапазон фото обновлён: {first_id} ... {last_id} ({count} шт.), "
        f"режим: {photo_mode}, фото/пост: {photos_per_post}"
    )
    return jsonify(_config_response(cfg))


# ── Публикация ────────────────────────────────────────
def post_text_with_photo() -> bool:
    cfg = load_config()
    photo_mode = cfg.get("photo_mode", "random")

    # В random-режиме всегда 3 фото, в sequential — из конфига
    if photo_mode == "sequential":
        photos_per_post = cfg.get("photos_per_post", 4)
    else:
        photos_per_post = 3

    attachments = photo_state.get_for_post(photos_per_post, photo_mode)
    if not attachments:
        logger.error("❌ Нет доступных фото для публикации!")
        return False

    message = cfg.get("post_text", DEFAULT_POST_TEXT)

    try:
        r = requests.post(
            "https://api.vk.com/method/wall.post",
            params={
                "owner_id": GROUP_ID,
                "message": message,
                "attachment": ",".join(attachments),
                "access_token": VK_TOKEN,
                "v": "5.131",
            },
            timeout=10,
        )
        result = r.json()

        if "error" in result:
            logger.error(f"❌ Ошибка публикации: {result['error']}")
            return False

        post_id = result["response"]["post_id"]

        # В sequential-режиме сохраняем курсор после успешного поста
        if photo_mode == "sequential":
            cfg = load_config()
            cfg["seq_cursor"] = photo_state.get_cursor()
            save_config(cfg)
            logger.info(
                f"✅ УСПЕХ! Пост {post_id} | режим: sequential | "
                f"фото: {', '.join(attachments)} | курсор: {cfg['seq_cursor']}"
            )
        else:
            logger.info(
                f"✅ УСПЕХ! Пост {post_id} | режим: random | "
                f"фото: {', '.join(attachments)}"
            )
        return True

    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        return False


def get_moscow_time() -> datetime:
    return datetime.now(timezone(timedelta(hours=3)))


# ── Основной цикл бота ────────────────────────────────
def bot_loop():
    logger.info("🚀 Бот запущен. Читаем конфиг из schedule.json...")
    last_posted_date = None

    while True:
        try:
            now = get_moscow_time()
            current_date = now.date()
            current_hm = now.strftime("%H:%M")

            publish_time = load_config()["publish_time"]

            if current_hm == publish_time and last_posted_date != current_date:
                logger.info(f"⏰ Время публикации: {publish_time} МСК. Начинаем пост...")
                post_text_with_photo()
                last_posted_date = current_date
                time.sleep(60)
            else:
                time.sleep(30)

        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception:
            logger.exception("⚠️ Ошибка в цикле, пробуем снова через 10 сек...")
            time.sleep(10)


# ── Запуск ────────────────────────────────────────────
if __name__ == "__main__":
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    logger.info("📡 Бот запущен в фоновом потоке.")

    port = int(os.getenv("PORT", 5000))
    logger.info(f"🌐 Flask-сервер слушает порт {port}")
    app.run(host="0.0.0.0", port=port)
