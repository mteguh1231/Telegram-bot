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
            teks = "📰 *Top Berita:*\n\n" + "".join([f"{i}. [{item.find('title').text}]({item.find('link').text})\n\n" for i, item in enumerate(root.findall('./channel/item')[:5], 1)])
            bot.send_message(message.chat.id, teks, parse_mode="Markdown", disable_web_page_preview=True)
        except:
            bot.reply_to(message, "Gagal mengambil berita.")
    elif cmd == '/quote':
        try:
            data = requests.get("https://dummyjson.com/quotes/random").json()
            bot.reply_to(message, f"💡 *Quote:*\n\n_\"{data['quote']}\"_\n— *{data['author']}*", parse_mode="Markdown")
        except:
            bot.reply_to(message, "Error mengambil quote.")
    elif cmd == '/reset':
        if message.chat.id in user_chats: del user_chats[message.chat.id]
        bot.reply_to(message, "🧹 Memori obrolan dihapus!")

# ==========================================
# FITUR: Telinga AI (Mendengar Voice Note)
# ==========================================
@bot.message_handler(content_types=['voice'])
def handle_voice_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        nama_file_audio = f"vn_{message.chat.id}.ogg"
        with open(nama_file_audio, 'wb') as new_file:
            new_file.write(downloaded_file)
        audio_upload = ai_client.files.upload(file=nama_file_audio)
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        instruksi = "Tolong dengarkan dan balas pesan suara ini dalam bahasa Indonesia."
        response = user_chats[message.chat.id].send_message([audio_upload, instruksi])
        bot.reply_to(message, response.text, parse_mode="Markdown")
        os.remove(nama_file_audio)
    except Exception as e:
        bot.reply_to(message, "Maaf, telinga AI sedang berdengung.")
        logging.error(f"Error Voice Chat: {e}")

# ==========================================
# Sosmed Downloader
# ==========================================
@bot.message_handler(commands=['download'])
def handle_download(message):
    try:
        url = message.text.split(" ", 1)[1]
    except IndexError:
        bot.reply_to(message, "Format salah. Coba: `/download <link>`", parse_mode="Markdown")
        return
    msg_tunggu = bot.reply_to(message, "⏳ Sedang memproses video...")
    bot.send_chat_action(message.chat.id, 'upload_video')
    ydl_opts = {'format': 'best[filesize<50M]', 'outtmpl': f'video_{message.chat.id}.%(ext)s', 'quiet': True, 'noplaylist': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        with open(filename, 'rb') as video:
            bot.send_video(message.chat.id, video, caption="🎥 Berhasil diunduh!")
        os.remove(filename)
        bot.delete_message(message.chat.id, msg_tunggu.message_id)
    except Exception as e:
        bot.reply_to(message, "❌ Gagal! Video mungkin terlalu besar/diprivasi.")

# ==========================================
# Voice AI (Text to Speech)
# ==========================================
@bot.message_handler(commands=['suara'])
def handle_voice_ai(message):
    if not ai_client: return
    try:
        pertanyaan = message.text.split(" ", 1)[1]
    except:
        bot.reply_to(message, "Format: `/suara <pertanyaan>`", parse_mode="Markdown")
        return
    bot.send_chat_action(message.chat.id, 'record_voice')
    try:
        response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=f"Jawab singkat untuk suara: {pertanyaan}")
        tts = gTTS(text=response.text, lang='id')
        nama_file = f"suara_{message.chat.id}.ogg"
        tts.save(nama_file)
        with open(nama_file, 'rb') as vf:
            bot.send_voice(message.chat.id, vf, caption="🎙️")
        os.remove(nama_file)
    except:
        bot.reply_to(message, "Pita suara sedang serak.")

# ==========================================
# AI Vision & Chat Memori
# ==========================================
@bot.message_handler(content_types=['photo'])
def handle_vision(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        prompt = message.caption if message.caption else "Jelaskan gambar ini"
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
        bot.reply_to(message, ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, prompt]).text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "Gagal menganalisa gambar.")

@bot.message_handler(content_types=['text'])
def handle_chat(message):
    if not ai_client: return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        if message.chat.id not in user_chats:
            user_chats[message.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        bot.reply_to(message, user_chats[message.chat.id].send_message(message.text).text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "Server Google sedang sibuk.")

if __name__ == "__main__":
    logging.info("Bot Super V7 (AUDIO EDITION) berjalan...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
