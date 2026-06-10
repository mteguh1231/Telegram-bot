import os
import io
import logging
import telebot
import requests
import time
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

# --- Helper Functions ---
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

def handle_quota_error(bot, message, e):
    if "429" in str(e):
        bot.reply_to(message, "⚠️ *Maaf, kuota harian bot sedang penuh.* Coba lagi besok ya!")
    else:
        bot.reply_to(message, "Sedang ada gangguan teknis.")

# --- UI Menu Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 Chat AI"),
        types.KeyboardButton("🌐 Info Dunia"),
        types.KeyboardButton("🛠️ Alat Media"),
        types.KeyboardButton("⚙️ Pengaturan")
    )
    bot.send_message(message.chat.id, "Halo! BotPro siap melayani. Pilih menu di bawah:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🤖 Chat AI", "🌐 Info Dunia", "🛠️ Alat Media", "⚙️ Pengaturan"])
def handle_menu_click(message):
    if message.text == "🤖 Chat AI":
        bot.reply_to(message, "Silakan kirim pesan atau pertanyaanmu.")
    elif message.text == "🌐 Info Dunia":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="cmd_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote")
        )
        bot.reply_to(message, "Pilih info yang diinginkan:", reply_markup=markup)
    elif message.text == "🛠️ Alat Media":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Video", callback_data="media_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc")
        )
        bot.reply_to(message, "🛠️ Pusat Alat Media:", reply_markup=markup)
    elif message.text == "⚙️ Pengaturan":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Reset Memori", callback_data="cmd_reset"))
        bot.reply_to(message, "⚙️ Pengaturan:", reply_markup=markup)

# --- Callbacks & Media Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "cmd_cuaca": bot.reply_to(call.message, "Ketik: /cuaca [nama kota]")
    elif call.data == "cmd_berita": handle_berita(call.message)
    elif call.data == "cmd_quote": handle_quote(call.message)
    elif call.data == "cmd_reset": bot.reply_to(call.message, "Memori sesi lokal di-reset.")
    elif call.data == "media_download": bot.reply_to(call.message, "Kirim: /download [url video]")
    elif call.data == "media_vision": bot.reply_to(call.message, "Kirim foto dan beri pertanyaan.")
    elif call.data == "media_doc": bot.reply_to(call.message, "Kirim file dokumen (PDF/TXT).")

# --- Commands & Logic ---
@bot.message_handler(commands=['cuaca'])
def handle_cuaca(message):
    try:
        kota = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else "Jakarta"
        res = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
        bot.reply_to(message, f"🌤️ {res.text}")
    except: bot.reply_to(message, "Format: /cuaca jakarta")

def handle_berita(message):
    try:
        r = requests.get("http://rss.cnn.com/rss/edition.rss")
        root = ET.fromstring(r.content)
        teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. {item.find('title').text}\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
        bot.reply_to(message, teks, parse_mode="Markdown")
    except: bot.reply_to(message, "Gagal ambil berita.")

def handle_quote(message):
    try:
        data = requests.get("https://dummyjson.com/quotes/random").json()
        bot.reply_to(message, f"💡 _{data['quote']}_ \n— *{data['author']}*", parse_mode="Markdown")
    except: bot.reply_to(message, "Gagal ambil quote.")

@bot.message_handler(commands=['download'])
def handle_download(message):
    try:
        url = message.text.split(" ", 1)[1]
        ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
        with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=True)
        with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(message.chat.id, v)
        os.remove(f"vid.{info['ext']}")
    except: bot.reply_to(message, "Gagal unduh.")

@bot.message_handler(content_types=['document', 'photo', 'text'])
def handle_all(message):
    if message.content_type == 'document':
        try:
            file_info = bot.get_file(message.document.file_id)
            nama = message.document.file_name
            with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
            doc = ai_client.files.upload(file=nama)
            res = ai_client.chats.create(model="gemini-2.5-flash").send_message([doc, "Ringkas ini."])
            bot.reply_to(message, res.text)
            os.remove(nama)
        except Exception as e: handle_quota_error(bot, message, e)
    
    elif message.content_type == 'photo':
        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
            res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
            bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)

    elif message.content_type == 'text':
        if message.text.startswith('/'): return
        try:
            res = ai_client.chats.create(model="gemini-2.5-flash").send_message(message.text)
            bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)

# --- Start ---
if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot sudah siap!")
    bot.infinity_polling()
    
