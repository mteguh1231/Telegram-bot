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

# --- Helper Fungsi Spotify (MODE DETEKTIF) ---
def search_spotify_track(query):
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return "DEBUG_ERROR: Client ID/Secret belum ada di Railway."
        
    kata1 = "accounts"
    kata2 = "spo" + "tify"
    kata3 = "com"
    url_token = f"https://{kata1}.{kata2}.{kata3}/api/token"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    
    try:
        res_token = requests.post(
            url_token, headers=headers, data=data, 
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET), timeout=10
        )
        if res_token.status_code != 200:
            return f"DEBUG_TOKEN_ERROR: Kode {res_token.status_code} | Info: {res_token.text}"
        token = res_token.json().get("access_token")
    except Exception as e:
        return f"DEBUG_TOKEN_CRASH: Jaringan error - {str(e)}"
        
    kata4 = "api"
    url_search = f"https://{kata4}.{kata2}.{kata3}/v1/search"
    headers_search = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "track", "limit": 1}
    
    try:
        res_search = requests.get(
            url_search, headers=headers_search, params=params, timeout=10
        )
        if res_search.status_code != 200:
            return f"DEBUG_SEARCH_ERROR: Kode {res_search.status_code} | Info: {res_search.text}"
        
        items = res_search.json().get("tracks", {}).get("items", [])
        if not items:
            return "DEBUG_NOT_FOUND: Lagu tidak ada di database."
            
        track = items[0]
        return {
            "title": track.get("name"),
            "artist": track["artists"][0]["name"] if track["artists"] else "Unknown",
            "album": track.get("album", {}).get("name"),
            "link": track.get("external_urls", {}).get("spotify"),
            "preview": track.get("preview_url")
        }
    except Exception as e:
        return f"DEBUG_SEARCH_CRASH: Error Python - {str(e)}"

# --- Command /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = "chat"
    welcome_text = (
        "✨ *Selamat Datang di BotPro Elite!*\n\n"
        "Asisten AI pribadi Anda (Powered by Gemini 2.5 Flash).\n\n"
        "🚀 *Kemampuan saya:*\n"
        "• 💬 *Chat:* Ngobrol pintar dengan AI.\n"
        "• 🧰 *Tools:* Download Media, analisis foto, ringkas doc.\n"
        "• 🎵 *Musik:* Cari lagu Spotify!\n\n"
        "Gunakan tombol di bawah untuk mulai."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
    show_main_menu(message.chat.id, "Pilih kategori fitur:")

# --- Handle Navigasi Menu Utama ---
@bot.message_handler(func=lambda message: message.text in ["💬 Chat", "🧰 Tools", "🎵 Musik", "⚙️ Reset"])
def handle_menu_click(message):
    user_id = message.chat.id
    
    if message.text == "💬 Chat":
        user_states[user_id] = "chat"
        bot.reply_to(message, "💬 *Mode Chat AI Aktif*\nKirim pertanyaanmu!")
    elif message.text == "🎵 Musik":
        user_states[user_id] = "awaiting_music"
        teks = "🎵 *Mode Pencarian Musik Aktif*\nKetik nama penyanyi & judul lagu.\n_(Klik 💬 Chat untuk keluar)_"
        bot.reply_to(message, teks, parse_mode="Markdown")
    elif message.text == "🧰 Tools":
        user_states[user_id] = "tools"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Media", callback_data="state_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc"),
            types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_back")
        )
        bot.reply_to(message, "🧰 *Pusat Alat Media:*", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "⚙️ Reset":
        if user_id in user_chats:
            del user_chats[user_id]
        bot.reply_to(message, "⚙️ Sesi chat AI di-reset!")

# --- Callback Navigasi ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "cmd_back":
        bot.delete_message(user_id, call.message.message_id)
        user_states[user_id] = "chat"
        show_main_menu(user_id, "Kembali ke Menu Utama.")
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        teks = "📥 *Mode Download*\nKirim link media.\n_(Klik 💬 Chat untuk keluar)_"
        bot.edit_message_text(teks, user_id, call.message.message_id, parse_mode="Markdown")
    elif call.data == "media_vision": 
        user_states[user_id] = "chat"
        bot.reply_to(call.message, "📸 Kirim foto untuk dianalisis.")
    elif call.data == "media_doc": 
        user_states[user_id] = "chat"
        bot.reply_to(call.message, "📄 Kirim dokumen (.pdf/.txt).")

# --- Logic & Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id, "chat")

    # --- 1. Pencarian Spotify ---
    if state == "awaiting_music" and message.text:
        bot.reply_to(message, "🔍 Memeriksa server...")
        result = search_spotify_track(message.text)
        
        if isinstance(result, str) and result.startswith("DEBUG_"):
            pesan_error = f"🚨 *ERROR TERTANGKAP!*\n\n`{result}`"
            bot.reply_to(message, pesan_error, parse_mode="Markdown")
        else:
            info_lagu = (
                f"🎵 *Lagu Ditemukan!*\n\
    
