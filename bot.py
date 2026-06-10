import os
import io
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
from PIL import Image
from google import genai
from gtts import gTTS # <--- Library Pita Suara Baru

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not BOT_TOKEN:
    logging.error("BOT_TOKEN tidak ditemukan!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

# Inisialisasi AI & Memori
user_chats = {}

if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None
    logging.warning("GEMINI_API_KEY tidak ditemukan!")

# ==========================================
# Command Dasar
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    teks = (
        f"Halo *{message.from_user.first_name}*! 👋\n\n"
        "Saya adalah bot AI Super V4. Perintah yang tersedia:\n\n"
        "🤖 *Chat Teks:* Ngobrol biasa (punya memori)\n"
        "🗣️ */suara <tanya>:* AI membalas pakai Voice Note\n"
        "👁️ *Vision:* Kirim foto + caption untuk dianalisa\n"
        "🌤️ */cuaca <kota>* - Info cuaca\n"
        "📰 */berita* - Berita CNN\n"
        "💡 */quote* - Quote acak\n"
        "🧹 */reset* - Hapus memori"
    )
    bot.reply_to(message, teks, parse_mode="Markdown")

@bot.message_handler(commands=['cuaca'])
def cek_cuaca(message):
    try:
        kota = message.text.split(" ", 1)[1]
        url = f"https://wttr.in/{kota}?format=%l:+%c+%t\nKelembapan:+%h\nAngin:+%w"
        response = requests.get(url)
        if response.status_code == 200:
            bot.reply_to(message, f"🌤️ *Info Cuaca:*\n\n{response.text}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Cuaca kota tersebut tidak ditemukan.")
    except IndexError:
        bot.reply_to(message, "Format: `/cuaca bandung`", parse_mode="Markdown")

@bot.message_handler(commands=['berita'])
def cek_berita(message):
    bot.reply_to(message, "⏳ Mengambil berita CNN...")
    try:
        url = "http://rss.cnn.com/rss/edition.rss"
        response = requests.get(url)
        root = ET.fromstring(response.content)
        berita_teks = "📰 *Top Berita CNN:*\n\n"
        for idx, item in enumerate(root.findall('./channel/item')[:5], 1):
            berita_teks += f"{idx}. [{item.find('title').text}]({item.find('link').text})\n\n"
        bot.send_message(message.chat.id, berita_teks, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception:
        bot.send_message(message.chat.id, "Gagal mengambil berita.")

@bot.message_handler(commands=['quote'])
def cek_quote(message):
    try:
        data = requests.get("https://dummyjson.com/quotes/random").json()
        bot.reply_to(message, f"💡 *Quote:*\n\n_\"{data['quote']}\"_\n— *{data['author']}*", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "Sedang kehabisan kata-kata.")

@bot.message_handler(commands=['reset'])
def reset_memory(message):
    user_id = message.chat.id
    if user_id in user_chats:
        del user_chats[user_id]
    bot.reply_to(message, "🧹 Memori obrolan kita sudah dihapus. Mari mulai dari awal!")

# ==========================================
# FITUR BARU 3: Voice Note AI (Text-to-Speech)
# ==========================================
@bot.message_handler(commands=['suara'])
def handle_voice_ai(message):
    if not ai_client:
        bot.reply_to(message, "Sistem AI belum aktif.")
        return

    try:
        # Mengambil pertanyaan setelah kata /suara
        pertanyaan = message.text.split(" ", 1)[1]
    except IndexError:
        bot.reply_to(message, "Format salah. Coba ketik:\n`/suara Ceritakan dongeng kancil singkat`", parse_mode="Markdown")
        return

    # Memberi efek di Telegram bahwa bot sedang "Merekam Suara"
    bot.send_chat_action(message.chat.id, 'record_voice')
    
    try:
        # Dapatkan teks jawaban dari AI
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Jawab dengan singkat dan padat (maksimal 3 paragraf) untuk diubah menjadi suara: {pertanyaan}"
        )
        jawaban_teks = response.text

        # Proses mengubah teks menjadi file suara (Bahasa Indonesia)
        tts = gTTS(text=jawaban_teks, lang='id')
        nama_file = f"suara_{message.chat.id}.ogg"
        tts.save(nama_file)

        # Kirim voice note ke pengguna
        with open(nama_file, 'rb') as voice_file:
            bot.send_voice(message.chat.id, voice_file, caption="🎙️ Jawaban AI")
            
        # Hapus file suara dari server agar tidak membuat server penuh
        os.remove(nama_file)
        
    except Exception as e:
        bot.reply_to(message, "Maaf, pita suara saya sedang serak. Terjadi kesalahan.")
        logging.error(f"Error Voice AI: {e}")

# ==========================================
# AI Vision (Menangani Gambar/Foto)
# ==========================================
@bot.message_handler(content_types=['photo'])
def handle_ai_vision(message):
    if not ai_client:
        return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        prompt = message.caption if message.caption else "Jelaskan gambar ini"
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded_file))
        response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, prompt])
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Maaf, gagal menganalisa gambar.")

# ==========================================
# Chat AI dengan Memori
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_ai_chat(message):
    user_id = message.chat.id
    if not ai_client:
        return
    bot.send_chat_action(user_id, 'typing')
    try:
        if user_id not in user_chats:
            user_chats[user_id] = ai_client.chats.create(model="gemini-2.5-flash")
        response = user_chats[user_id].send_message(message.text)
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Server Google sedang sibuk, mohon tunggu sebentar.")

# ==========================================
# Eksekusi Utama
# ==========================================
if __name__ == "__main__":
    logging.info("Bot Super V4 berjalan...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
