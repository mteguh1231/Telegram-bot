import requests
import sqlite3
import time
import hashlib
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("8382786338:AAG5PIqTogDL0UDW0RJnNEXUAt1PtHhRo38")
OPENROUTER_API_KEY = "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"
WEATHER_API_KEY = "9f6e89a97a0dab91ac1fbd21c7e0b476"
NEWS_API_KEY = "3fc49704bdae4569b56c62dd1216dad7"
# ================== DATABASE ==================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    mode TEXT DEFAULT 'normal'
)
""")
conn.commit()

def set_mode(user_id, mode):
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, mode))
    conn.commit()

def get_mode(user_id):
    cursor.execute("SELECT mode FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "normal"

# ================== MEMORY ==================
memory = {}
cache = {}
last_request = {}
MAX_MEMORY = 10

def rate_limit(user_id):
    now = time.time()
    if user_id in last_request:
        if now - last_request[user_id] < 3:
            return False
    last_request[user_id] = now
    return True

def make_key(text):
    return hashlib.md5(text.encode()).hexdigest()

# ================== AI ==================
def ai_router(text, mode, user_id):

    if user_id not in memory:
        memory[user_id] = []

    memory[user_id].append({"role": "user", "content": text})
    memory[user_id] = memory[user_id][-MAX_MEMORY:]

    system_prompt = {
        "normal": "Jawab singkat dan jelas.",
        "pintar": "Jawab detail tapi ringkas.",
        "lucu": "Jawab dengan humor ringan.",
        "guru": "Jelaskan seperti guru.",
        "galak": "Jawab tegas dan singkat."
    }

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt.get(mode, "normal")},
            *memory[user_id]
        ]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=12)
        result = r.json()["choices"][0]["message"]["content"]

        memory[user_id].append({"role": "assistant", "content": result})
        return result

    except:
        return None

def ai(user_id, text):
    mode = get_mode(user_id)
    key = make_key(text)

    if key in cache:
        return cache[key]

    result = ai_router(text, mode, user_id)

    if result:
        cache[key] = result
        return result

    return "⚠️ AI sedang sibuk. Coba lagi nanti."

# ================== CUACA ==================
def cuaca(kota):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={kota}&appid={WEATHER_API_KEY}&units=metric&lang=id"
    r = requests.get(url).json()

    try:
        return f"🌤 {kota}: {r['weather'][0]['description']}, {r['main']['temp']}°C"
    except:
        return "Kota tidak ditemukan"

# ================== SHOLAT ==================
def sholat(kota):
    url = f"https://api.aladhan.com/v1/timingsByCity?city={kota}&country=Indonesia"
    r = requests.get(url).json()

    try:
        t = r["data"]["timings"]
        return f"""🕌 Sholat {kota}

Subuh: {t['Fajr']}
Dzuhur: {t['Dhuhr']}
Ashar: {t['Asr']}
Maghrib: {t['Maghrib']}
Isya: {t['Isha']}"""
    except:
        return "Data tidak ditemukan"

# ================== BERITA ==================
def berita():
    url = f"https://newsapi.org/v2/top-headlines?country=id&apiKey={NEWS_API_KEY}"
    r = requests.get(url).json()

    data = []

    try:
        for a in r["articles"][:5]:
            data.append({
                "title": a["title"],
                "desc": a["description"] or "-",
                "img": a["urlToImage"]
            })
        return data
    except:
        return []

# ================== MENU ==================
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 AI", callback_data="ai")],
        [InlineKeyboardButton("🌤 Cuaca", callback_data="cuaca")],
        [InlineKeyboardButton("🕌 Sholat", callback_data="sholat")],
        [InlineKeyboardButton("📰 Berita", callback_data="berita")],
        [InlineKeyboardButton("🎛 Mode", callback_data="mode")]
    ])

# ================== HANDLER ==================
def start(update: Update, context: CallbackContext):
    update.message.reply_text("🚀 BOT AKTIF", reply_markup=menu())

def button(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()

    if q.data == "berita":
        news = berita()

        if not news:
            q.message.edit_text("Berita tidak tersedia")
            return

        for n in news:
            caption = f"📰 {n['title']}\n\n{n['desc']}"

            if n["img"]:
                q.message.reply_photo(n["img"], caption=caption)
            else:
                q.message.reply_text(caption)

    elif q.data == "cuaca":
        q.message.edit_text("Ketik: cuaca jakarta")

    elif q.data == "sholat":
        q.message.edit_text("Ketik: sholat jakarta")

    elif q.data == "mode":
        keyboard = [
            [InlineKeyboardButton("Normal", callback_data="mode_normal")],
            [InlineKeyboardButton("Pintar", callback_data="mode_pintar")],
            [InlineKeyboardButton("Lucu", callback_data="mode_lucu")],
            [InlineKeyboardButton("Guru", callback_data="mode_guru")],
            [InlineKeyboardButton("Galak", callback_data="mode_galak")]
        ]
        q.message.reply_text("Pilih mode:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data.startswith("mode_"):
        mode = q.data.replace("mode_", "")
        set_mode(q.from_user.id, mode)
        q.message.edit_text(f"Mode: {mode}")

def handle(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    if not rate_limit(user_id):
        update.message.reply_text("⏳ terlalu cepat")
        return

    if text.startswith("cuaca"):
        kota = text.replace("cuaca", "").strip()
        update.message.reply_text(cuaca(kota))

    elif text.startswith("sholat"):
        kota = text.replace("sholat", "").strip()
        update.message.reply_text(sholat(kota))

    else:
        update.message.reply_text(ai(user_id, text))

# ================== RUN ==================
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))

    print("🔥 BOT RUNNING")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
