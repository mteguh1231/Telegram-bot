import os
import io
import logging
import telebot
import requests
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL
from supabase import create_client, Client

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Spotify API Keys
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

bot = telebot.TeleBot(BOT_TOKEN)

# Inisialisasi Klien AI (Hanya Gemini)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

user_states = {}
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
        types.KeyboardButton("🧰 Tools"),
        types.KeyboardButton("🎵 Musik"),
        types.KeyboardButton("⚙️ Reset")
    )
    bot.send_message(chat_id, text, reply_markup=markup)

# --- Helper Fungsi Spotify ---
def get_spotify_token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    try:
        res = requests.post(url, headers=headers, data=data, auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET))
        if res.status_code == 200:
            return res.json().get("access_token")
    except:
        return None
    return None

def search_spotify_track(query):
    token = get_spotify_token()
    if not token:
        return "config_error"
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "track", "limit": 1}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            items = res.json().get("tracks", {}).get("items", [])
            if items:
                track = items[0]
                return {
                    "title": track.get("name"),
                    "artist": track["artists"][0]["name"] if track["artists"] else "Unknown",
                    "album": track.get("album", {}).get("name"),
                    "link": track.get("external_urls", {}).get("spotify"),
                    "preview": track.get("preview_url")
                }
            return "not_found"
    except:
        return "api_error"
    return "not_found"

# --- Command /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = None
    welcome_text = (
        "✨ *Selamat Datang di BotPro Elite!*\n\n"
        "Asisten AI pribadi Anda (Powered by Gemini 2.5 Flash).\n\n"
        "🚀 *Kemampuan saya:*\n"
        "• 💬 *Chat:* Ngobrol pintar dan tanya jawab dengan AI.\n"
        "• 🧰 *Tools:* Download video, analisis foto, ringkas dokumen.\n"
        "• 🎵 *Musik:* Cari lagu dan dengerin preview Spotify!\n\n"
        "Gunakan tombol di bawah untuk mulai beraksi."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
    show_main_menu(message.chat.id, "Pilih kategori fitur:")

# --- Handle Navigasi Menu Utama ---
@bot.message_handler(func=lambda message: message.text in ["💬 Chat", "🧰 Tools", "🎵 Musik", "⚙️ Reset"])
def handle_menu_click(message):
    user_id = message.chat.id
    user_states[user_id] = None
    
    if message.text == "💬 Chat":
        bot.reply_to(message, "💬 *Mode Chat AI Aktif*\nSilakan kirim pertanyaanmu! Bot akan mengingat obrolan kita.")
    elif message.text == "🎵 Musik":
        user_states[user_id] = "awaiting_music"
        bot.reply_to(message, "🎵 *Pencarian Musik Spotify*\nKetik nama penyanyi dan judul lagu yang ingin kamu cari:")
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
        if user_id in user_chats:
            del user_chats[user_id]
        bot.reply_to(message, "⚙️ Sesi memori chat AI berhasil di-reset!")

# --- Callback Navigasi ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "cmd_back":
        bot.delete_message(user_id, call.message.message_id)
        show_main_menu(user_id, "Kembali ke Menu Utama.")
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        bot.edit_message_text("📥 Kirim link video (YouTube/Tiktok/IG):", user_id, call.message.message_id)
    elif call.data == "media_vision": bot.reply_to(call.message, "📸 Kirim foto untuk dianalisis oleh Gemini.")
    elif call.data == "media_doc": bot.reply_to(call.message, "📄 Kirim file dokumen (.pdf/.txt) untuk diringkas.")

# --- Logic & Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id)

    # Logika Pencarian Spotify
    if state == "awaiting_music" and message.text:
        bot.reply_to(message, "🔍 Sedang mencari lagu di Spotify...")
        result = search_spotify_track(message.text)
        
        if result == "config_error":
            bot.reply_to(message, "❌ Fitur musik belum dikonfigurasi. Pastikan API Spotify sudah diisi di Railway.")
        elif result == "api_error" or result == "not_found":
            bot.reply_to(message, "❌ Lagu tidak ditemukan. Coba ketik lebih spesifik (Contoh: Tulus - Hati Hati di Jalan).")
        else:
            info_lagu = (
                f"🎵 *Lagu Ditemukan!*\n\n"
                f"📌 *Judul:* {result['title']}\n"
                f"🎤 *Penyanyi:* {result['artist']}\n"
                f"💿 *Album:* {result['album']}\n\n"
                f"🎧 *Dengarkan Penuh:* [Buka di Spotify]({result['link']})"
            )
            bot.send_message(user_id, info_lagu, parse_mode="Markdown")
            
            if result['preview']:
                try:
                    bot.send_audio(user_id, result['preview'], caption="🔊 Potongan Preview Musik (30 Detik)")
                except:
                    pass
        user_states[user_id] = None

    # Logika Download Video
    elif state == "awaiting_url" and message.text:
        bot.reply_to(message, "⏳ Sedang memproses download... Mohon tunggu.")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
            with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(message.text, download=True)
            with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(user_id, v)
            os.remove(f"vid.{info['ext']}")
        except: bot.reply_to(message, "❌ Gagal. Link mungkin tidak didukung atau video terlalu besar.")
        user_states[user_id] = None
        
    # Logika Analisis File / Foto (Gemini Vision & Doc)
    elif message.content_type in ['document', 'photo']:
        bot.reply_to(message, "⏳ Mata Gemini sedang menganalisis file kamu...")
        try:
            if message.content_type == 'document':
                file_info = bot.get_file(message.document.file_id)
                nama = message.document.file_name
                with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
                doc = ai_client.files.upload(file=nama)
                res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[doc, "Ringkas isi dokumen ini dengan detail."])
                bot.reply_to(message, res.text)
                os.remove(nama)
            else:
                file_info = bot.get_file(message.photo[-1].file_id)
                img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
                res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini dengan detail"])
                bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)
        
    # Logika Chat AI (100% Gemini Flash)
    elif message.text and not message.text.startswith('/'):
        try:
            bot.send_chat_action(user_id, 'typing')
            if user_id not in user_chats:
                user_chats[user_id] = ai_client.chats.create(model="gemini-2.5-flash")
            
            res = user_chats[user_id].send_message(message.text)
            bot.reply_to(message, f"✨ {res.text}")
            
        except Exception as e: handle_quota_error(bot, message, e)

if __name__ == "__main__":
    bot.remove_webhook()
    print("🤖 BotPro Elite sedang berjalan...")
    bot.infinity_polling()
                
