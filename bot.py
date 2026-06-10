import os
import io
import logging
import telebot
import requests
import time
import xml.etree.ElementTree as ET
from flask import Flask, request
from PIL import Image
from google import genai
from google.genai import types
from yt_dlp import YoutubeDL
from duckduckgo_search import DDGS
from supabase import create_client, Client
from gtts import gTTS

# --- Setup ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- Helpers ---
def simpan_chat(user_id, message, response):
    if supabase:
        supabase.table("chat_history").insert({"user_id": str(user_id), "message": message, "response": response}).execute()

def ambil_memori(user_id):
    if not supabase: return []
    res = supabase.table("chat_history").select("*").eq("user_id", str(user_id)).order("created_at", desc=True).limit(5).execute()
    return res.data[::-1]

def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            return "\n\n".join([f"Sumber: {r['href']}\nInfo: {r['body']}" for r in results]) if results else "Info tidak ditemukan."
    except: return "Gagal akses internet."

# --- Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "BotPro Webhook Aktif! Saya siap membantu.")

@bot.message_handler(commands=['cuaca', 'berita', 'quote', 'reset'])
def handle_commands(message):
    cmd = message.text.split()[0]
    if cmd == '/cuaca':
        try:
            kota = message.text.split(" ", 1)[1]
            res = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {res.text}")
        except: bot.reply_to(message, "Format: /cuaca jakarta")
    elif cmd == '/berita':
        try:
            r = requests.get("http://rss.cnn.com/rss/edition.rss")
            root = ET.fromstring(r.content)
            teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. {item.find('title').text}\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
            bot.reply_to(message, teks, parse_mode="Markdown")
        except: bot.reply_to(message, "Gagal ambil berita.")
    elif cmd == '/reset':
        bot.reply_to(message, "Memori sesi lokal di-reset.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        nama_file = message.document.file_name
        with open(nama_file, 'wb') as f: f.write(bot.download_file(file_info.file_path))
        doc_upload = ai_client.files.upload(file=nama_file)
        res = ai_client.chats.create(model="gemini-2.5-flash").send_message([doc_upload, "Ringkas dokumen ini."])
        bot.reply_to(message, res.text)
        os.remove(nama_file)
    except: bot.reply_to(message, "Gagal baca dokumen.")

@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
    bot.reply_to(message, res.text)

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    file_info = bot.get_file(message.voice.file_id)
    nama = "vn.ogg"
    with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
    audio_upload = ai_client.files.upload(file=nama, config=types.UploadFileConfig(mime_type="audio/ogg"))
    res = ai_client.chats.create(model="gemini-2.5-flash").send_message([audio_upload, "Balas pesan suara ini."])
    bot.reply_to(message, res.text)
    os.remove(nama)

@bot.message_handler(commands=['download'])
def handle_download(message):
    try:
        url = message.text.split(" ", 1)[1]
        ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
        with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=True)
        with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(message.chat.id, v)
        os.remove(f"vid.{info['ext']}")
    except: bot.reply_to(message, "Gagal unduh.")

@bot.message_handler(content_types=['text'])
def handle_chat(message):
    user_id = message.chat.id
    history = ambil_memori(user_id)
    context = "\n".join([f"User: {h['message']}\nBot: {h['response']}" for h in history])
    if any(key in message.text.lower() for key in ["siapa", "berita", "terbaru"]):
        context += f"\nInfo Internet: {search_internet(message.text)}"
    res = ai_client.chats.create(model="gemini-2.5-flash").send_message(f"Ingatan:\n{context}\n\nUser: {message.text}")
    simpan_chat(user_id, message.text, res.text)
    bot.reply_to(message, res.text)

# --- Webhook ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
            
