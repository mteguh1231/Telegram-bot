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

MY_PERSONA = "Kamu adalah BotPro, asisten AI cerdas yang ahli menganalisis dokumen, data, dan memberikan ringkasan yang akurat."

# ==========================================
# FUNGSI PENCARI INTERNET
# ==========================================
def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results: return "Tidak menemukan info terkini."
            return "\n\n".join([f"Sumber: {r['href']}\nInfo: {r['body']}" for r in results])
    except: return "Gagal akses internet."

# ==========================================
# HANDLER DOKUMEN (Level 2: Document Analyzer)
# ==========================================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'upload_document')
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        nama_file = message.document.file_name
        
        with open(nama_file, 'wb') as f: f.write(downloaded_file)
        
        # Upload ke Gemini
        doc_upload = ai_client.files.upload(file=nama_file)
        
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
            
        prompt = message.caption if message.caption else "Tolong ringkas dokumen ini."
        response = user_chats[message.chat.id].send_message([doc_upload, prompt])
        
        bot.reply_to(message, f"📄 *Analisa Dokumen:*\n\n{response.text}", parse_mode="Markdown")
        os.remove(nama_file)
    except Exception as e:
        bot.reply_to(message, "Gagal membaca dokumen.")
        logging.error(f"Error Doc: {e}")

# ==========================================
# CHAT HANDLER (Dengan Internet & Anti-429)
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
        
        # Logika Internet
        keywords = ["siapa", "berita", "terbaru", "harga", "info", "tadi malam", "hari ini"]
        if any(key in query.lower() for key in keywords):
            search_info = search_internet(query)
            final_prompt = f"User bertanya: {query}. \n\n{search_info}\n\nJawab berdasarkan info di atas."
        else:
            final_prompt = query
            
        response = user_chats[message.chat.id].send_message(final_prompt)
        bot.reply_to(message, response.text, parse_mode="Markdown")

    except Exception as e:
        if "429" in str(e): bot.reply_to(message, "Wah, kuota AI-ku sedang terpakai, tunggu 1 menit ya! 😅")
        else: bot.reply_to(message, "Server sibuk.")
        logging.error(f"Error Chat: {e}")

# ==========================================
# FUNGSI LAIN (Voice, Vision, Downloader)
# ==========================================
@bot.message_handler(content_types=['voice'])
def handle_voice_chat(message):
    # ... (Gunakan fungsi handle_voice_chat dari kode V9 sebelumnya)
    pass # Disini kamu bisa copy bagian handle_voice_chat sebelumnya

@bot.message_handler(commands=['download'])
def handle_download(message):
    # ... (Gunakan fungsi handle_download dari kode V9 sebelumnya)
    pass 

@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    # ... (Gunakan fungsi handle_vision dari kode V9 sebelumnya)
    pass

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
