import os
import io
import time
import logging
import subprocess
import sys
import zipfile

import telebot
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL

# --- Pengaman Import Library Lama ---
try:
    from pdf2docx import Converter
except ImportError:
    Converter = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pdfplumber
    import pandas as pd
except ImportError:
    pdfplumber = None
    pd = None

# --- Pengaman Import Library BARU ---
try:
    from rembg import remove
except ImportError:
    remove = None

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    import qrcode
except ImportError:
    qrcode = None

# --- Setup Konfigurasi Utama ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# ==========================================
# ROTASI API KEY GEMINI VIA RAILWAY VARIABLES
# ==========================================
raw_keys = os.getenv('GEMINI_KEYS', '')
API_KEYS = [k.strip() for k in raw_keys.split(',')] if raw_keys else []
current_key_index = 0

def get_ai_response(prompt, img_pil=None):
    global current_key_index
    
    if not API_KEYS or API_KEYS == ['']:
        return "❌ Batalkan proses! Variabel 'GEMINI_KEYS' belum diisi atau salah format di Railway."
        
    attempts = 0
    while attempts < len(API_KEYS):
        active_key = API_KEYS[current_key_index]
        temp_client = genai.Client(api_key=active_key)
        
        try:
            if img_pil:
                response = temp_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, img_pil]
                )
            else:
                response = temp_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
            return response.text
            
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                logging.warning(f"Key indeks ke-{current_key_index} kena limit. Rotasi ke key berikutnya!")
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                attempts += 1
            else:
                raise e 
                
    return "❌ Waduh, semua API Key yang didaftarkan di Railway sedang limit! Coba beberapa menit lagi."

# ==========================================

# --- Fungsi Animasi ---
def animate_loading(chat_id, message_id, steps, delay=0.4):
    for step in steps:
        try:
            bot.edit_message_text(step, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
            time.sleep(delay)
        except Exception:
            pass

# --- Menu Utama ---
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💬 Chat AI"), 
        types.KeyboardButton("🤖 AI Vision"),
        types.KeyboardButton("📥 Downloader"),
        types.KeyboardButton("📁 Convert File"),
        types.KeyboardButton("🛠️ Utility Tools")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- Command Start ---
@bot.message_handler(commands=['start'])
def start(m):
    loading_msg = bot.reply_to(m, "⚡ *Menginisialisasi Bot...* `[▒▒▒▒▒▒▒▒▒▒]`", parse_mode="Markdown")
    time.sleep(0.5)
    bot.edit_message_text("✨ *Sistem Siap!* `[██████████]`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.3)
    bot.delete_message(m.chat.id, loading_msg.message_id)
    send_main_menu(m.chat.id)

# --- Handler Menu Navigasi ---
@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "📁 Convert File", "🛠️ Utility Tools"])
def menu(m):
    if m.text == "💬 Chat AI": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat AI Aktif.*\nSilakan kirimkan pertanyaan atau obrolan kamu!", parse_mode="Markdown")
        
    elif m.text == "🤖 AI Vision": 
        user_states[m.chat.id] = "ai_vision"
        bot.reply_to(m, "👁️ *Mode AI Vision (OCR & Analisis) Aktif.*\nSilakan kirimkan *Foto* (dengan caption pertanyaan jika ada). AI akan membaca teks dan menganalisis gambar tersebut!", parse_mode="Markdown")

    elif m.text == "📥 Downloader":
        user_states[m.chat.id] = "downloader_menu"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔺 YouTube Video", callback_data="dl_yt"),
            types.InlineKeyboardButton("⚫ TikTok Video", callback_data="dl_tt"),
            types.InlineKeyboardButton("📸 Instagram Reel", callback_data="dl_ig"),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
        )
        bot.reply_to(m, "📥 *Premium Downloader Portal*\nPilih platform media:", reply_markup=markup, parse_mode="Markdown")
        
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
        bot.reply_to(m, "📁 *File Converter Engine*\nSilakan pilih metode konversi:", reply_markup=markup, parse_mode="Markdown")

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
        bot.reply_to(m, "🛠️ *Utility Tools*\nFitur praktis untuk kebutuhanmu:", reply_markup=markup, parse_mode="Markdown")

# --- Callbacks ---
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
        bot.edit_message_text(f"📥 *Mode Unduh {platform} Aktif.*\nKirimkan linknya!", cid, mid, parse_mode="Markdown")
        return
        
    if call.data in ["set_pdf2word", "set_word2pdf", "set_any2jpg", "set_jpg2pdf", "set_pdf2jpg", "set_pdf2excel"]:
        user_states[cid] = call.data
        bot.edit_message_text(f"📁 *Mode Konversi Aktif.*\nSilakan kirimkan file yang sesuai!", cid, mid, parse_mode="Markdown")
        return

    if call.data in ["set_rmbg", "set_compress", "set_qr_gen", "set_qr_read"]:
        user_states[cid] = call.data
        if call.data == "set_qr_gen":
            msg = "🔳 *Pembuat QR Code*\nSilakan kirim *Teks atau Link* yang ingin dijadikan QR Code!"
        else:
            msg = f"🛠️ *Mode Aktif.*\nSilakan kirimkan foto atau file yang ingin diproses!"
        bot.edit_message_text(msg, cid, mid, parse_mode="Markdown")
        return

# --- Handler File (PDF, Foto, Dokumen) ---
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
            
            prompt = m.caption if m.caption else "Ekstrak teks (OCR) jika ada, lalu jelaskan isi gambar ini secara detail."
            reply_text = get_ai_response(prompt, img_pil=img_pil)
            bot.edit_message_text(f"🤖 *Hasil AI Vision:*\n\n{reply_text}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
        except Exception as e: 
            bot.edit_message_text(f"❌ *Error AI Vision:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_rmbg":
        loading_msg = bot.reply_to(m, "🪄 *Menghapus background, mohon tunggu...*", parse_mode="Markdown")
        try:
            if remove is None: raise Exception("Library rembg gagal dimuat.")
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            
            output_data = remove(img_data)
            out_io = io.BytesIO(output_data)
            
            bot.send_document(m.chat.id, out_io, visible_file_name="nobg_result.png", caption="✨ *Background berhasil dihapus!* (Format PNG)")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_qr_read":
        loading_msg = bot.reply_to(m, "🔍 *Mendeteksi QR Code...*", parse_mode="Markdown")
        try:
            if cv2 is None: raise Exception("Library opencv-python gagal dimuat.")
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            
            np_arr = np.frombuffer(img_data, np.uint8)
            img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(img_cv)
            
            if data:
                bot.edit_message_text(f"✅ *QR Code Terdeteksi!*\n\n*Isi:* `{data}`", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ *Gagal mendeteksi.* Pastikan gambar jelas dan berisi QR Code.", m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_compress":
        loading_msg = bot.reply_to(m, "🗜️ *Mengompresi file...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            file_data = bot.download_file(file_path)
            out_io = io.BytesIO()
            
            if m.photo or file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                img = Image.open(io.BytesIO(file_data))
                if img.mode != 'RGB': img = img.convert('RGB')
                img.save(out_io, format="JPEG", optimize=True, quality=60)
                ext = "jpg"
            else:
                with zipfile.ZipFile(out_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.writestr(file_name, file_data)
                ext = "zip"
                
            out_io.seek(0)
            bot.send_document(m.chat.id, out_io, visible_file_name=f"compressed_{m.chat.id}.{ext}", caption="✨ *Kompresi Selesai!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error Kompresi:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_pdf2word" and m.document:
        loading_msg = bot.reply_to(m, "📥 *Memproses PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file, out_file = m.document.file_name, m.document.file_name.rsplit('.', 1)[0] + '.docx'
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            cv = Converter(in_file)
            cv.convert(out_file, start=0, end=None)
            cv.close()
            
            with open(out_file, 'rb') as doc:
                bot.send_document(m.chat.id, doc, caption="✨ *Konversi PDF ke Word Selesai!*")
            
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_word2pdf" and m.document:
        loading_msg = bot.reply_to(m, "📥 *Memproses Word...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            doc_data = bot.download_file(file_path)
            in_file, out_file = m.document.file_name, m.document.file_name.rsplit('.', 1)[0] + '.pdf'
            with open(in_file, 'wb') as f: f.write(doc_data)
            
            subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', in_file], check=True)
            
            with open(out_file, 'rb') as pdf:
                bot.send_document(m.chat.id, pdf, caption="✨ *Konversi Word ke PDF Selesai!*")
            
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_any2jpg":
        loading_msg = bot.reply_to(m, "📥 *Mengonversi gambar...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            out_name = "output.jpg"
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
            out_io = io.BytesIO()
            img.save(out_io, format="JPEG", quality=95)
            out_io.seek(0)
            
            bot.send_document(m.chat.id, out_io, visible_file_name=out_name, caption="✨ *Sukses konversi ke JPG!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_jpg2pdf":
        loading_msg = bot.reply_to(m, "📥 *Memproses PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
            out_io = io.BytesIO()
            img.save(out_io, format="PDF")
            out_io.seek(0)
            
            bot.send_document(m.chat.id, out_io, visible_file_name="output.pdf", caption="✨ *Sukses konversi Gambar ke PDF!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_pdf2jpg" and m.document:
        loading_msg = bot.reply_to(m, "📥 *Merender PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file = "temp.pdf"
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            doc = fitz.open(in_file)
            pix = doc.load_page(0).get_pixmap(dpi=150)
            out_io = io.BytesIO(pix.tobytes())
            
            bot.send_photo(m.chat.id, out_io, caption="✨ *Hasil PDF ke JPG!*")
            os.remove(in_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state == "set_pdf2excel" and m.document:
        loading_msg = bot.reply_to(m, "📥 *Mengekstrak data...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file = "temp.pdf"; out_file = "temp.xlsx"
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            with pdfplumber.open(in_file) as pdf:
                with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
                    for i, page in enumerate(pdf.pages):
                        table = page.extract_table()
                        if table:
                            pd.DataFrame(table).to_excel(writer, sheet_name=f'Page_{i+1}', index=False, header=False)
            
            with open(out_file, 'rb') as excel:
                bot.send_document(m.chat.id, excel, caption="✨ *Konversi Excel Selesai!*")
            
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)

# --- Handler Teks (AI, QR Gen & Downloader) ---
@bot.message_handler(content_types=['text'])
def handle_text(m):
    state = user_states.get(m.chat.id, "chat")
    
    if state == "set_qr_gen":
        loading_msg = bot.reply_to(m, "🔳 *Merender QR Code...*", parse_mode="Markdown")
        try:
            if qrcode is None: raise Exception("Library qrcode gagal dimuat.")
            img = qrcode.make(m.text)
            out_io = io.BytesIO()
            img.save(out_io, format="PNG")
            out_io.seek(0)
            bot.send_photo(m.chat.id, out_io, caption=f"✨ *QR Code Selesai!*\n*Data:* {m.text[:50]}...")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Error:* {str(e)}", m.chat.id, loading_msg.message_id)
        return

    elif state in ["dl_yt", "dl_tt", "dl_ig"]:
        loading_msg = bot.reply_to(m, "⏳ *Mengunduh media...*", parse_mode="Markdown")
        try:
            out_filename = f"media_{m.chat.id}.mp4"
            with YoutubeDL({'format': 'best', 'outtmpl': out_filename}) as ydl: 
                ydl.download([m.text])
            
            with open(out_filename, 'rb') as f: 
                bot.send_video(m.chat.id, f, caption="✨ *Unduhan Selesai!*")
            os.remove(out_filename); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception: bot.edit_message_text("❌ *Gagal mengunduh!*", m.chat.id, loading_msg.message_id)

    elif state == "chat":
        loading_msg = bot.reply_to(m, "💭 *AI sedang berpikir...*", parse_mode="Markdown")
        try:
            reply_text = get_ai_response(m.text)
            bot.edit_message_text(reply_text, chat_id=m.chat.id, message_id=loading_msg.message_id)
        except Exception as e: 
            bot.edit_message_text(f"❌ *AI Sibuk:* {str(e)}", chat_id=m.chat.id, message_id=loading_msg.message_id)

if __name__ == "__main__": 
    bot.infinity_polling()
            
