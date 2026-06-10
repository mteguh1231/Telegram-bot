import os
import io
import logging
import telebot
import requests
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL
from duckduckgo_search import DDGS
from supabase import create_client, Client

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# Simpan state user (apakah sedang download, nunggu kota, dll)
user_states = {}

# --- Helpers ---
def handle_quota_error(bot, message, e):
    if "429" in str(e):
        bot.reply_to(message, "⚠️ *Maaf, kuota harian bot penuh.* Coba lagi besok ya!")
    else:
        bot.reply_to(message, "Terjadi gangguan teknis.")

# --- Menu ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = None # Reset state saat mulai
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 Chat AI"),
        types.KeyboardButton("🌐 Info Dunia"),
        types.KeyboardButton("🛠️ Alat Media"),
        types.KeyboardButton("⚙️ Pengaturan")
    )
    bot.send_message(message.chat.id, "Halo! Pilih menu di bawah:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🤖 Chat AI", "🌐 Info Dunia", "🛠️ Alat Media", "⚙️ Pengaturan"])
def handle_menu_click(message):
    user_states[message.chat.id] = None
    if message.text == "🤖 Chat AI":
        bot.reply_to(message, "Silakan kirim pesan atau pertanyaanmu.")
    elif message.text == "🌐 Info Dunia":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="state_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote")
        )
        bot.reply_to(message, "Pilih info yang diinginkan:", reply_markup=markup)
    elif message.text == "🛠️ Alat Media":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Video", callback_data="state_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc")
        )
        bot.reply_to(message, "🛠️ Pusat Alat Media:", reply_markup=markup)
    elif message.text == "⚙️ Pengaturan":
        bot.reply_to(message, "Memori sesi telah di-reset.")

# --- Callback (Mode Selector) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "state_cuaca":
        user_states[user_id] = "awaiting_city"
        bot.reply_to(call.message, "🌤️ Ketik nama kota (contoh: Jakarta):")
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        bot.reply_to(call.message, "📥 Kirim link video yang ingin di-download:")
    elif call.data == "cmd_berita":
        # Logika berita tetap langsung
        bot.reply_to(call.message, "Mengambil berita... (fitur ini masih instant)")
    elif call.data == "cmd_quote":
        # Logika quote tetap langsung
        bot.reply_to(call.message, "Fitur Quote (fitur ini masih instant)")
    elif call.data == "media_vision":
        bot.reply_to(call.message, "Kirim foto saja, saya akan jelaskan.")
    elif call.data == "media_doc":
        bot.reply_to(call.message, "Kirim file dokumen, saya akan ringkas.")

# --- Main Handler (Logic + State) ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id)

    # 1. Mode Download
    if state == "awaiting_url" and message.text:
        bot.reply_to(message, "⏳ Sedang memproses download, mohon tunggu...")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
            with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(message.text, download=True)
            with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(message.chat.id, v)
            os.remove(f"vid.{info['ext']}")
        except: bot.reply_to(message, "Gagal. Pastikan link valid.")
        user_states[user_id] = None
        return

    # 2. Mode Cuaca
    elif state == "awaiting_city" and message.text:
        try:
            res = requests.get(f"https://wttr.in/{message.text}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {res.text}")
        except: bot.reply_to(message, "Gagal cari kota.")
        user_states[user_id] = None
        return

    # 3. Handling File (Foto/Dokumen)
    elif message.content_type == 'document':
        try:
            file_info = bot.get_file(message.document.file_id)
            nama = message.document.file_name
            with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
            doc = ai_client.files.upload(file=nama)
            res = ai_client.chats.create(model="gemini-2.5-flash").send_message([doc, "Ringkas ini."])
            bot.reply_to(message, res.text)
            os.remove(nama)
        except Exception as e: handle_quota_error(bot, message, e)
    
    elif message.content_type == 'photo':
        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
            res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
            bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)

    # 4. Default Chat (AI)
    elif message.text and not message.text.startswith('/'):
        try:
            res = ai_client.chats.create(model="gemini-2.5-flash").send_message(message.text)
            bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)

# --- Run ---
if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot Mode-Free Siap!")
    bot.infinity_polling()
    
