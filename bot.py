import os
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
from google import genai # <--- Menggunakan library Google terbaru

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mengambil Token dari Environment Variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not BOT_TOKEN:
    logging.error("BOT_TOKEN tidak ditemukan!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

# Setup Google Gemini AI (VERSI TERBARU)
if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None
    logging.warning("GEMINI_API_KEY tidak ditemukan! Fitur AI tidak akan berfungsi.")

# ==========================================
# Command: /start & /help
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    teks = (
        f"Halo *{message.from_user.first_name}*! 👋\n\n"
        "Saya adalah bot multifungsi. Berikut adalah perintah yang bisa kamu gunakan:\n\n"
        "🤖 *Chat AI:* Langsung saja ketik pesanmu, saya akan membalas menggunakan AI!\n"
        "🌤️ */cuaca <nama_kota>* - Cek cuaca hari ini\n"
        "📰 */berita* - Baca 5 headline berita terbaru dari CNN\n"
        "💡 */quote* - Dapatkan kutipan motivasi acak"
    )
    bot.reply_to(message, teks, parse_mode="Markdown")

# ==========================================
# Command: /cuaca
# ==========================================
@bot.message_handler(commands=['cuaca'])
def cek_cuaca(message):
    try:
        kota = message.text.split(" ", 1)[1]
        url = f"https://wttr.in/{kota}?format=%l:+%c+%t\nKelembapan:+%h\nAngin:+%w"
        response = requests.get(url)
        
        if response.status_code == 200:
            bot.reply_to(message, f"🌤️ *Info Cuaca:*\n\n{response.text}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Maaf, cuaca untuk kota tersebut tidak ditemukan.")
    except IndexError:
        bot.reply_to(message, "Gunakan format yang benar:\nContoh: `/cuaca bandung`", parse_mode="Markdown")

# ==========================================
# Command: /berita
# ==========================================
@bot.message_handler(commands=['berita'])
def cek_berita(message):
    bot.reply_to(message, "⏳ Sedang mengambil berita terbaru dari CNN...")
    try:
        url = "http://rss.cnn.com/rss/edition.rss"
        response = requests.get(url)
        root = ET.fromstring(response.content)
        
        berita_teks = "📰 *Top Berita CNN Hari Ini:*\n\n"
        items = root.findall('./channel/item')[:5]
        for idx, item in enumerate(items, 1):
            title = item.find('title').text
            link = item.find('link').text
            berita_teks += f"{idx}. [{title}]({link})\n\n"
            
        bot.send_message(message.chat.id, berita_teks, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.send_message(message.chat.id, "Maaf, gagal mengambil berita saat ini.")

# ==========================================
# Command: /quote
# ==========================================
@bot.message_handler(commands=['quote'])
def cek_quote(message):
    try:
        url = "https://dummyjson.com/quotes/random"
        response = requests.get(url).json()
        quote = response['quote']
        author = response['author']
        bot.reply_to(message, f"💡 *Quote of the Day:*\n\n_\"{quote}\"_\n— *{author}*", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "Sedang kehabisan kata-kata. Coba lagi nanti!")

# ==========================================
# Chat AI (Format Terbaru Gemini 3.5 Flash)
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_ai_chat(message):
    if not ai_client:
        bot.reply_to(message, "Maaf, sistem AI sedang tidak aktif karena API Key belum dipasang.")
        return
        
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Menggunakan format pemanggilan API generasi baru
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash",
            contents=message.text
        )
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Maaf, saya sedang pusing memproses pertanyaanmu.")
        logging.error(f"Error AI: {e}")

# ==========================================
# Menjalankan Bot
# ==========================================
if __name__ == "__main__":
    logging.info("Bot Multifungsi V2 sedang berjalan...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
