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

MY_PERSONA = "Kamu adalah BotPro, asisten AI cerdas, sopan, humoris, dan ahli menganalisis dokumen serta data."

# ==========================================
# FUNGSI PENDUKUNG
# ==========================================
def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            return "\n\n".join([f"Sumber: {r['href']}\nInfo: {r['body']}" for r in results]) if results else "Info tidak ditemukan."
    except: return "Gagal akses internet."

def daily_scheduler():
    while True:
        time.sleep(86400)
        try: bot.send_message(ADMIN_ID, "☀️ Selamat Pagi! BotPro siap melayani.")
        except: pass

# ==========================================
# HANDLERS (Perintah Dasar)
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Halo! Saya BotPro. Saya bisa browsing, baca dokumen, mendengar VN, dan menganalisa foto!")

@bot.message_handler(commands=['cuaca', 'berita', 'quote', 'reset'])
def handle_basic_commands(message):
    cmd = message.text.split()[0]
    if cmd == '/cuaca':
        try:
            kota = message.text.split(" ", 1)[1]
            res = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {res.text}", parse_mode="Markdown")
        except: bot.reply_to(message, "Format: /cuaca bandung")
    elif cmd == '/berita':
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
# HANDLERS (AI Fitur: Chat, Doc, Foto, Suara, Download)
# ==========================================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'upload_document')
    try:
        file_info = bot.get_file(message.document.file_id)
        nama_file = message.document.file_name
        with open(nama_file, 'wb') as f: f.write(bot.download_file(file_info.file_path))
        
        # Upload file ke Gemini
        doc_upload = ai_client.files.upload(file=nama_file)
        
        # Loop: Tunggu sampai status file menjadi "ACTIVE"
        bot.reply_to(message, "⏳ AI sedang membaca dokumen, tunggu sebentar ya...")
        while doc_upload.state.name == "PROCESSING":
            time.sleep(2)
            doc_upload = ai_client.files.get(name=doc_upload.name)
            
        if doc_upload.state.name != "ACTIVE":
            bot.reply_to(message, "Gagal memproses file.")
            return

        # Proses analisa
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
            
        prompt = message.caption if message.caption else "Tolong ringkas dokumen ini."
        response = user_chats[message.chat.id].send_message([doc_upload, prompt])
        
        bot.reply_to(message, f"📄 *Analisa Dokumen:*\n\n{response.text}", parse_mode="Markdown")
        os.remove(nama_file)
    except Exception as e:
        bot.reply_to(message, "Gagal membaca dokumen.")
        logging.error(f"Error Doc: {e}")
        

@bot.message_handler(content_types=['text'])
def handle_chat(message):
    bot.send_chat_action(message.chat.id, 'typing')
    query = message.text
    try:
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=MY_PERSONA))
        
        if any(key in query.lower() for key in ["siapa", "berita", "terbaru", "harga", "info"]):
            final_prompt = f"User bertanya: {query}. \n\n{search_internet(query)}\n\nJawab dengan sopan."
        else: final_prompt = query
            
        bot.reply_to(message, user_chats[message.chat.id].send_message(final_prompt).text, parse_mode="Markdown")
    except Exception as e:
        if "429" in str(e): bot.reply_to(message, "Kuota AI penuh, tunggu sebentar ya! 😅")
        else: bot.reply_to(message, "Server sibuk.")

@bot.message_handler(content_types=['voice'])
def handle_voice_chat(message):
    file_info = bot.get_file(message.voice.file_id)
    nama = "vn.ogg"
    with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
    audio_upload = ai_client.files.upload(file=nama, config=types.UploadFileConfig(mime_type="audio/ogg"))
    if message.chat.id not in user_chats: user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
    bot.reply_to(message, user_chats[message.chat.id].send_message([audio_upload, "Balas pesan ini."]).text)
    os.remove(nama)

@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
    bot.reply_to(message, res.text)

@bot.message_handler(commands=['download'])
def handle_download(message):
    url = message.text.split(" ", 1)[1]
    ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
    with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=True)
    with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(message.chat.id, v)
    os.remove(f"vid.{info['ext']}")

if __name__ == "__main__":
    threading.Thread(target=daily_scheduler, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
