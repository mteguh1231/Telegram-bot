import os
import io
import time
import logging
import requests
import zipfile
import threading

import telebot
from telebot import types
from PIL import Image
from groq import Groq

# --- Pengaman Import Library ---
try: from pdf2docx import Converter
except ImportError: Converter = None
try: import fitz
except ImportError: fitz = None
try: import pdfplumber; import pandas as pd
except ImportError: pdfplumber = None; pd = None
try: import cv2; import numpy as np
except ImportError: cv2 = None; np = None
try: import qrcode
except ImportError: qrcode = None
try: import yt_dlp 
except ImportError: yt_dlp = None

# --- Setup Konfigurasi Utama ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# ==========================================================================
# CONFIGURATION: DAFTAR MODEL AI GROQ
# ==========================================================================
TEXT_MODEL = "llama-3.3-70b-versatile"
chat_history = {} 
current_key_index = 0

# ==========================================================================
# FUNGSI ANIMASI LOADING BERGERAK
# ==========================================================================
class LoadingAnim:
    def __init__(self, chat_id, message_id, text="Memproses"):
        self.chat_id = chat_id
        self.message_id = message_id
        self.text = text
        self.running = True
        self.thread = threading.Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()

    def _animate(self):
        frames = ["⏳", "⌛", "🔄", "🔃", "🚀"]
        idx = 0
        while self.running:
            try:
                frame = frames[idx % len(frames)]
                bot.edit_message_text(f"{frame} *{self.text}...*", self.chat_id, self.message_id, parse_mode="Markdown")
                idx += 1
            except: 
                pass 
            for _ in range(20): 
                if not self.running: break
                time.sleep(0.1)

    def update_text(self, new_text):
        self.text = new_text

    def stop(self):
        self.running = False

# ==========================================================================
# FUNGSI AI CHAT
# ==========================================================================
def get_ai_response(chat_id, prompt):
    global current_key_index, chat_history
    raw_keys = os.getenv('GROQ_KEYS') or os.getenv('GROQ_KEY', '')
    API_KEYS = [k.strip().strip('"').strip("'") for k in raw_keys.split(',')] if raw_keys else []
    API_KEYS = [k for k in API_KEYS if k]
    if not API_KEYS: return "❌ Variabel 'GROQ_KEYS' belum diisi di server."
        
    attempts = 0
    while attempts < len(API_KEYS):
        active_key = API_KEYS[current_key_index % len(API_KEYS)]
        try:
            temp_client = Groq(api_key=active_key)
            if chat_id not in chat_history:
                chat_history[chat_id] = [{"role": "system", "content": "Kamu adalah asisten AI yang ramah, pintar, dan menggunakan bahasa Indonesia yang santai."}]
            
            chat_history[chat_id].append({"role": "user", "content": prompt})
            if len(chat_history[chat_id]) > 11:
                chat_history[chat_id] = [chat_history[chat_id][0]] + chat_history[chat_id][-10:]
            
            response = temp_client.chat.completions.create(model=TEXT_MODEL, messages=chat_history[chat_id])
            bot_reply = response.choices[0].message.content
            chat_history[chat_id].append({"role": "assistant", "content": bot_reply})
            return bot_reply
            
        except Exception as e:
            current_key_index += 1
            attempts += 1
    return "❌ Waduh, API Key Groq sedang sibuk/limit! Coba lagi nanti."

# ==========================================================================
# MENU & HANDLERS
# ==========================================================================
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💬 Chat AI", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools", "🧹 Hapus Memori Chat")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m): send_main_menu(m.chat.id, "✨ *Sistem Siap Digunakan!*")

@bot.message_handler(commands=['clear', 'hapus'])
def clear_command(m):
    global chat_history
    if m.chat.id in chat_history: del chat_history[m.chat.id]
    user_states[m.chat.id] = "chat"
    bot.reply_to(m, "🧹 *Memori chat berhasil dihapus!*", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools", "🧹 Hapus Memori Chat"])
def menu(m):
    if m.text == "💬 Chat AI": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat AI Aktif.*", parse_mode="Markdown")
    
    elif m.text == "🧹 Hapus Memori Chat":
        global chat_history
        if m.chat.id in chat_history: del chat_history[m.chat.id]
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "🧹 *Memori dibersihkan!*", parse_mode="Markdown")

    elif m.text == "📥 Downloader":
        user_states[m.chat.id] = "downloader_menu"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔺 YouTube Video", callback_data="dl_yt"),
            types.InlineKeyboardButton("⚫ TikTok Video", callback_data="dl_tt"),
            types.InlineKeyboardButton("📸 Instagram Reel", callback_data="dl_ig"),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
        )
        bot.reply_to(m, "📥 *Pilih platform:*", reply_markup=markup, parse_mode="Markdown")
        
    elif m.text == "📁 Convert File": 
        user_states[m.chat.id] = "convert_menu"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📄 PDF ke Word", callback_data="set_pdf2word"),
            types.InlineKeyboardButton("📝 Word ke PDF", callback_data="set_word2pdf"),
            types.InlineKeyboardButton("🖼️ Gambar ke JPG", callback_data="set_any2jpg"),
            types.InlineKeyboardButton("📄➡️🖼️ PDF ke JPG", callback_data="set_pdf2jpg"),
            types.InlineKeyboardButton("🖼️➡️📄 JPG ke PDF", callback_data="set_jpg2pdf"),
            types.InlineKeyboardButton("📊 PDF ke Excel", callback_data="set_pdf2excel"),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
        )
        bot.reply_to(m, "📁 *Pilih metode:*", reply_markup=markup, parse_mode="Markdown")

    elif m.text == "🛠️ Utility Tools":
        user_states[m.chat.id] = "utility_menu"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🪄 Hapus Background", callback_data="set_rmbg"),
            types.InlineKeyboardButton("🗜️ Kompresi File", callback_data="set_compress"),
            types.InlineKeyboardButton("🔳 Buat QR Code", callback_data="set_qr_gen"),
            types.InlineKeyboardButton("🔍 Baca QR Code", callback_data="set_qr_read"),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
        )
        bot.reply_to(m, "🛠️ *Pilih Tools:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    if call.data == "back_to_main":
        user_states[cid] = "chat"
        bot.delete_message(cid, mid)
        send_main_menu(cid, text="🔙 *Kembali ke Menu Utama.*")
        return
    if call.data in ["dl_yt", "dl_tt", "dl_ig"]:
        platform = {"dl_yt": "YouTube", "dl_tt": "TikTok", "dl_ig": "Instagram"}[call.data]
        user_states[cid] = call.data
        bot.edit_message_text(f"📥 *Unduh {platform}*\nKirimkan linknya!", cid, mid, parse_mode="Markdown")
        return
    if call.data in ["set_pdf2word", "set_word2pdf", "set_any2jpg", "set_jpg2pdf", "set_pdf2jpg", "set_pdf2excel"]:
        user_states[cid] = call.data
        bot.edit_message_text(f"📁 *Mode Konversi*\nKirimkan filenya!", cid, mid, parse_mode="Markdown")
        return
    if call.data in ["set_rmbg", "set_compress", "set_qr_gen", "set_qr_read"]:
        user_states[cid] = call.data
        msg = "🔳 *Kirim Teks/Link*" if call.data == "set_qr_gen" else "🛠️ *Kirim foto/file*"
        bot.edit_message_text(msg, cid, mid, parse_mode="Markdown")
        return

@bot.message_handler(content_types=['document', 'photo'])
def handle_files(m):
    state = user_states.get(m.chat.id, "chat")
    file_id = m.document.file_id if m.document else m.photo[-1].file_id
    file_name = m.document.file_name if m.document else "image.jpg"

    if state == "set_rmbg":
        loading_msg = bot.reply_to(m, "🪄 *Menyiapkan gambar...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Menghapus background")
        try:
            API_KEY = os.getenv('REMOVE_BG_KEY')
            if not API_KEY:
                anim.stop()
                bot.edit_message_text("❌ *Gagal:* Variabel `REMOVE_BG_KEY` belum disetting di Server!", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                return

            file_path = bot.get_file(file_id).file_path
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                data={'image_url': file_url, 'size': 'auto'},
                headers={'X-Api-Key': API_KEY},
            )
            anim.stop()
            
            if response.status_code == requests.codes.ok:
                out_io = io.BytesIO(response.content)
                bot.send_document(m.chat.id, out_io, visible_file_name="nobg_result.png", caption="✨ Selesai!")
                bot.delete_message(m.chat.id, loading_msg.message_id)
            else:
                bot.edit_message_text(f"❌ *Gagal:* Pastikan API Key valid.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
        except Exception as e: 
            anim.stop()
            bot.edit_message_text(f"❌ Error: {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_qr_read":
        loading_msg = bot.reply_to(m, "🔍 *Mendeteksi QR...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            np_arr = np.frombuffer(img_data, np.uint8)
            img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(img_cv)
            if data: bot.edit_message_text(f"✅ *Isi QR:* `{data}`", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            else: bot.edit_message_text("❌ *Gagal mendeteksi.*", m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ Error: {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_compress":
        loading_msg = bot.reply_to(m, "🗜️ *Menyiapkan kompresi...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Mengkompresi file")
        try:
            file_path = bot.get_file(file_id).file_path
            file_data = bot.download_file(file_path)
            out_io = io.BytesIO()
            if m.photo or file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                img = Image.open(io.BytesIO(file_data)).convert('RGB')
                img.save(out_io, format="JPEG", optimize=True, quality=60)
                ext = "jpg"
            else:
                with zipfile.ZipFile(out_io, 'w', zipfile.ZIP_DEFLATED) as zipf: zipf.writestr(file_name, file_data)
                ext = "zip"
            out_io.seek(0)
            anim.stop()
            bot.send_document(m.chat.id, out_io, visible_file_name=f"compressed.{ext}", caption="✨ Selesai!")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: 
            anim.stop()
            bot.edit_message_text(f"❌ Error: {str(e)}", m.chat.id, loading_msg.message_id)


@bot.message_handler(content_types=['text'])
def handle_text(m):
    state = user_states.get(m.chat.id, "chat")
    
    if state == "set_qr_gen":
        try:
            img = qrcode.make(m.text)
            out_io = io.BytesIO()
            img.save(out_io, format="PNG")
            out_io.seek(0)
            bot.send_photo(m.chat.id, out_io, caption=f"✨ *QR Code Selesai!*")
        except Exception as e: bot.reply_to(m, f"❌ *Error:* {str(e)}")
        return

    # === MESIN DOWNLOADER YT-DLP + COOKIES + FFMPEG ===
    elif state in ["dl_yt", "dl_tt", "dl_ig"]:
        if yt_dlp is None:
            bot.reply_to(m, "❌ *System Error:* Library `yt-dlp` belum terinstal!", parse_mode="Markdown")
            return
            
        loading_msg = bot.reply_to(m, "⏳ *Menerima link...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Menyiapkan mesin pengunduh")
        temp_filename = f"vid_{m.chat.id}_{int(time.time())}.mp4"
        
        try:
            url = m.text.strip()
            if url.startswith("Https://"): url = url.replace("Https://", "https://")
            elif url.startswith("Http://"): url = url.replace("Http://", "http://")
            if "?si=" in url: url = url.split("?si=")[0]
            if "&si=" in url: url = url.split("&si=")[0]
            
            downloaded_file = None

            # 1. TIKTOK (TikWM)
            if "tiktok.com" in url or "vt.tiktok" in url:
                anim.update_text("Menyedot video TikTok")
                res = requests.get(f"https://www.tikwm.com/api/?url={url}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                video_link = res.get('data', {}).get('play')
                if video_link:
                    with requests.get(video_link, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        with open(temp_filename, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                    downloaded_file = temp_filename

            # 2. YOUTUBE & INSTAGRAM
            else:
                anim.update_text("Mengekstrak video (Dibantu FFmpeg)")
                
                # INI KUNCINYA: format disetting agar mencari gabungan DULU, kalau gagal baru ambil terpisah
                ydl_opts = {
                    'outtmpl': temp_filename,
                    'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                if os.path.exists('cookies.txt'):
                    ydl_opts['cookiefile'] = 'cookies.txt'

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                if os.path.exists(temp_filename):
                    downloaded_file = temp_filename

            # --- KIRIM VIDEO KE TELEGRAM ---
            if downloaded_file and os.path.exists(downloaded_file):
                file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
                
                if file_size_mb > 49.5:
                    anim.stop()
                    bot.edit_message_text(f"❌ *Gagal:* Ukuran video terlalu besar (*{file_size_mb:.1f} MB*). Maksimal 50 MB.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                    os.remove(downloaded_file)
                else:
                    anim.update_text(f"Mengirim video ({file_size_mb:.1f} MB)")
                    with open(downloaded_file, 'rb') as f:
                        bot.send_video(m.chat.id, f, caption="✨ *Selesai!*", parse_mode="Markdown", timeout=120)
                    os.remove(downloaded_file)
                    anim.stop() 
                    bot.delete_message(m.chat.id, loading_msg.message_id)
            else:
                anim.stop()
                bot.edit_message_text("❌ *Gagal:* Video tidak ditemukan atau diprivate.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

        except Exception as e: 
            anim.stop()
            bot.edit_message_text(f"❌ *Gagal mengunduh!*\n\n`Detail Error: {str(e)[:150]}...`", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            if os.path.exists(temp_filename):
                try: os.remove(temp_filename)
                except: pass
        return

    # === BAGIAN AI CHAT ===
    elif state == "chat":
        loading_msg = bot.reply_to(m, "💭 *AI sedang berpikir...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Mengetik balasan")
        try:
            reply_text = get_ai_response(m.chat.id, m.text)
            anim.stop()
            try:
                bot.edit_message_text(reply_text, m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Telegram menolak Markdown: {e}")
                bot.edit_message_text(reply_text, m.chat.id, loading_msg.message_id)
        except Exception as e: 
            anim.stop()
            bot.edit_message_text(f"❌ *Sistem AI Error:* {str(e)[:100]}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

if __name__ == "__main__": 
    bot.infinity_polling()
    
