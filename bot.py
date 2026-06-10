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
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

user_states = {}
user_chats = {} 

# --- Helper Spotify ---
def search_spotify_track(query):
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return "Error: Client ID/Secret kosong."
    
    u_token = "https://accounts.spotify.com/api/token"
    u_search = "https://api.spotify.com/v1/search"
    
    try:
        # Get Token
        res_t = requests.post(u_token, data={"grant_type": "client_credentials"}, 
                              auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET), timeout=10)
        token = res_t.json().get("access_token")
        
        # Search
        res_s = requests.get(u_search, headers={"Authorization": f"Bearer {token}"}, 
                             params={"q": query, "type": "track", "limit": 1}, timeout=10)
        items = res_s.json().get("tracks", {}).get("items", [])
        
        if not items: return "Lagu tidak ditemukan."
        track = items[0]
        
        # Format hasil aman
        msg = f"🎵 {track.get('name')} - {track['artists'][0]['name']}\n"
        msg += f"🔗 {track.get('external_urls', {}).get('spotify')}"
        return msg
    except Exception as e: 
        return f"Error: {str(e)}"

# --- Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = "chat"
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add(types.KeyboardButton("💬 Chat"), types.KeyboardButton("🧰 Tools"), 
             types.KeyboardButton("🎵 Musik"), types.KeyboardButton("⚙️ Reset"))
    bot.reply_to(message, "Halo! Gunakan menu di bawah.", reply_markup=menu)

@bot.message_handler(func=lambda m: m.text in ["💬 Chat", "🧰 Tools", "🎵 Musik", "⚙️ Reset"])
def menu(m):
    if m.text == "💬 Chat": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "Mode Chat aktif.")
    elif m.text == "🎵 Musik": 
        user_states[m.chat.id] = "awaiting_music"
        bot.reply_to(m, "Ketik judul lagu:")
    elif m.text == "🧰 Tools": 
        user_states[m.chat.id] = "tools"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Download", callback_data="state_download"))
        bot.reply_to(m, "Pilih tool:", reply_markup=kb)
    elif m.text == "⚙️ Reset": 
        user_chats.pop(m.chat.id, None)
        bot.reply_to(m, "Sesi di-reset!")

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if c.data == "state_download": 
        user_states[c.message.chat.id] = "awaiting_url"
        bot.edit_message_text("Kirim link download:", c.message.chat.id, c.message.message_id)

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle(m):
    state = user_states.get(m.chat.id, "chat")
    
    if state == "awaiting_music" and m.text:
        res = search_spotify_track(m.text)
        bot.reply_to(m, res)
        
    elif state == "awaiting_url" and m.text:
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'media.mp4'}
            with YoutubeDL(ydl_opts) as ydl: ydl.download([m.text])
            with open('media.mp4', 'rb') as f: bot.send_video(m.chat.id, f)
            os.remove('media.mp4')
        except: bot.reply_to(m, "Gagal download.")
        
    elif state == "chat" and m.text:
        if m.chat.id not in user_chats: 
            user_chats[m.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        bot.reply_to(m, user_chats[m.chat.id].send_message(m.text).text)

if __name__ == "__main__": 
    bot.infinity_polling()
    
