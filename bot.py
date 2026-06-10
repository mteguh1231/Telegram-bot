import os
import io
import logging
import telebot
import requests
import xml.etree.ElementTree as ET
from PIL import Image
from google import genai
from google.genai import types
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
        "Saya adalah bot AI Super V6. Perintah yang tersedia:\n\n"
        "🤖 *Chat:* Ngobrol biasa (punya memori)\n"
        "🗣️ */suara <tanya>:* Dibalas pakai Voice Note\n"
        "🎨 */gambar <teks>:* AI Pembuat Gambar\n"
        "📥 */download <link>:* Unduh video (YT/TikTok)\n"
        "👁️ *Vision:* Kirim foto untuk dianalisa AI\n"
        "🌤️ */cuaca <kota>* - Info cuaca\n"
        "📰 */berita* - Berita CNN\n"
        "💡 */quote* - Quote acak\n"
        "🧹 */reset* - Hapus memori obrolan"
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
# FITUR BARU 5: AI Image Generator (Native Google Gemini)
# ==========================================
@bot.message_handler(commands=['gambar'])
def handle_image_generation(message):
    if not ai_client:
        bot.reply_to(message, "API Key belum terpasang.")
        return

    try:
        prompt = message.text.split(" ", 1)[1]
    except IndexError:
        bot.reply_to(message, "Format salah.\nContoh: `/gambar kucing pakai kacamata hitam di pantai`", parse_mode="Markdown")
        return

    bot.send_chat_action(message.chat.id, 'upload_photo')
    msg_tunggu = bot.reply_to(message, "🎨 Sedang melukis gambar dengan otak Gemini... Mohon tunggu sebentar.")
    
    try:
        # Memerintahkan Gemini untuk merespons dengan format GAMBAR
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        
        gambar_ditemukan = False
        for part in response.parts:
            if part.inline_data:
                # Mengambil file gambar dari Google
                pil_image = part.as_image()
                
                # Mengubahnya menjadi format file untuk Telegram
                bio = io.BytesIO()
                pil_image.save(bio, format="JPEG")
                bio.seek(0)
                
                bot.send_photo(message.chat.id, bio, caption=f"🎨 Hasil dari: *{prompt}*", parse_mode="Markdown")
                gambar_ditemukan = True
                break
                
        if not gambar_ditemukan:
            bot.reply_to(message, "Maaf, gambar gagal dibuat (mungkin ditolak oleh filter keamanan Google).")
            
        bot.delete_message(message.chat.id, msg_tunggu.message_id)
        
    except Exception as e:
        bot.reply_to(message, "Maaf, server gambar Google sedang sibuk atau menolak.")
        logging.error(f"Error Image Gen: {e}")
        
        
        

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

    ydl_opts = {
        'format': 'best[filesize<50M]',
        'outtmpl': f'video_{message.chat.id}.%(ext)s',
        'quiet': True,
        'noplaylist': True
    }

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
        response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=f"Jawab singkat (maks 2 paragraf) untuk suara: {pertanyaan}")
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
    logging.info("Bot Super V6 (IMAGE GEN) berjalan...")
    
    # Membersihkan sisa koneksi agar tidak tabrakan (Bypass Error 409)
    bot.remove_webhook()
    
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

        
