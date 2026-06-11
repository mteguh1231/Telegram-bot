import os, io, time, logging, zipfile, subprocess
import telebot
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL

# --- Import Library dengan Aman ---
try: from pdf2docx import Converter
except: Converter = None
try: import fitz
except: fitz = None
try: import pdfplumber, pandas as pd
except: pdfplumber = None; pd = None
try: from rembg import remove
except: remove = None
try: import cv2, numpy as np
except: cv2 = None; np = None
try: import qrcode
except: qrcode = None

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-1.5-flash"

user_states = {}
user_chats = {}

def send_main_menu(chat_id, text="🤖 *Bot Siap!* Silakan pilih menu:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m): send_main_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools"])
def menu(m):
    user_states[m.chat.id] = m.text
    if m.text == "📥 Downloader":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔺 YouTube", callback_data="dl_yt"))
        bot.reply_to(m, "📥 Kirim link YouTube-nya:", reply_markup=markup)
    else:
        bot.reply_to(m, f"✅ Mode {m.text} aktif. Kirimkan file/foto/teks terkait.")

@bot.message_handler(content_types=['document', 'photo', 'text'])
def handle_all(m):
    state = user_states.get(m.chat.id, "")
    
    # 1. AI CHAT
    if state == "💬 Chat AI" and m.text:
        if m.chat.id not in user_chats: user_chats[m.chat.id] = ai_client.chats.create(model=MODEL_NAME)
        try: bot.reply_to(m, user_chats[m.chat.id].send_message(m.text).text)
        except Exception as e: bot.reply_to(m, f"❌ AI Error: {e}")

    # 2. AI VISION
    elif state == "🤖 AI Vision" and m.photo:
        try:
            file_info = bot.get_file(m.photo[-1].file_id)
            img = Image.open(io.BytesIO(bot.download_file(file_info.file_path))).convert("RGB")
            res = ai_client.models.generate_content(model=MODEL_NAME, contents=[m.caption or "Analisis gambar ini", img])
            bot.reply_to(m, f"🤖 *Hasil:* {res.text}", parse_mode="Markdown")
        except Exception as e: bot.reply_to(m, f"❌ Error Vision: {e}")

    # 3. UTILITY (Hapus Background)
    elif state == "🛠️ Utility Tools" and m.photo and remove:
        try:
            msg = bot.reply_to(m, "🪄 Memproses...")
            img_data = bot.download_file(bot.get_file(m.photo[-1].file_id).file_path)
            out_io = io.BytesIO(remove(img_data))
            bot.send_document(m.chat.id, out_io, visible_file_name="nobg.png")
            bot.delete_message(m.chat.id, msg.message_id)
        except Exception as e: bot.reply_to(m, f"❌ Error: {e}")

    # 4. DOWNLOADER
    elif state == "📥 Downloader" and m.text and "http" in m.text:
        try:
            msg = bot.reply_to(m, "⏳ Mengunduh...")
            with YoutubeDL({'format': 'best', 'outtmpl': 'vid.mp4'}) as ydl: ydl.download([m.text])
            with open('vid.mp4', 'rb') as f: bot.send_video(m.chat.id, f)
            os.remove('vid.mp4'); bot.delete_message(m.chat.id, msg.message_id)
        except Exception as e: bot.reply_to(m, f"❌ Gagal: {e}")

if __name__ == "__main__":
    bot.infinity_polling()
    
