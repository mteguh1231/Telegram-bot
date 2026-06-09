import os
import time
import json
import hashlib
import logging
import sqlite3
import aiohttp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

MAX_MEMORY = 10
RATE_LIMIT_SECONDS = 3

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =========================
# DATABASE
# =========================

conn = sqlite3.connect(
    "bot.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    mode TEXT DEFAULT 'normal'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id INTEGER,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# =========================
# USER MODE
# =========================

def set_mode(user_id, mode):
    cursor.execute(
        """
        INSERT INTO users(user_id, mode)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET mode=excluded.mode
        """,
        (user_id, mode)
    )
    conn.commit()

def get_mode(user_id):
    cursor.execute(
        "SELECT mode FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return "normal"

# =========================
# MEMORY
# =========================

def save_memory(user_id, role, content):

    cursor.execute(
        """
        INSERT INTO memory(user_id, role, content)
        VALUES(?, ?, ?)
        """,
        (user_id, role, content)
    )

    conn.commit()

    cursor.execute(
        """
        SELECT rowid
        FROM memory
        WHERE user_id=?
        ORDER BY rowid DESC
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    if len(rows) > (MAX_MEMORY * 2):
        for row in rows[(MAX_MEMORY * 2):]:
            cursor.execute(
                "DELETE FROM memory WHERE rowid=?",
                (row[0],)
            )

    conn.commit()

def get_memory(user_id):

    cursor.execute(
        """
        SELECT role, content
        FROM memory
        WHERE user_id=?
        ORDER BY rowid DESC
        LIMIT ?
        """,
        (user_id, MAX_MEMORY)
    )

    rows = cursor.fetchall()
    rows.reverse()

    messages = []

    for role, content in rows:
        messages.append({
            "role": role,
            "content": content
        })

    return messages

# =========================
# CACHE
# =========================

cache = {}

def make_key(user_id, text):
    return hashlib.md5(
        f"{user_id}:{text}".encode()
    ).hexdigest()

# =========================
# RATE LIMIT
# =========================

last_request = {}

def rate_limit(user_id):

    now = time.time()

    if user_id in last_request:
        diff = now - last_request[user_id]

        if diff < RATE_LIMIT_SECONDS:
            return False

    last_request[user_id] = now
    return True

# =========================
# OPENROUTER AI
# =========================

async def ai_router(user_id, text):

    mode = get_mode(user_id)

    prompts = {
        "normal": "Jawab singkat dan jelas.",
        "pintar": "Jawab detail namun tetap ringkas.",
        "lucu": "Jawab dengan humor ringan.",
        "guru": "Jelaskan seperti guru yang mengajar.",
        "galak": "Jawab tegas dan singkat."
    }

    memory = get_memory(user_id)

    messages = [
        {
            "role": "system",
            "content": prompts.get(mode, prompts["normal"])
        }
    ]

    messages.extend(memory)

    messages.append({
        "role": "user",
        "content": text
    })

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "messages": messages
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            ) as response:

                if response.status != 200:
                    text_error = await response.text()

                    logging.error(
                        f"OpenRouter Error: {text_error}"
                    )

                    return None

                data = await response.json()

                answer = (
                    data["choices"][0]
                    ["message"]["content"]
                )

                save_memory(
                    user_id,
                    "user",
                    text
                )

                save_memory(
                    user_id,
                    "assistant",
                    answer
                )

                return answer

    except Exception as e:
        logging.exception(e)
        return None

async def ai(user_id, text):

    key = make_key(user_id, text)

    if key in cache:
        return cache[key]

    result = await ai_router(
        user_id,
        text
    )

    if result:
        cache[key] = result
        return result

    return "⚠️ AI sedang sibuk. Coba lagi beberapa saat lagi."

# =========================
# WEATHER
# =========================

async def cuaca(kota):

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={kota}"
        f"&appid={WEATHER_API_KEY}"
        "&units=metric"
        "&lang=id"
    )

    try:

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:

                data = await response.json()

                if data.get("cod") != 200:
                    return f"❌ {data.get('message', 'Kota tidak ditemukan')}"

                nama = data["name"]
                kondisi = data["weather"][0]["description"]
                suhu = data["main"]["temp"]
                kelembapan = data["main"]["humidity"]
                angin = data["wind"]["speed"]

                return (
                    f"🌤 Cuaca {nama}\n\n"
                    f"🌡 Suhu: {suhu}°C\n"
                    f"☁️ Kondisi: {kondisi}\n"
                    f"💧 Kelembapan: {kelembapan}%\n"
                    f"🌬 Angin: {angin} m/s"
                )

    except Exception as e:
        print("CUACA ERROR =", e)
        return f"❌ Error cuaca: {e}"

# =========================
# SHOLAT
# =========================

async def sholat(kota):

    url = (
        "https://api.aladhan.com/v1/timingsByCity"
        f"?city={kota}"
        "&country=Indonesia"
    )

    try:

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:

                data = await response.json()

                t = data["data"]["timings"]

                return (
                    f"🕌 Jadwal Sholat {kota.title()}\n\n"
                    f"Subuh : {t['Fajr']}\n"
                    f"Dzuhur: {t['Dhuhr']}\n"
                    f"Ashar : {t['Asr']}\n"
                    f"Maghrib: {t['Maghrib']}\n"
                    f"Isya  : {t['Isha']}"
                )

    except Exception:
        return "Data tidak ditemukan."

# =========================
# NEWS
# =========================

async def berita():

    url = (
        "https://newsapi.org/v2/top-headlines"
        f"?country=id&apiKey={NEWS_API_KEY}"
    )

    try:

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:

                data = await response.json()

                print("NEWS STATUS =", response.status)
                print("NEWS DATA =", data)

                result = []

                for item in data["articles"][:5]:

                    result.append({
                        "title": item["title"],
                        "desc": item.get("description") or "-",
                        "img": item.get("urlToImage")
                    })

                return result

    except Exception as e:
        print("NEWS ERROR =", e)
        return []

# =========================
# MENU
# =========================

def menu():

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 AI", callback_data="ai")],
        [InlineKeyboardButton("🌤 Cuaca", callback_data="cuaca")],
        [InlineKeyboardButton("🕌 Sholat", callback_data="sholat")],
        [InlineKeyboardButton("📰 Berita", callback_data="berita")],
        [InlineKeyboardButton("🎛 Mode", callback_data="mode")]
    ])

# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🚀 Bot aktif dan siap digunakan",
        reply_markup=menu()
    )

# =========================
# MODE COMMAND
# =========================

async def mode_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [InlineKeyboardButton(
            "Normal",
            callback_data="mode_normal"
        )],
        [InlineKeyboardButton(
            "Pintar",
            callback_data="mode_pintar"
        )],
        [InlineKeyboardButton(
            "Lucu",
            callback_data="mode_lucu"
        )],
        [InlineKeyboardButton(
            "Guru",
            callback_data="mode_guru"
        )],
        [InlineKeyboardButton(
            "Galak",
            callback_data="mode_galak"
        )]
    ]

    await update.message.reply_text(
        "Pilih mode AI:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

# =========================
# BUTTON
# =========================

async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    q = update.callback_query

    await q.answer()

    if q.data == "ai":

        await q.message.reply_text(
            "🤖 Kirim pertanyaan apa saja."
        )

    elif q.data == "cuaca":

        await q.message.reply_text(
            "Contoh:\ncuaca jakarta"
        )

    elif q.data == "sholat":

        await q.message.reply_text(
            "Contoh:\nsholat bandung"
        )

    elif q.data == "mode":

        keyboard = [
            [InlineKeyboardButton(
                "Normal",
                callback_data="mode_normal"
            )],
            [InlineKeyboardButton(
                "Pintar",
                callback_data="mode_pintar"
            )],
            [InlineKeyboardButton(
                "Lucu",
                callback_data="mode_lucu"
            )],
            [InlineKeyboardButton(
                "Guru",
                callback_data="mode_guru"
            )],
            [InlineKeyboardButton(
                "Galak",
                callback_data="mode_galak"
            )]
        ]

        await q.message.reply_text(
            "Pilih mode:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

    elif q.data.startswith("mode_"):

        mode = q.data.replace(
            "mode_",
            ""
        )

        set_mode(
            q.from_user.id,
            mode
        )

        await q.message.reply_text(
            f"✅ Mode diubah ke: {mode}"
        )

    elif q.data == "berita":

        news = await berita()

        if not news:

            await q.message.reply_text(
                "Berita tidak tersedia."
            )

            return

        for item in news:

            caption = (
                f"📰 {item['title']}\n\n"
                f"{item['desc']}"
            )

            if item["img"]:
                await q.message.reply_photo(
                    item["img"],
                    caption=caption
                )
            else:
                await q.message.reply_text(
                    caption
                )

# =========================
# MESSAGE HANDLER
# =========================

async def handle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    user_id = update.effective_user.id

    if not rate_limit(user_id):

        await update.message.reply_text(
            "⏳ Tunggu beberapa detik lalu coba lagi."
        )

        return

    if text.lower().startswith("cuaca"):

        kota = (
            text.replace(
                "cuaca",
                ""
            )
            .strip()
        )

        if not kota:
            await update.message.reply_text(
                "Contoh: cuaca jakarta"
            )
            return

        await update.message.reply_text(
            await cuaca(kota)
        )

        return

    if text.lower().startswith("sholat"):

        kota = (
            text.replace(
                "sholat",
                ""
            )
            .strip()
        )

        if not kota:
            await update.message.reply_text(
                "Contoh: sholat bandung"
            )
            return

        await update.message.reply_text(
            await sholat(kota)
        )

        return

    response = await ai(
        user_id,
        text
    )

    await update.message.reply_text(
        response
    )

# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN belum diisi"
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "mode",
            mode_command
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle
        )
    )

    logging.info(
        "BOT RUNNING..."
    )

    app.run_polling(
        drop_pending_updates=True
    )

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
