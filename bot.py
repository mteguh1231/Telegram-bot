import os
import io
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
import threading
import time
from PIL import Image
from google import genai
from google.genai import types
from gtts import gTTS
from yt_dlp import YoutubeDL
from duckduckgo_search import DDGS

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_ID = "5973565109"

bot = telebot.TeleBot(BOT_TOKEN)
user_chats = {}
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

MY_PERSONA = "Kamu adalah BotPro, asisten AI cerdas, sopan, humoris, dan suka memberikan saran bijak dengan bahasa Indonesia santai."

# ==========================================
# FUNGSI PENCARI INTERNET (Level 1)
# ==========================================
def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results: return "Maaf, tidak menemukan info terkini."
            search_context = "\n\n".join([f"Sumber: {r['href']}\nInfo: {r['body']}" for r in results])
            return f"Informasi dari internet:\n{search_context}"
    except:
        return "Gagal mengakses internet."

# ==========================================
# AUTOMASI (Scheduler)
# ==========================================
def daily_scheduler():
    while True:
        time.sleep(86400) # 24 jam
        try:
            bot.send_message(ADMIN_ID, "☀️ *Selamat Pagi!* \nBotPro siap melayani. Jangan lupa ngopi!")
        except Exception as e:
            logging.error(f"Scheduler error: {e}")

# ==========================================
# Command Dasar
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Halo! Saya BotPro. Saya punya kemampuan browsing internet, mendengar VN, dan menganalisa foto!")

@bot.message_handler(commands=['cuaca', 'berita', 'quote', 'reset'])
def handle_basic_commands(message):
    cmd = message.text.split()[0]
    if cmd == '/cuaca':
        try:
            kota = message.text.split(" ", 1)[1]
            response = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {response.text}", parse_mode="Markdown")
        except: bot.reply_to(message, "Format: /cuaca bandung")
    elif cmd == '/berita':
        bot.reply_to(message, "⏳ Mencari berita...")
        try:
            root = ET.fromstring(requests.get("http://rss.cnn.com/rss/edition.rss").content)
            teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. {item.find('title').text}\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
            bot.reply_to(message, teks, parse_mode="Markdown")
        except: bot.reply_to(message, "Gagal ambil berita.")
    elif cmd == '/quote':
        data = requests.get("https://dummyjson.com/quotes/random").json()
        bot.reply_to(message, f"💡 _{data['quote']}_ \n— *{data['author']}*", parse_mode="Markdown")
    elif cmd == '/reset':
        if message.chat.id in user_chats: del user_chats[message.chat.id]
        bot.reply_to(message, "🧹 Memori dihapus!")

# ==========================================
# CHAT HANDLER (Dengan Internet Search)
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    query = message.text
    try:
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(system_instruction=MY_PERSONA)
            )
        
        # Logika: Jika user menanyakan info terbaru, kita cari di internet
        keywords = ["siapa", "berita", "terbaru", "harga", "info", "tadi malam", "hari ini"]
        if any(key in query.lower() for key in keywords):
            search_info = search_internet(query)
            final_prompt = f"User bertanya: {query}. \n\n{search_info}\n\nJawab berdasarkan info di atas."
        else:
            final_prompt = query
            
        bot.reply_to(message, user_chats[message.chat.id].send_message(final_prompt).text, parse_mode="Markdown")
        except Exception as e:
        # Menangkap error 429 secara spesifik
        if "429" in str(e):
            bot.reply_to(message, "Wah, kuota AI-ku sedang terpakai banyak nih! Tunggu 1 menit lagi ya, biar aku bisa 'nafas' dulu. 😅")
        else:
            bot.reply_to(message, "Server sedang sibuk. Coba lagi nanti ya.")
        logging.error(f"Error Chat: {e}")
    
# ==========================================
# Telinga AI (Voice Note)
# ==========================================
@bot.message_handler(content_types=['voice'])
def handle_voice_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        nama_file_audio = f"vn_{message.chat.id}.ogg"
        with open(nama_file_audio, 'wb') as f: f.write(downloaded_file)
        
        audio_upload = ai_client.files.upload(
            file=nama_file_audio, 
            config=types.UploadFileConfig(mime_type="audio/ogg")
        )
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        
        response = user_chats[message.chat.id].send_message([audio_upload, "Balas pesan suara ini."])
        bot.reply_to(message, response.text, parse_mode="Markdown")
        os.remove(nama_file_audio)
    except:
        bot.reply_to(message, "Telinga AI sedang berdengung.")

# ==========================================
# Fitur Lainnya (Downloader, Vision, TTS)
# ==========================================
@bot.message_handler(commands=['download'])
def handle_download(message):
    try:
        url = message.text.split(" ", 1)[1]
        ydl_opts = {'format': 'best', 'outtmpl': 'video.%(ext)s'}
        with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=True)
        with open(f"{info['id']}.{info['ext']}", 'rb') as v: bot.send_video(message.chat.id, v)
        os.remove(f"{info['id']}.{info['ext']}")
    except: bot.reply_to(message, "Gagal unduh.")

@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
        res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
        bot.reply_to(message, res.text)
    except: bot.reply_to(message, "Gagal analisa.")

@bot.message_handler(commands=['suara'])
def handle_voice_ai(message):
    text = message.text.split(" ", 1)[1]
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=text)
    tts = gTTS(text=res.text, lang='id')
    tts.save("suara.ogg")
    with open("suara.ogg", 'rb') as f: bot.send_voice(message.chat.id, f)
    os.remove("suara.ogg")

if __name__ == "__main__":
    threading.Thread(target=daily_scheduler, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
