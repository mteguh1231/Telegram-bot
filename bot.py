import os
import io
import time
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
    url_token = "https://accounts.spotify.com/api/token"
    url_search = "https://api.spotify.com/v1/search"
    
    try:
        res_t = requests.post(
            url_token, 
            data={"grant_type": "client_credentials"}, 
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET), 
            timeout=10
        )
        
        if res_t.status_code != 200:
            return f"❌ Error API Spotify (Token): {res_t.status_code}\nPastikan CLIENT ID & SECRET valid."
            
        token = res_t.json().get("access_token")
        
        headers = {"Authorization": f"Bearer {token}"}
        params = {"q": query, "type": "track", "limit": 1}
        
        res_s = requests.get(url_search, headers=headers, params=params, timeout=10)
        
        if res_s.status_code != 200:
            return f"❌ Error Pencarian: {res_s.status_code}"
            
        items = res_s.json().get("tracks", {}).get("items", [])
        if not items: 
            return "⚠️ Lagu tidak ditemukan. Coba judul atau artis yang lebih spesifik."
        
        track = items[0]
        return f"🎵 {track['name']} - {track['artists'][0]['name']}\n🔗 {track['external_urls']['spotify']}"
        
    except Exception as e:
        return f"❌ Error sistem: {str(e)}"

# --- Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    # Animasi Loading Start
    loading_msg = bot.reply_to(m, "🔄 Menyiapkan sistem...")
    time.sleep(0.5)
    bot.edit_message_text("⚙️ Memuat menu...", chat_id=m.chat.id, message_id=loading_msg.message_id)
    time.sleep(0.5)
    
    # Hapus pesan loading dan kirim menu utama
    bot.delete_message(m.chat.id, loading_msg.message_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💬 Chat"), types.KeyboardButton("🎵 Musik"), types.KeyboardButton("📥 Download"))
    
    bot.send_message(m.chat.id, "🤖 *Bot siap digunakan!*\nSilakan pilih menu di bawah ini:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["💬 Chat", "🎵 Musik", "📥 Download"])
def menu(m):
    if m.text == "💬 Chat": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat Aktif.*\nSilakan ngobrol dengan AI!", parse_mode="Markdown")
    elif m.text == "🎵 Musik": 
        user_states[m.chat.id] = "music"
        bot.reply_to(m, "🎵 *Mode Musik Aktif.*\nKetik judul lagu yang ingin kamu cari di Spotify:", parse_mode="Markdown")
    elif m.text == "📥 Download": 
        user_states[m.chat.id] = "download"
        bot.reply_to(m, "📥 *Mode Download Aktif.*\nKirim link video yang ingin diunduh:", parse_mode="Markdown")

@bot.message_handler(content_types=['text'])
def handle(m):
    state = user_states.get(m.chat.id, "chat")
    
    # --- FITUR MUSIK ---
    if state == "music":
        loading_msg = bot.reply_to(m, "🔍 *Sedang mencari lagu...*", parse_mode="Markdown")
        bot.send_chat_action(m.chat.id, 'typing') # Status indikator "Bot is typing..."
        
        result = search_spotify_track(m.text)
        
        # Animasi edit teks saat hasil ketemu
        bot.edit_message_text(result, chat_id=m.chat.id, message_id=loading_msg.message_id)
        
        # Pengingat supaya pengguna tahu mereka masih di mode musik
        bot.send_message(m.chat.id, "💡 _Ketik judul lagu lain untuk mencari lagi, atau klik tombol menu lain._", parse_mode="Markdown")

    # --- FITUR DOWNLOAD ---
    elif state == "download":
        try:
            loading_msg = bot.reply_to(m, "⏳ *Memproses link...*", parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'record_video')
            
            ydl_opts = {'format': 'best', 'outtmpl': 'media.mp4', 'quiet': True}
            with YoutubeDL(ydl_opts) as ydl: 
                ydl.download([m.text])
                
            bot.edit_message_text("🚀 *Mengirim video...*", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'upload_video')
            
            with open('media.mp4', 'rb') as f: 
                bot.send_video(m.chat.id, f)
            os.remove('media.mp4')
            
            bot.delete_message(m.chat.id, loading_msg.message_id) # Hapus teks loading setelah video terkirim
            bot.send_message(m.chat.id, "💡 _Kirim link lagi untuk download video lain._", parse_mode="Markdown")
        except Exception as e: 
            bot.edit_message_text("❌ *Gagal mengunduh.* Pastikan link valid dan dapat diakses publik.", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    
    # --- FITUR CHAT AI ---
    elif state == "chat":
        if m.chat.id not in user_chats: 
            user_chats[m.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        
        try:
            loading_msg = bot.reply_to(m, "💭 *AI sedang berpikir...*", parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'typing')
            
            reply_text = user_chats[m.chat.id].send_message(m.text).text
            
            # Ganti tulisan "AI sedang berpikir" dengan jawaban AI
            bot.edit_message_text(reply_text, chat_id=m.chat.id, message_id=loading_msg.message_id)
        except Exception as e:
            bot.edit_message_text("❌ Maaf, sistem AI sedang mengalami kendala.", chat_id=m.chat.id, message_id=loading_msg.message_id)

if __name__ == "__main__": 
    print("Bot sedang berjalan...")
    bot.infinity_polling()
    
