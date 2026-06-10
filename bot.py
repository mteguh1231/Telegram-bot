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

user_states = {}
user_chats = {} 

# --- Helper Spotify (RESMI & AMAN) ---
def search_spotify_track(query):
    # URL Resmi (Gunakan ini agar tidak error 403)
    url_token = "https://accounts.spotify.com/api/token"
    url_search = "https://api.spotify.com/v1/search"
    
    try:
        # 1. Ambil Token
        res_t = requests.post(url_token, 
                              data={"grant_type": "client_credentials"}, 
                              auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET), 
                              timeout=10)
        
        # Jika kodenya 401 atau 403, berarti CLIENT_ID/SECRET kamu di Railway salah
        if res_t.status_code != 200:
            return f"Error API Spotify: {res_t.status_code} (Cek ID & Secret di Railway)"
            
        token = res_t.json().get("access_token")
        
        # 2. Cari Lagu
        headers = {"Authorization": f"Bearer {token}"}
        params = {"q": query, "type": "track", "limit": 1}
        res_s = requests.get(url_search, headers=headers, params=params, timeout=10)
        
        if res_s.status_code != 200:
            return f"Error Pencarian: {res_s.status_code}"
            
        items = res_s.json().get("tracks", {}).get("items", [])
        if not items: 
            return "Lagu tidak ditemukan."
        
        track = items[0]
        return f"🎵 {track['name']} - {track['artists'][0]['name']}\n🔗 {track['external_urls']['spotify']}"
        
    except Exception as e:
        return f"Error sistem: {str(e)}"
        

# --- Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "Bot siap! Gunakan menu: /chat, /musik, /download", 
                 reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                     types.KeyboardButton("💬 Chat"), types.KeyboardButton("🎵 Musik"), 
                     types.KeyboardButton("📥 Download")))

@bot.message_handler(func=lambda m: m.text in ["💬 Chat", "🎵 Musik", "📥 Download"])
def menu(m):
    if m.text == "💬 Chat": user_states[m.chat.id] = "chat"; bot.reply_to(m, "Mode Chat.")
    elif m.text == "🎵 Musik": user_states[m.chat.id] = "music"; bot.reply_to(m, "Ketik judul lagu:")
    elif m.text == "📥 Download": user_states[m.chat.id] = "download"; bot.reply_to(m, "Kirim link:")

@bot.message_handler(content_types=['text'])
def handle(m):
    state = user_states.get(m.chat.id, "chat")
    
    if state == "music" and m.text:
        bot.reply_to(m, search_spotify_track(m.text))
        
    elif state == "download" and m.text:
        try:
            bot.reply_to(m, "Sedang download...")
            ydl_opts = {'format': 'best', 'outtmpl': 'media.mp4', 'quiet': True}
            with YoutubeDL(ydl_opts) as ydl: ydl.download([m.text])
            with open('media.mp4', 'rb') as f: bot.send_video(m.chat.id, f)
            os.remove('media.mp4')
        except: bot.reply_to(m, "Gagal.")
        
    elif state == "chat" and m.text:
        if m.chat.id not in user_chats: user_chats[m.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        bot.reply_to(m, user_chats[m.chat.id].send_message(m.text).text)

if __name__ == "__main__": bot.infinity_polling()
            
