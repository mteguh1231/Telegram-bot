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

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_ID = "5973565109" # ID Kamu sudah terpasang!

bot = telebot.TeleBot(BOT_TOKEN)
user_chats = {}
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Definisi Persona
MY_PERSONA = "Kamu adalah BotPro, asisten AI yang cerdas, sopan, humoris, dan suka memberikan saran bijak dengan bahasa Indonesia yang santai."

# ==========================================
# AUTOMASI (Scheduler)
# ==========================================
def daily_scheduler():
    while True:
        # Menunggu 24 jam (86400 detik) sebelum mengirim pesan lagi
        time.sleep(86400) 
        try:
            bot.send_message(ADMIN_ID, "☀️ *Selamat Pagi!* \nBotPro siap melayani. Jangan lupa ngopi dan tetap semangat hari ini!")
        except Exception as e:
            logging.error(f"Gagal kirim pesan otomatis: {e}")

# ==========================================
# Chat Handler (Dengan Persona)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Halo! Saya BotPro, asisten AI pribadimu. Apa yang bisa saya bantu hari ini?")

@bot.message_handler(content_types=['text'])
def handle_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(system_instruction=MY_PERSONA)
            )
        bot.reply_to(message, user_chats[message.chat.id].send_message(message.text).text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "Server sedang sibuk.")

# ==========================================
# Fungsi Lainnya (Voice, Vision, Download, dll)
# ==========================================
@bot.message_handler(content_types=['voice'])
def handle_voice_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        nama_file_audio = f"vn_{message.chat.id}.ogg"
        with open(nama_file_audio, 'wb') as new_file: new_file.write(downloaded_file)
        
        audio_upload = ai_client.files.upload(
            file=nama_file_audio, 
            config=types.UploadFileConfig(mime_type="audio/ogg")
        )
        
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        
        response = user_chats[message.chat.id].send_message([audio_upload, "Balas pesan suara ini dalam bahasa Indonesia."])
        bot.reply_to(message, response.text, parse_mode="Markdown")
        os.remove(nama_file_audio)
    except Exception as e:
        bot.reply_to(message, "Maaf, telinga AI sedang berdengung.")
        logging.error(f"Error Voice Chat: {e}")

@bot.message_handler(commands=['download'])
def handle_download(message):
    try:
        url = message.text.split(" ", 1)[1]
        msg_tunggu = bot.reply_to(message, "⏳ Memproses...")
        bot.send_chat_action(message.chat.id, 'upload_video')
        ydl_opts = {'format': 'best[filesize<50M]', 'outtmpl': f'video_{message.chat.id}.%(ext)s', 'quiet': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        with open(filename, 'rb') as video:
            bot.send_video(message.chat.id, video, caption="🎥 Berhasil!")
        os.remove(filename)
        bot.delete_message(message.chat.id, msg_tunggu.message_id)
    except:
        bot.reply_to(message, "❌ Gagal mengunduh.")

@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    if not ai_client: return
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
        response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini"])
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "Gagal menganalisa gambar.")

if __name__ == "__main__":
    # Jalankan Scheduler di latar belakang
    threading.Thread(target=daily_scheduler, daemon=True).start()
    logging.info("Bot Super V8 (PRO EDITION) berjalan...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
