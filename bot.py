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
# FUNGSI ANIMASI LOADING BERGERAK (THREADING)
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
        frames = ["⏳", "⌛", "🔄", "🔃"]
        idx = 0
        while self.running:
            try:
                frame = frames[idx % len(frames)]
                bot.edit_message_text(f"{frame} *{self.text}...*", self.chat_id, self.message_id, parse_mode="Markdown")
                idx += 1
            except: 
                pass 
            
            for _ in range(15): 
                if not self.running: break
                time.sleep(0.1)

    def stop(self):
        self.running = False

# ==========================================================================
# FUNGSI AI CHAT & DOWNLOADER
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

def download_media_via_api(url):
    # --- SISTEM PEMBERSIH LINK OTOMATIS ---
    url = url.strip()
    if url.startswith("Https://"): url = url.replace("Https://", "https://")
    elif url.startswith("Http://"): url = url.replace("Http://", "http://")
    
    if "?si=" in url: url = url.split("?si=")[0]
    if "&si=" in url: url = url.split("&si=")[0]
    if "instagram.com" in url and "?" in url: url = url.split("?")[0]
    if "tiktok.com" in url and "?" in url: url = url.split("?")[0]
    
    if "youtube.com" in url or "youtu.be" in url:
        vid_id = None
        if "youtu.be/" in url: vid_id = url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/shorts/" in url: vid_id = url.split("youtube.com/shorts/")[1].split("?")[0]
        elif "youtube.com/watch?v=" in url: vid_id = url.split("youtube.com/watch?v=")[1].split("&")[0]
        if vid_id: url = f"https://youtu.be/{vid_id}"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"}

    # 1. Khusus TikTok
    if "tiktok.com" in url or "vt.tiktok" in url:
        try: return requests.get(f"https://www.tikwm.com/api/?url={url}", headers=headers, timeout=10).json().get('data', {}).get('play')
        except: pass

    # --- FUNGSI PELACAK LINK OTOMATIS DALAM JSON ---
    def extract_vid_url(data):
        if isinstance(data, dict):
            # Cari kunci yang biasa dipakai untuk nyimpen link video MP4
            for key in ['url', 'dl', 'link', 'video', 'media', 'play']:
                if key in data and isinstance(data[key], str) and data[key].startswith('http') and not data[key].endswith('.jpg'):
                    return data[key]
            for k, v in data.items():
                res = extract_vid_url(v)
                if res: return res
        elif isinstance(data, list) and len(data) > 0:
            return extract_vid_url(data[0])
        return None

    # 2. Khusus YouTube (Mode Serbu 4 API)
    if "youtu.be" in url or "youtube.com" in url:
        yt_apis = [
            f"https://api.siputzx.my.id/api/d/ytmp4?url={url}",
            f"https://api.ryzendesu.vip/api/downloader/ytmp4?url={url}",
            f"https://api.agatz.my.id/api/ytmp4?url={url}",
            f"https://api.vreden.my.id/api/ytmp4?url={url}"
        ]
        for api_url in yt_apis:
            try:
                res = requests.get(api_url, headers=headers, timeout=10).json()
                vid_link = extract_vid_url(res)
                if vid_link: return vid_link
            except: continue

    # 3. Khusus Instagram (Mode Serbu 4 API)
    if "instagram.com" in url:
        ig_apis = [
            f"https://api.siputzx.my.id/api/d/igdl?url={url}",
            f"https://api.ryzendesu.vip/api/downloader/igdl?url={url}",
            f"https://api.agatz.my.id/api/igdl?url={url}",
            f"https://api.vreden.my.id/api/igdownload?url={url}"
def download_media_via_api(url):
    # --- SISTEM PEMBERSIH LINK OTOMATIS ---
    url = url.strip()
    if url.startswith("Https://"): url = url.replace("Https://", "https://")
    elif url.startswith("Http://"): url = url.replace("Http://", "http://")
    
    if "?si=" in url: url = url.split("?si=")[0]
    if "&si=" in url: url = url.split("&si=")[0]
    if "instagram.com" in url and "?" in url: url = url.split("?")[0]
    if "tiktok.com" in url and "?" in url: url = url.split("?")[0]
    
    if "youtube.com" in url or "youtu.be" in url:
        vid_id = None
        if "youtu.be/" in url: vid_id = url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/shorts/" in url: vid_id = url.split("youtube.com/shorts/")[1].split("?")[0]
        elif "youtube.com/watch?v=" in url: vid_id = url.split("youtube.com/watch?v=")[1].split("&")[0]
        if vid_id: url = f"https://youtu.be/{vid_id}"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"}

    # 1. Khusus TikTok (TikWM - Terbukti Stabil)
    if "tiktok.com" in url or "vt.tiktok" in url:
        try: return requests.get(f"https://www.tikwm.com/api/?url={url}", headers=headers, timeout=10).json().get('data', {}).get('play')
        except: pass

    # --- FUNGSI PELACAK LINK MP4 CERDAS ---
    def extract_vid_url(data):
        if isinstance(data, dict):
            for key in ['url', 'dl', 'link', 'video', 'media', 'play', 'mp4']:
                if key in data and isinstance(data[key], str) and data[key].startswith('http') and not data[key].endswith('.jpg'):
                    return data[key]
            for k, v in data.items():
                res = extract_vid_url(v)
                if res: return res
        elif isinstance(data, list) and len(data) > 0:
            return extract_vid_url(data[0])
        return None

    # 2. Khusus YouTube (Mode Serbu 4 API Tangguh)
    if "youtu.be" in url or "youtube.com" in url:
        yt_apis = [
            f"https://widipe.com/download/ytdl?url={url}",       # API Utama 1
            f"https://api.btch.info/download/ytdl?url={url}",    # API Utama 2
            f"https://api.siputzx.my.id/api/d/ytmp4?url={url}",  # Cadangan 1
            f"https://api.ryzendesu.vip/api/downloader/ytmp4?url={url}" # Cadangan 2
        ]
        for api_url in yt_apis:
            try:
                res = requests.get(api_url, headers=headers, timeout=10).json()
                vid_link = extract_vid_url(res)
                if vid_link: return vid_link
            except: continue

    # 3. Khusus Instagram (Mode Serbu 4 API Tangguh)
    if "instagram.com" in url:
        ig_apis = [
            f"https://widipe.com/download/igdl?url={url}",       # API Utama 1
            f"https://api.btch.info/download/igdl?url={url}",    # API Utama 2
            f"https://api.siputzx.my.id/api/d/igdl?url={url}",   # Cadangan 1
            f"https://api.ryzendesu.vip/api/downloader/igdl?url={url}"  # Cadangan 2
        ]
        for api_url in ig_apis:
            try:
                res = requests.get(api_url, headers=headers, timeout=10).json()
                vid_link = extract_vid_url(res)
                if vid_link: return vid_link
            except: continue

    # 4. Sapu Jagat Terakhir (Jaringan Cobalt Server Komunitas)
    cobalt_instances = [
        "https://cobalt.q-n.space/api/json",
        "https://co.wuk.sh/api/json",
        "https://api.cobalt.tools/"
    ]
    for cob in cobalt_instances:
        try:
            cobalt_headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": headers["User-Agent"]}
            res = requests.post(cob, json={"url": url}, headers=cobalt_headers, timeout=15)
            if res.status_code in [200, 201]:
                data = res.json()
                if data.get("status") in ["stream", "redirect"]: return data.get("url")
                elif data.get("status") == "picker": return data["picker"][0]["url"]
                elif data.get("url"): return data.get("url")
        except: continue
    
    return None
    
    

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
                bot.edit_message_text("❌ *Gagal:* Variabel `REMOVE_BG_KEY` belum disetting di Variables Server!", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
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
                bot.edit_message_text(f"❌ *Gagal:* Pastikan API Key valid atau kuota Remove.bg masih ada.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
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

    elif state in ["dl_yt", "dl_tt", "dl_ig"]:
        loading_msg = bot.reply_to(m, "⏳ *Menerima link...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Membongkar link dari server")
        try:
            video_link = download_media_via_api(m.text)
            
            if video_link:
                anim.text = "Mengirim video ke Telegram"
                
                temp_filename = f"vid_{m.chat.id}_{int(time.time())}.mp4"
                with requests.get(video_link, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(temp_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                
                with open(temp_filename, 'rb') as f:
                    bot.send_video(m.chat.id, f, caption="✨ *Selesai!*", parse_mode="Markdown", timeout=120)
                
                os.remove(temp_filename)
                anim.stop() 
                bot.delete_message(m.chat.id, loading_msg.message_id)
            else:
                anim.stop()
                bot.edit_message_text("❌ *Gagal:* Sistem API tertahan oleh hak cipta / link tidak valid.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
        except Exception as e: 
            anim.stop()
            logging.error(f"Gagal download API: {str(e)}")
            bot.edit_message_text(f"❌ *Gagal mengunduh!*\n\n`Detail: {str(e)[:150]}...`", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            for file in os.listdir('.'):
                if file.startswith(f"vid_{m.chat.id}"):
                    try: os.remove(file)
                    except: pass
        return

    elif state == "chat":
        loading_msg = bot.reply_to(m, "💭 *AI sedang berpikir...*", parse_mode="Markdown")
        anim = LoadingAnim(m.chat.id, loading_msg.message_id, "Mengetik balasan")
        try:
            reply_text = get_ai_response(m.chat.id, m.text)
            anim.stop()
            bot.edit_message_text(reply_text, m.chat.id, loading_msg.message_id, parse_mode="Markdown")
        except Exception as e: 
            anim.stop()
            bot.edit_message_text(f"❌ *Bot Sibuk:* Coba lagi nanti.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

if __name__ == "__main__": 
    bot.infinity_polling()
        
