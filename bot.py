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

# --- Helpers Umum ---
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

# --- Helper Fungsi Spotify (MODE DETEKTIF - TANPA TYPO) ---
def search_spotify_track(query):
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return "DEBUG_ERROR: Client ID atau Secret belum terdeteksi di Railway. Pastikan namanya benar."
        
    kata1 = "accounts"
    kata2 = "spo" + "tify"
    kata3 = "com"
    url_token = f"https://{kata1}.{kata2}.{kata3}/api/token"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    
    try:
        res_token = requests.post(url_token, headers=headers, data=data, auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET), timeout=10)
        if res_token.status_code != 200:
            return f"DEBUG_TOKEN_ERROR: Kunci API salah! (Kode: {res_token.status_code}) | Info: {res_token.text}"
        token = res_token.json().get("access_token")
    except Exception as e:
        return f"DEBUG_TOKEN_CRASH: Jaringan error saat mengambil kunci - {str(e)}"
        
    kata4 = "api"
    url_search = f"https://{kata4}.{kata2}.{kata3}/v1/search"
    headers_search = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "track", "limit": 1}
    
    try:
        res_search = requests.get(url_search, headers=headers_search, params=params, timeout=10)
        if res_search.status_code != 200:
            return f"DEBUG_SEARCH_ERROR: Gagal mencari! (Kode: {res_search.status_code}) | Info: {res_search.text}"
        
        items = res_search.json().get("tracks", {}).get("items", [])
        if not items:
            return "DEBUG_NOT_FOUND: Koneksi Spotify sukses 100%, tapi lagu benar-benar tidak ada di database."
            
        track = items[0]
        return {
            "title": track.get("name"),
            "artist": track["artists"][0]["name"] if track["artists"] else "Unknown",
            "album": track.get("album", {}).get("name"),
            "link": track.get("external_urls", {}).get("spotify"),
            "preview": track.get("preview_url")
        }
    except Exception as e:
        return f"DEBUG_SEARCH_CRASH: Terjadi masalah internal Python - {str(e)}"

# --- Command /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = "chat"
    welcome_text = (
        "✨ *Selamat Datang di BotPro Elite!*\n\n"
        "Asisten AI pribadi Anda (Powered by Gemini 2.5 Flash).\n\n"
        "🚀 *Kemampuan saya:*\n"
        "• 💬 *Chat:* Ngobrol pintar dan tanya jawab dengan AI.\n"
        "• 🧰 *Tools:* Download Media (YT, IG, TikTok), analisis foto, ringkas dokumen.\n"
        "• 🎵 *Musik:* Cari lagu dan dengerin preview Spotify!\n\n"
        "Gunakan tombol di bawah untuk mulai beraksi."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
    show_main_menu(message.chat.id, "Pilih kategori fitur:")

# --- Handle Navigasi Menu Utama ---
@bot.message_handler(func=lambda message: message.text in ["💬 Chat", "🧰 Tools", "🎵 Musik", "⚙️ Reset"])
def handle_menu_click(message):
    user_id = message.chat.id
    
    if message.text == "💬 Chat":
        user_states[user_id] = "chat"
        bot.reply_to(message, "💬 *Mode Chat AI Aktif*\nSilakan kirim pertanyaanmu! Bot akan merespons sebagai AI.")
    elif message.text == "🎵 Musik":
        user_states[user_id] = "awaiting_music"
        bot.reply_to(message, "🎵 *Mode Pencarian Musik Aktif*\nSilakan ketik nama penyanyi & judul lagu.\n_(Klik tombol 💬 Chat jika ingin keluar dari mode ini)_", parse_mode="Markdown")
    elif message.text == "🧰 Tools":
        user_states[user_id] = "tools"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Media (YT/IG/TikTok)", callback_data="state_download"),
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
        user_states[user_id] = "chat"
        show_main_menu(user_id, "Kembali ke Menu Utama. Mode AI aktif.")
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        bot.edit_message_text("📥 *Mode Download Aktif*\nKirim link media yang ingin diunduh.\n_(Klik tombol 💬 Chat jika ingin keluar dari mode ini)_", user_id, call.message.message_id, parse_mode="Markdown")
    elif call.data == "media_vision": 
        user_states[user_id] = "chat"
        bot.reply_to(call.message, "📸 Kirim foto untuk dianalisis oleh Gemini.")
    elif call.data == "media_doc": 
        user_states[user_id] = "chat"
        bot.reply_to(call.message, "📄 Kirim file dokumen (.pdf/.txt) untuk diringkas.")

# --- Logic & Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id, "chat")

    # --- 1. Logika Pencarian Spotify (Mode Terkunci) ---
    if state == "awaiting_music" and message.text:
        bot.reply_to(message, "🔍 Memeriksa langsung ke dalam server...")
        result = search_spotify_track(message.text)
        
        # JIKA TERJADI ERROR, BOT AKAN MENAMPILKAN DIAGNOSA PENYEBABNYA
        if isinstance(result, str) and result.startswith("DEBUG_"):
            pesan_error = (
                "🚨 *SISTEM ERROR TERTANGKAP!*\n\n"
                "Bot berhasil mendeteksi letak kesalahannya. *Tolong screenshot/kirim pesan bot ini ke saya:*\n\n"
                f"`{result}`"
            )
            bot.reply_to(message, pesan_error, parse_mode="Markdown")
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
                    bot.send_audio(user_id, result['preview'], caption="🔊 Preview 30 Detik")
                except:
                    pass
            bot.send_message(user_id, "_(Mau cari lagu lain? Langsung ketik judulnya saja. Klik 💬 Chat untuk keluar.)_", parse_mode="Markdown")

    # --- 2. Logika Download Media (Mode Terkunci) ---
    elif state == "awaiting_url" and message.text:
        bot.reply_to(message, "⏳ Sedang memproses link...")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'media.%(ext)s', 'quiet': True, 'no_warnings': True}
            with YoutubeDL(ydl_opts) as ydl: 
                info = ydl.extract_info(message.text, download=True)
                ext = info.get('ext', 'mp4') 
                filename = f"media.{ext}"
                
                with open(filename, 'rb') as f:
                    if ext.lower() in ['jpg', 'jpeg', 'png', 'webp']:
                        bot.send_photo(user_id, f, caption="✅ Berhasil mengunduh foto!")
                    else:
                        bot.send_video(user_id, f, caption="✅ Berhasil mengunduh video!")
            os.remove(filename) 
            bot.send_message(user_id, "_(Kirim link lagi jika ingin download yang lain, atau klik 💬 Chat untuk keluar)_", parse_mode="Markdown")
        except Exception as e: 
            bot.reply_to(message, "❌ Gagal mengunduh.\n_(Kirim link yang benar, atau klik 💬 Chat untuk keluar)_", parse_mode="
        
