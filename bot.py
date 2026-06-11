import os
import io
import time
import logging
import base64
import requests
import zipfile

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
# Mengunci nama model resmi vision agar tidak ditolak server Groq
VISION_MODELS = ["llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"]
# ==========================================================================

chat_history = {} 
current_key_index = 0

def get_ai_response(chat_id, prompt, img_pil=None):
    global current_key_index
    global chat_history
    
    raw_keys = os.getenv('GROQ_KEYS') or os.getenv('GROQ_KEY', '')
    API_KEYS = [k.strip().strip('"').strip("'") for k in raw_keys.split(',')] if raw_keys else []
    API_KEYS = [k for k in API_KEYS if k]
    
    if not API_KEYS: return "❌ Variabel 'GROQ_KEYS' belum diisi di server."
        
    attempts = 0
    total_keys = len(API_KEYS)
    
    while attempts < total_keys:
        active_key = API_KEYS[current_key_index % total_keys]
        try:
            temp_client = Groq(api_key=active_key)
            
            if img_pil:
                # --- PERBAIKAN AI VISION ---
                buffered = io.BytesIO()
                img_pil.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                last_error = None
                for model_name in VISION_MODELS:
                    try:
                        response = temp_client.chat.completions.create(
                            model=model_name,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                                ]
                            }],
                            max_tokens=1024 # Parameter wajib agar server tidak error/reject
                        )
                        return response.choices[0].message.content
                    except Exception as ve:
                        last_error = ve
                        continue
                return f"❌ Waduh, semua model Vision sedang diblokir Groq saat ini.\nDetail: {str(last_error)[:100]}"
                
            else:
                # Mode Chat Teks
                if chat_id not in chat_history:
                    chat_history[chat_id] = [{"role": "system", "content": "Kamu adalah asisten AI yang ramah, pintar, dan menggunakan bahasa Indonesia yang santai."}]
                
                chat_history[chat_id].append({"role": "user", "content": prompt})
                
                if len(chat_history[chat_id]) > 11:
                    chat_history[chat_id] = [chat_history[chat_id][0]] + chat_history[chat_id][-10:]
                
                response = temp_client.chat.completions.create(
                    model=TEXT_MODEL,
                    messages=chat_history[chat_id]
                )
                
                bot_reply = response.choices[0].message.content
                chat_history[chat_id].append({"role": "assistant", "content": bot_reply})
                
                return bot_reply
            
        except Exception as e:
            current_key_index = (current_key_index + 1) % total_keys
            attempts += 1
                
    return "❌ Waduh, API Key Groq sedang sibuk/limit! Coba lagi nanti."

# --- FUNGSI BARU: DOWNLOADER MULTI-API LAPIS BAJA ---
def download_media_via_api(url):
    # Lapis 1: Cobalt API (Kualitas terbaik, tanpa watermark)
    try:
        res = requests.post("https://api.cobalt.tools/api/json", json={"url": url}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") in ["stream", "redirect"]: return data.get("url")
            elif data.get("status") == "picker": return data["picker"][0]["url"]
    except: pass
    
    # Lapis 2: Khusus TikTok (TikWM)
    if "tiktok.com" in url or "vt.tiktok" in url:
        try:
            res = requests.get(f"https://www.tikwm.com/api/?url={url}", timeout=10).json()
            return res.get('data', {}).get('play')
        except: pass
        
    # Lapis 3: Fallback YouTube & Instagram (Siputzx API)
    try:
        if "youtube.com" in url or "youtu.be" in url or "yt.be" in url:
            res = requests.get(f"https://api.siputzx.my.id/api/d/ytmp4?url={url}", timeout=15).json()
            return res.get('data', {}).get('dl')
        elif "instagram.com" in url:
            res = requests.get(f"https://api.siputzx.my.id/api/d/igdl?url={url}", timeout=15).json()
            data = res.get('data')
            if isinstance(data, list) and len(data) > 0: return data[0].get('url')
    except: pass
    
    return None

# --- Fungsi Menu Utama ---
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools", "🧹 Hapus Memori Chat")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- Command Start & Hapus History ---
@bot.message_handler(commands=['start'])
def start(m): send_main_menu(m.chat.id, "✨ *Sistem Siap Digunakan!*")

@bot.message_handler(commands=['clear', 'hapus'])
def clear_command(m):
    global chat_history
    if m.chat.id in chat_history: del chat_history[m.chat.id]
    user_states[m.chat.id] = "chat"
    bot.reply_to(m, "🧹 *Memori chat berhasil dihapus!*", parse_mode="Markdown")

# --- Handler Menu Navigasi ---
@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools", "🧹 Hapus Memori Chat"])
def menu(m):
    if m.text == "💬 Chat AI": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat AI Aktif.*", parse_mode="Markdown")
    
    elif m.text == "🧹 Hapus Memori Chat":
        global chat_history
        if m.chat.id in chat_history: del chat_history[m.chat.id]
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "🧹 *Memori dibersihkan!*", parse_mode="Markdown")

    elif m.text == "🤖 AI Vision": 
        user_states[m.chat.id] = "ai_vision"
        bot.reply_to(m, "👁️ *Mode AI Vision Aktif.*\nKirim foto untuk dianalisis!", parse_mode="Markdown")

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

# --- Handler File & Foto ---
@bot.message_handler(content_types=['document', 'photo'])
def handle_files(m):
    state = user_states.get(m.chat.id, "chat")
    file_id = m.document.file_id if m.document else m.photo[-1].file_id
    file_name = m.document.file_name if m.document else "image.jpg"

    if state == "ai_vision":
        loading_msg = bot.reply_to(m, "👁️ *Menganalisis gambar...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            img_pil = Image.open(io.BytesIO(img_data)).convert("RGB")
            
            prompt = m.caption if m.caption else "Tolong jelaskan secara detail isi dari gambar ini."
            reply_text = get_ai_response(m.chat.id, prompt, img_pil=img_pil)
            bot.edit_message_text(f"🤖 *Hasil:*\n\n{reply_text}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
        except Exception as e: 
            bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_rmbg":
        loading_msg = bot.reply_to(m, "🪄 *Menghapus background (Cloud Mode)...*", parse_mode="Markdown")
        try:
            API_KEY = os.getenv('REMOVE_BG_KEY')
            if not API_KEY:
                bot.edit_message_text("❌ *Gagal:* Variabel `REMOVE_BG_KEY` belum disetting di Variables Server!", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                return

            file_path = bot.get_file(file_id).file_path
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            
            # --- PERBAIKAN: API REMOVE.BG (SANGAT RINGAN) ---
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                data={'image_url': file_url, 'size': 'auto'},
                headers={'X-Api-Key': API_KEY},
            )
            
            if response.status_code == requests.codes.ok:
                out_io = io.BytesIO(response.content)
                bot.send_document(m.chat.id, out_io, visible_file_name="nobg_result.png", caption="✨ Selesai!")
                bot.delete_message(m.chat.id, loading_msg.message_id)
            else:
                bot.edit_message_text(f"❌ *Gagal:* Pastikan API Key valid atau kuota Remove.bg masih ada.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
        except Exception as e: 
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
        loading_msg = bot.reply_to(m, "🗜️ *Kompresi file...*", parse_mode="Markdown")
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
            bot.send_document(m.chat.id, out_io, visible_file_name=f"compressed.{ext}", caption="✨ Selesai!")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ Error: {str(e)}", m.chat.id, loading_msg.message_id)

# --- Handler Text (Pesan Biasa / Chat AI / Downloader) ---
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
        loading_msg = bot.reply_to(m, "⏳ *Membongkar link dari server...*", parse_mode="Markdown")
        try:
            # --- PERBAIKAN: MENGGUNAKAN API (MENGHAPUS YT-DLP) ---
            video_link = download_media_via_api(m.text)
            
            if video_link:
                bot.edit_message_text("📤 *Video berhasil ditarik! Menyiapkan pengiriman ke Telegram...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                
                # Download stream per chunk agar RAM tetap super lega
                temp_filename = f"vid_{m.chat.id}_{int(time.time())}.mp4"
                with requests.get(video_link, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(temp_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                bot.edit_message_text("📤 *Sedang mengirim video ke obrolan ini...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                with open(temp_filename, 'rb') as f:
                    bot.send_video(m.chat.id, f, caption="✨ *Selesai!*", parse_mode="Markdown", timeout=120)
                
                # Bersihkan file
                os.remove(temp_filename)
                bot.delete_message(m.chat.id, loading_msg.message_id)
            else:
                bot.edit_message_text("❌ *Gagal:* Sistem API tertahan oleh hak cipta / akun tersebut di-private.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
        except Exception as e: 
            logging.error(f"Gagal download API: {str(e)}")
            bot.edit_message_text(f"❌ *Gagal mengunduh!*\n\n`Detail: {str(e)[:150]}...`", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            # Pembersih sampah darurat
            for file in os.listdir('.'):
                if file.startswith(f"vid_{m.chat.id}"):
                    try: os.remove(file)
                    except: pass
        return

    elif state == "chat":
        bot.send_chat_action(m.chat.id, 'typing')
        try:
            reply_text = get_ai_response(m.chat.id, m.text)
            bot.reply_to(m, reply_text, parse_mode="Markdown")
        except Exception as e: 
            bot.reply_to(m, f"❌ *Bot Sibuk:* Coba lagi.")

if __name__ == "__main__": 
    bot.infinity_polling()
    
