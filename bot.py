import os
import io
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
from PIL import Image
from google import genai
from gtts import gTTS
from yt_dlp import YoutubeDL

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not BOT_TOKEN:
    logging.error("BOT_TOKEN tidak ditemukan!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)
user_chats = {}

if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None

# ==========================================
# Command Dasar
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    teks = (
        f"Halo *{message.from_user.first_name}*! 👋\n\n"
        "Saya adalah bot AI Super V7 (Audio Edition). Perintah:\n\n"
        "🤖 *Chat Teks:* Ngobrol biasa (punya memori)\n"
        "👂 *Voice Chat:* Kirim Voice Note (VN), saya bisa dengar!\n"
        "🗣️ */suara <tanya>:* AI membalas pakai Voice Note\n"
        "📥 */download <link>:* Unduh video (YT/TikTok)\n"
        "👁️ *Vision:* Kirim foto untuk dianalisa AI\n"
        "🌤️ */cuaca <kota>* - Info cuaca\n"
        "📰 */berita* - Berita CNN\n"
        "💡 */quote* - Quote acak\n"
        "🧹 */reset* - Hapus memori"
    )
    bot.reply_to(message, teks, parse_mode="Markdown")

@bot.message_handler(commands=['cuaca', 'berita', 'quote', 'reset'])
def handle_basic_commands(message):
    cmd = message.text.split()[0]
    if cmd == '/cuaca':
        try:
            kota = message.text.split(" ", 1)[1]
            response = requests.get(f"https://wttr.in/{kota}?format=%l:+%c+%t\nKelembapan:+%h\nAngin:+%w")
            bot.reply_to(message, f"🌤️ *Info Cuaca:*\n\n{response.text}" if response.status_code == 200 else "Cuaca kota tidak ditemukan.", parse_mode="Markdown")
        except:
            bot.reply_to(message, "Format: `/cuaca bandung`", parse_mode="Markdown")
    elif cmd == '/berita':
        bot.reply_to(message, "⏳ Mengambil berita...")
        try:
            root = ET.fromstring(requests.get("http://rss.cnn.com/rss/edition.rss").content)
            teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. [{item.find('title').text}]({item.find('link').text})\n\n
            
