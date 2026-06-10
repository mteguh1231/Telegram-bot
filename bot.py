import os
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mengambil Token dari Environment Variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not BOT_TOKEN:
    logging.error("BOT_TOKEN tidak ditemukan!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

# Setup Google Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Menggunakan model Gemini terbaru
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None
    logging.warning("GEMINI_API_KEY tidak ditemukan! Fitur AI tidak akan berfungsi.")

# ==========================================
# 1. Command: /start & /help
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
# 2. Command: /cuaca (Menggunakan wttr.in tanpa API Key)
# ==========================================
@bot.message_handler(commands=['cuaca'])
def cek_cuaca(message):
    try:
        # Mengambil nama kota dari pesan, misalnya: /cuaca jakarta
        kota = message.text.split(" ", 1)[1]
        
        # Mengambil data dari layanan wttr.in
        url = f"https://wttr.in/{kota}?format=%l:+%c+%t\nKelembapan:+%h\nAngin:+%w"
        response = requests.get(url)
        
        if response.status_code == 200:
            bot.reply_to(message, f"🌤️ *Info Cuaca:*\n\n{response.text}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Maaf, cuaca untuk kota tersebut tidak ditemukan.")
    except IndexError:
        bot.reply_to(message, "Gunakan format yang benar:\nContoh: `/cuaca bandung`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Terjadi kesalahan saat mengambil data cuaca.")
        logging.error(f"Error cuaca: {e}")

# ==========================================
# 3. Command: /berita (Mengambil RSS CNN)
# ==========================================
@bot.message_handler(commands=['berita'])
def cek_berita(message):
    bot.reply_to(message, "⏳ Sedang mengambil berita terbaru dari CNN...")
    try:
        # URL RSS Feed CNN Internasional
        url = "http://rss.cnn.com/rss/edition.rss"
        response = requests.get(url)
        root = ET.fromstring(response.content)
        
        berita_teks = "📰 *Top Berita CNN Hari Ini:*\n\n"
        
        # Mengambil 5 berita pertama
        items = root.findall('./channel/item')[:5]
        for idx, item in enumerate(items, 1):
            title = item.find('title').text
            link = item.find('link').text
            berita_teks += f"{idx}. [{title}]({link})\n\n"
            
        bot.send_message(message.chat.id, berita_teks, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.send_message(message.chat.id, "Maaf, gagal mengambil berita saat ini.")
        logging.error(f"Error berita: {e}")

# ==========================================
# 4. Command: /quote (Kutipan Acak)
# ==========================================
@bot.message_handler(commands=['quote'])
def cek_quote(message):
    try:
        url = "https://dummyjson.com/quotes/random"
        response = requests.get(url).json()
        quote = response['quote']
        author = response['author']
        
        teks = f"💡 *Quote of the Day:*\n\n_\"{quote}\"_\n— *{author}*"
        bot.reply_to(message, teks, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Sedang kehabisan kata-kata. Coba lagi nanti!")

# ==========================================
# 5. Chat AI (Menangani Semua Pesan Teks Biasa)
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_ai_chat(message):
    if not ai_model:
        bot.reply_to(message, "Maaf, sistem AI sedang tidak aktif karena API Key belum dipasang.")
        return
        
    # Memberikan efek "typing..." di Telegram
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Mengirim teks pengguna ke Google Gemini
        response = ai_model.generate_content(message.text)
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Maaf, saya sedang pusing memproses pertanyaanmu (terjadi error pada sistem AI).")
        logging.error(f"Error AI: {e}")

# ==========================================
# Menjalankan Bot
# ==========================================
if __name__ == "__main__":
    logging.info("Bot Multifungsi sedang berjalan...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logging.error(f"Bot berhenti: {e}")
        
