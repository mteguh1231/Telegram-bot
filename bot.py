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

# --- UI Menu ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 Chat AI"),
        types.KeyboardButton("🌐 Info Dunia"),
        types.KeyboardButton("🛠️ Alat Media"),
        types.KeyboardButton("⚙️ Pengaturan")
    )
    bot.send_message(message.chat.id, "Selamat datang! Pilih kategori fitur di bawah:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🤖 Chat AI", "🌐 Info Dunia", "🛠️ Alat Media", "⚙️ Pengaturan"])
def handle_menu_click(message):
    if message.text == "🤖 Chat AI":
        bot.reply_to(message, "Silakan ketik pertanyaanmu langsung. Saya akan menjawab sebagai AI.")
    elif message.text == "🌐 Info Dunia":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="cmd_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote")
        )
        bot.reply_to(message, "Pilih informasi yang ingin dilihat:", reply_markup=markup)
    elif message.text == "🛠️ Alat Media":
        bot.reply_to(message, "Gunakan perintah:\n/download [url] - Download Video\n/vision [kirim foto] - Analisis Foto\n/doc [kirim file] - Ringkas Dokumen")
    elif message.text == "⚙️ Pengaturan":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Reset Memori", callback_data="cmd_reset"))
        bot.reply_to(message, "Pengaturan Bot:", reply_markup=markup)

# --- Callback Handlers (Tombol Dinamis) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "cmd_cuaca":
        bot.reply_to(call.message, "Ketik: /cuaca [nama kota]")
    elif call.data == "cmd_berita":
        handle_berita(call.message)
    elif call.data == "cmd_quote":
        handle_quote(call.message)
    elif call.data == "cmd_reset":
        bot.reply_to(call.message, "Memori sesi telah di-reset.")

# --- Functional Handlers ---
def handle_berita(message):
    try:
        r = requests.get("http://rss.cnn.com/rss/edition.rss")
        root = ET.fromstring(r.content)
        teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. {item.find('title').text}\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
        bot.reply_to(message, teks, parse_mode="Markdown")
    except: bot.reply_to(message, "Gagal ambil berita.")

def handle_quote(message):
    data = requests.get("https://dummyjson.com/quotes/random").json()
    bot.reply_to(message, f"💡 _{data['quote']}_ \n— *{data['author']}*", parse_mode="Markdown")

@bot.message_handler(commands=['cuaca'])
def handle_cuaca(message):
    try:
        kota = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else "Jakarta"
        res = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t")
        bot.reply_to(message, f"🌤️ {res.text}")
    except: bot.reply_to(message, "Format: /cuaca jakarta")

@bot.message_handler(content_types=['text'])
def handle_chat(message):
    if message.text.startswith('/'): return
    try:
        user_id = message.chat.id
        history = ambil_memori(user_id)
        context = "\n".join([f"User: {h['message']}\nBot: {h['response']}" for h in history])
        if any(key in message.text.lower() for key in ["siapa", "berita", "terbaru"]):
            context += f"\nInfo Internet: {search_internet(message.text)}"
        
        res = ai_client.chats.create(model="gemini-2.5-flash").send_message(f"Ingatan:\n{context}\n\nUser: {message.text}")
        simpan_chat(user_id, message.text, res.text)
        bot.reply_to(message, res.text)
    except Exception as e:
        if "429" in str(e):
            bot.reply_to(message, "⚠️ *Maaf, kuota harian bot sedang penuh.* Coba lagi besok ya!")
        else:
            bot.reply_to(message, "Sedang ada gangguan teknis.")

# --- Start ---
if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling()
    
