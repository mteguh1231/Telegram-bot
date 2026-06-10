import os
import io
import logging
import random
import telebot
import requests
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL
from duckduckgo_search import DDGS
from supabase import create_client, Client

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

bot = telebot.TeleBot(BOT_TOKEN)

# Inisialisasi Klien AI
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

user_states = {}
user_chats = {} 

# --- Helpers ---
def handle_quota_error(bot, message, e):
    if "429" in str(e):
        bot.reply_to(message, "⚠️ *Maaf, kuota harian AI penuh.* Coba lagi besok ya!")
    else:
        bot.reply_to(message, f"Sedang ada gangguan teknis: {e}")

def show_main_menu(chat_id, text="Pilih menu di bawah:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💬 Chat"),
        types.KeyboardButton("🌍 Info"),
        types.KeyboardButton("🧰 Tools"),
        types.KeyboardButton("⚙️ Reset")
    )
    bot.send_message(chat_id, text, reply_markup=markup)

# --- Command /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = None
    welcome_text = (
        "✨ *Selamat Datang di BotPro Elite!*\n\n"
        "Asisten AI pribadi dengan sistem Hybrid (80% Gemini 2.5 Flash, 20% DeepSeek).\n\n"
        "🚀 *Kemampuan saya:*\n"
        "• 🤖 *AI Chat:* Analisis teks & jawaban cerdas.\n"
        "• 🌍 *Info:* Cuaca AI, Berita Real-Time, dan Quotes.\n"
        "• 🧰 *Tools:* Download video, analisis foto, ringkas dokumen.\n\n"
        "Gunakan tombol di bawah untuk mulai beraksi."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
    show_main_menu(message.chat.id, "Pilih kategori fitur:")

# --- Handle Navigasi Menu Utama ---
@bot.message_handler(func=lambda message: message.text in ["💬 Chat", "🌍 Info", "🧰 Tools", "⚙️ Reset"])
def handle_menu_click(message):
    user_id = message.chat.id
    user_states[user_id] = None
    
    if message.text == "💬 Chat":
        bot.reply_to(message, "💬 *Mode Chat AI Aktif*\nSilakan kirim pertanyaanmu!")
    elif message.text == "🌍 Info":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="state_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote"),
            types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_back")
        )
        bot.reply_to(message, "🌍 *Pilih Informasi:*", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "🧰 Tools":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Video", callback_data="state_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc"),
            types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_back")
        )
        bot.reply_to(message, "🧰 *Pusat Alat Media:*", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "⚙️ Reset":
        if user_id in user_chats:
            del user_chats[user_id]
        bot.reply_to(message, "⚙️ Sesi memori chat AI berhasil di-reset!")

# --- Callback Navigasi ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "cmd_back":
        bot.delete_message(user_id, call.message.message_id)
        show_main_menu(user_id, "Kembali ke Menu Utama.")
        
    elif call.data == "state_cuaca":
        user_states[user_id] = "awaiting_city"
        bot.edit_message_text("🌤️ Ketik nama kota untuk dicek cuacanya (contoh: Jakarta):", user_id, call.message.message_id)
        
    elif call.data == "state_download":
        user_states[user_id] = "awaiting_url"
        bot.edit_message_text("📥 Kirim link video:", user_id, call.message.message_id)
        
    elif call.data == "cmd_berita":
        bot.edit_message_text("📰 *Menggali berita terbaru...*", user_id, call.message.message_id, parse_mode="Markdown")
        try:
            # Mengambil 3 berita teratas dari internet
            results = DDGS().text("berita terkini indonesia hari ini", max_results=3)
            news_text = "📰 *Berita Utama Hari Ini:*\n\n"
            for idx, r in enumerate(results, 1):
                news_text += f"{idx}. *[{r['title']}]({r['href']})*\n_{r['body'][:100]}..._\n\n"
            bot.send_message(user_id, news_text, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(user_id, "Gagal mengambil berita saat ini.")
            
    elif call.data == "cmd_quote":
        try:
            res = requests.get("https://api.quotable.io/random").json()
            bot.send_message(user_id, f"💡 *Quote of the day:*\n\n_\"{res['content']}\"_\n- {res['author']}", parse_mode="Markdown")
        except:
            bot.send_message(user_id, "Gagal mengambil quote.")
            
    elif call.data == "media_vision": bot.reply_to(call.message, "📸 Kirim foto untuk dianalisis oleh AI.")
    elif call.data == "media_doc": bot.reply_to(call.message, "📄 Kirim file dokumen (.pdf/.txt) untuk diringkas.")

# --- Logic & Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all(message):
    user_id = message.chat.id
    state = user_states.get(user_id)

    # Logika Download Video
    if state == "awaiting_url" and message.text:
        bot.reply_to(message, "⏳ Sedang memproses download... Mohon tunggu.")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s'}
            with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(message.text, download=True)
            with open(f"vid.{info['ext']}", 'rb') as v: bot.send_video(user_id, v)
            os.remove(f"vid.{info['ext']}")
        except: bot.reply_to(message, "❌ Gagal. Link mungkin tidak didukung atau video terlalu besar.")
        user_states[user_id] = None
        
    # Logika Cuaca Canggih (Dengan Saran AI)
    elif state == "awaiting_city" and message.text:
        bot.reply_to(message, "🌤️ Mengecek kondisi cuaca dan menganalisis...")
        try:
            # Ambil data cuaca (Kondisi + Suhu + Kecepatan Angin)
            res = requests.get(f"https://wttr.in/{message.text}?format=Kondisi:+%C,+Suhu:+%t,+Angin:+%w")
            cuaca_mentah = res.text
            
            # Minta Gemini membuat saran berdasarkan cuaca tersebut
            prompt_saran = f"Cuaca di {message.text} saat ini: {cuaca_mentah}. Berikan 2 kalimat saran singkat (seperti rekomendasi pakaian atau aktivitas) dengan gaya asisten yang ramah."
            ai_saran = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt_saran).text
            
            hasil_akhir = f"📍 *Laporan Cuaca: {message.text.title()}*\n`{cuaca_mentah}`\n\n💡 *Saran AI:*\n{ai_saran}"
            bot.reply_to(message, hasil_akhir, parse_mode="Markdown")
        except: 
            bot.reply_to(message, "❌ Kota tidak ditemukan atau layanan cuaca sedang gangguan.")
        user_states[user_id] = None
        
    # Logika Analisis File / Foto
    elif message.content_type in ['document', 'photo']:
        bot.reply_to(message, "⏳ Mata AI sedang menganalisis file kamu...")
        try:
            if message.content_type == 'document':
                file_info = bot.get_file(message.document.file_id)
                nama = message.document.file_name
                with open(nama, 'wb') as f: f.write(bot.download_file(file_info.file_path))
                doc = ai_client.files.upload(file=nama)
                res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[doc, "Ringkas isi dokumen ini dengan detail."])
                bot.reply_to(message, res.text)
                os.remove(nama)
            else:
                file_info = bot.get_file(message.photo[-1].file_id)
                img = Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
                res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[img, "Jelaskan gambar ini dengan detail"])
                bot.reply_to(message, res.text)
        except Exception as e: handle_quota_error(bot, message, e)
        
    # Logika Chat AI Gacha (80% Gemini / 20% DeepSeek)
    elif message.text and not message.text.startswith('/'):
        try:
            chance = random.random()
            if chance > 0.8 and DEEPSEEK_API_KEY:
                bot.send_chat_action(user_id, 'typing')
                url = "https://api.deepseek.com/chat/completions"
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
                payload = {
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "Anda adalah asisten AI yang membantu. Jawablah dengan natural."},
                        {"role": "user", "content": message.text}
                    ]
                }
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    deepseek_reply = response.json()['choices'][0]['message']['content']
                    bot.reply_to(message, f"🐋 *DeepSeek:*\n{deepseek_reply}", parse_mode="Markdown")
                else:
                    bot.reply_to(message, "⚠️ Koneksi ke DeepSeek bermasalah.")
            else:
                bot.send_chat_action(user_id, 'typing')
                if user_id not in user_chats:
                    user_chats[user_id] = ai_client.chats.create(model="gemini-2.5-flash")
                res = user_chats[user_id].send_message(message.text)
                bot.reply_to(message, f"✨ *Gemini:*\n{res.text}", parse_mode="Markdown")
                
        except Exception as e: handle_quota_error(bot, message, e)

if __name__ == "__main__":
    bot.remove_webhook()
    print("🤖 BotPro Elite sedang berjalan...")
    bot.infinity_polling()
    
