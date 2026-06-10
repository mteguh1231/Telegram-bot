import os
import io
import logging
import telebot
import requests
import time
import threading
import xml.etree.ElementTree as ET
from telebot import types
from PIL import Image
from google import genai
from google.genai import types as genai_types
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

# --- UI / Buttons Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🌤️ Cuaca")
    btn2 = types.KeyboardButton("📰 Berita")
    btn3 = types.KeyboardButton("💡 Quote")
    btn4 = types.KeyboardButton("⚙️ Opsi Lain")
    markup.add(btn1, btn2, btn3, btn4)
    bot.send_message(message.chat.id, "Halo! Pilih menu di bawah atau ketik langsung pesanmu:", reply_markup=markup)

@bot.message_handler(commands=['opsi'])
def show_inline(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Support Bot", callback_data="support")
    btn2 = types.InlineKeyboardButton("Reset Memori", callback_data="reset_db")
    markup.add(btn1, btn2)
    bot.reply_to(message, "Pilih opsi pengaturan:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "support":
        bot.answer_callback_query(call.id, "Terima kasih telah menggunakan bot!")
    elif call.data == "reset_db":
        bot.answer_callback_query(call.id, "Memori sesi telah di-reset.")
        bot.send_message(call.message.chat.id, "Memori sesi lokal di-reset.")

# --- Text-based Command Handlers ---
@bot.message_handler(func=lambda message: message.text in ["🌤️ Cuaca", "📰 Berita", "💡 Quote", "⚙️ Opsi Lain"])
def handle_buttons(message):
    if message.text == "🌤️ Cuaca": bot.reply_to(message, "Ketik: /cuaca [nama kota]")
    elif message.text == "📰 Berita": handle_commands(message) # Akan diproses fungsi di bawah
    elif message.text == "💡 Quote": handle_commands(message)
    elif message.text == "⚙️ Opsi Lain": show_inline(message)

@bot.message_handler(commands=['cuaca', 'berita', 'quote', 'reset'])
def handle_commands(message):
    cmd = message.text.split()[0]
    if cmd == '/cuaca' or message.text == "🌤️ Cuaca":
        try:
            kota = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else "Jakarta"
            res = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
            bot.reply_to(message, f"🌤️ {res.text}")
        except: bot.reply_to(message, "Format: /cuaca jakarta")
    elif cmd == '/berita' or message.text == "📰 Berita":
        try:
            r = requests.get("http://rss.cnn.com/rss/edition.rss")
            root = ET.fromstring(r.content)
            teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. {item.find('title').text}\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
            bot.reply_to(message, teks, parse_mode="Markdown")
        except: bot.reply_to(message, "Gagal ambil berita.")
    elif cmd == '/quote' or message.text == "💡 Quote":
        data = requests.get("https://dummyjson.com/quotes/random").json()
        bot.reply_to(message, f"💡 _{data['quote']}_ \n— *{data['author']}*", parse_mode="Markdown")
    elif cmd == '/reset':
        bot.reply_to(message, "Memori sesi lokal di-reset.")

# --- Media & File Handlers ---
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
    audio_upload = ai_client.files.upload(file=nama, config=genai_types.UploadFileConfig(mime_type="audio/ogg"))
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
    if message.text.startswith('/'): return # Skip command
    user_id = message.chat.id
    history = ambil_memori(user_id)
    context = "\n".join([f"User: {h['message']}\nBot: {h['response']}" for h in history])
    if any(key in message.text.lower() for key in ["siapa", "berita", "terbaru"]):
        context += f"\nInfo Internet: {search_internet(message.text)}"
    res = ai_client.chats.create(model="gemini-2.5-flash").send_message(f"Ingatan:\n{context}\n\nUser: {message.text}")
    simpan_chat(user_id, message.text, res.text)
    bot.reply_to(message, res.text)

# --- Start ---
if __name__ == "__main__":
    print("Bot berjalan dengan UI...")
    bot.remove_webhook()
    bot.infinity_polling()
        
