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

user_states = {}
# TAMBAHAN: Dictionary untuk menyimpan sesi chat Gemini per user agar bot punya ingatan
user_chats = {} 

# --- Helpers ---
def handle_quota_error(bot, message, e):
    if "429" in str(e):
        bot.reply_to(message, "⚠️ *Maaf, kuota harian AI penuh.* Coba lagi besok ya!")
    else:
        bot.reply_to(message, f"Sedang ada gangguan teknis: {e}")

def show_main_menu(chat_id, text="Pilih menu di bawah:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💬 Chat"),
        types.KeyboardButton("🌍 Info"),
        types.KeyboardButton("🧰 Tools"),
        types.KeyboardButton("⚙️ Reset")
    )
    bot.send_message(chat_id, text, reply_markup=markup)

# --- Command /start Elite ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = None
    welcome_text = (
        "✨ *Selamat Datang di BotPro Elite!*\n\n"
        "Saya adalah asisten AI pribadi Anda yang siap membantu 24/7.\n\n"
        "🚀 *Kemampuan saya:*\n"
        "• 🤖 *AI Chat:* Analisis teks & jawaban cerdas (Gemini 3.1 Pro).\n"
        "• 🌍 *Info:* Cuaca, berita, dan quotes.\n"
        "• 🧰 *Tools:* Download video, analisis foto, ringkas dokumen.\n\n"
        "Gunakan tombol di bawah untuk mulai beraksi."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
    show_main_menu(message.chat.id, "Pilih kategori fitur:")

# --- Handle Navigasi Minimalis ---
@bot.message_handler(func=lambda message: message.text in ["💬 Chat", "🌍 Info", "🧰 Tools", "⚙️ Reset"])
def handle_menu_click(message):
    user_id = message.chat.id
    user_states[user_id] = None
    
    if message.text == "💬 Chat":
        bot.reply_to(message, "💬 *Mode Chat AI Aktif*\nSilakan kirim pertanyaanmu. Bot sekarang bisa mengingat obrolan sebelumnya!")
    elif message.text == "🌍 Info":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="state_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote"),
            types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_back")
        )
        bot.reply_to(message, "🌍 *Pilih Informasi:*", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "🧰 Tools":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Video", callback_data="state_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc"),
            types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_back")
        )
        bot.reply_to(message, "🧰 *Pusat Alat Media:*", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "⚙️ Reset":
        # PERBAIKAN: Sekarang tombol Reset benar-benar menghapus memori chat AI juga
        if user_id in user_chats:
            del user_chats[user_id]
        bot.reply_to(message, "⚙️ Sesi memori chat AI dan lokal berhasil di-reset!")

# --- Callback Navigasi ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "cmd_back":
        bot.delete_message(user_id, call.message.message_id)
        show_main_menu(user_id, "Kembali ke Menu Utama.")
    elif call.data == "state_cuaca":
        user_states[user_id] = "awaiting_city"
        bot.edit_message_text("🌤️ Ketik nama kota (contoh: Jakarta):", user_id, call.message.message_id)
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        bot.edit_message_text("📥 Kirim link video:", user_id, call.message.message_id)
    elif call.data == "cmd_berita": bot.reply_to(call.message, "Fitur Berita aktif.")
    elif call.data == "cmd_quote": bot.reply_to(call.message, "Fitur Quote aktif.")
    elif call.data == "media_vision": bot.reply_to(call.message, "Kirim foto untuk dianalisis.")
    elif call.data == "media_doc": bot.reply_to(call.message, "Kirim file dokumen (.pdf/.txt).")

# --- Logic & Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id)

    if state == "awaiting_url" and message.text:
        bot.reply_to(message, "⏳ Memproses...")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
            with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(message.text, download=True)
            with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(user_id, v)
            os.remove(f"vid.{info['ext']}")
        except: bot.reply_to(message, "Gagal. Link mungkin tidak didukung.")
        user_states[user_id] = None
        
    elif state == "awaiting_city" and message.text:
        try:
            res = requests.get(f"https://wttr.in/{message.text}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {res.text}")
        except: bot.reply_to(message, "Kota tidak ditemukan.")
        user_states[user_id] = None
        
    elif message.content_type in ['document', 'photo']:
        try:
            if message.content_type == 'document':
                file_info = bot.get_file(message.document.file_id)
                nama = message.document.file_name
                with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
                doc = ai_client.files.upload(file=nama)
                
                # UBAH KEDUA: Menggunakan model gemini-3.1-pro-preview untuk dokumen
                res = ai_client.chats.create(model="gemini-3.1-pro-preview").send_message([doc, "Ringkas ini."])
                bot.reply_to(message, res.text)
                os.remove(nama)
            else:
                file_info = bot.get_file(message.photo[-1].file_id)
                img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
                
                # UBAH KETIGA: Menggunakan model gemini-3.1-pro-preview untuk foto
                res = ai_client.models.generate_content(model="gemini-3.1-pro-preview", contents=[img, "Jelaskan gambar ini"])
                bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)
        
    elif message.text and not message.text.startswith('/'):
        try:
            # PERBAIKAN & UBAH PERTAMA: Cek apakah user sudah punya sesi chat berjalan
            if user_id not in user_chats:
                user_chats[user_id] = ai_client.chats.create(model="gemini-3.1-pro-preview")
            
            # Kirim pesan ke sesi chat yang sama agar ingat konteks obrolan sebelumnya
            res = user_chats[user_id].send_message(message.text)
            bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling()
    
