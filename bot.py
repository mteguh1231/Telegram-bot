import os
import io
import time
import logging
import subprocess
import telebot
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL

# Import library konversi tambahan dengan penanganan error
try:
    from pdf2docx import Converter
except ImportError:
    Converter = None

try:
    import fitz  # PyMuPDF untuk PDF ke JPG
except ImportError:
    fitz = None

try:
    import pdfplumber
    import pandas as pd
except ImportError:
    pdfplumber = None
    pd = None

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

user_states = {}
user_chats = {} 

# --- Fungsi Efek Animasi "Wah" ---
def animate_loading(chat_id, message_id, steps, delay=0.4):
    for step in steps:
        try:
            bot.edit_message_text(step, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
            time.sleep(delay)
        except Exception:
            pass

# --- Helper Menu Utama ---
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("💬 Chat AI"), 
        types.KeyboardButton("📥 Downloader"),
        types.KeyboardButton("📁 Convert File")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- Handlers Utama ---
@bot.message_handler(commands=['start'])
def start(m):
    loading_msg = bot.reply_to(m, "⚡ *Menginisialisasi Bot...* `[▒▒▒▒▒▒▒▒▒▒] 0%`", parse_mode="Markdown")
    time.sleep(0.3)
    bot.edit_message_text("⚙️ *Memuat Sistem Konversi...* `[██████▒▒▒▒] 60%`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.3)
    bot.edit_message_text("✨ *Sistem Siap!* `[██████████] 100%`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.2)
    bot.delete_message(m.chat.id, loading_msg.message_id)
    send_main_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "📥 Downloader", "📁 Convert File"])
def menu(m):
    if m.text == "💬 Chat AI": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat AI Aktif.*\nSilakan kirimkan pertanyaan atau obrolan kamu!", parse_mode="Markdown")
        
    elif m.text == "📥 Downloader":
        user_states[m.chat.id] = "downloader_menu"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔺 YouTube Video/Shorts", callback_data="dl_yt"),
            types.InlineKeyboardButton("⚫ TikTok Video", callback_data="dl_tt"),
            types.InlineKeyboardButton("📸 Instagram Reel/Post", callback_data="dl_ig"),
            types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")
        )
        bot.reply_to(m, "📥 *Premium Downloader Portal*\nPilih platform media yang ingin kamu unduh:", reply_markup=markup, parse_mode="Markdown")
        
    elif m.text == "📁 Convert File": 
        user_states[m.chat.id] = "convert_menu"
        markup = types.InlineKeyboardMarkup(row_width=2) # Diatur menjadi 2 kolom agar rapi
        markup.add(
            types.InlineKeyboardButton("📄 PDF ke Word", callback_data="set_pdf2word"),
            types.InlineKeyboardButton("📝 Word ke PDF", callback_data="set_word2pdf"),
            types.InlineKeyboardButton("🖼️ Gambar ke JPG", callback_data="set_any2jpg"),
            types.InlineKeyboardButton("📄➡️🖼️ PDF ke JPG", callback_data="set_pdf2jpg"),
            types.InlineKeyboardButton("🖼️➡️📄 JPG ke PDF", callback_data="set_jpg2pdf"),
            types.InlineKeyboardButton("📊 PDF ke Excel", callback_data="set_pdf2excel")
        )
        markup.add(types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main"))
        bot.reply_to(m, "📁 *File Converter Engine*\nSilakan tentukan jenis konversi dokumen/media kamu:", reply_markup=markup, parse_mode="Markdown")

# --- Callbacks Navigation ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    
    if call.data == "back_to_main":
        user_states[cid] = "chat"
        bot.delete_message(cid, mid)
        send_main_menu(cid, text="🔙 *Kembali ke Menu Utama.*\nSilakan pilih fitur kembali:")
        return

    # Callback Downloader Portal
    if call.data in ["dl_yt", "dl_tt", "dl_ig"]:
        platform = {"dl_yt": "YouTube", "dl_tt": "TikTok", "dl_ig": "Instagram"}[call.data]
        user_states[cid] = call.data
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_downloader"))
        bot.edit_message_text(f"📥 *Mode Unduh {platform} Aktif.*\nSilakan kirimkan tautan/link video {platform} kamu!", cid, mid, reply_markup=markup, parse_mode="Markdown")
        return
        
    elif call.data == "back_to_downloader":
        user_states[cid] = "downloader_menu"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔺 YouTube Video/Shorts", callback_data="dl_yt"),
            types.InlineKeyboardButton("⚫ TikTok Video", callback_data="dl_tt"),
            types.InlineKeyboardButton("📸 Instagram Reel/Post", callback_data="dl_ig"),
            types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")
        )
        bot.edit_message_text("📥 *Premium Downloader Portal*\nPilih platform media yang ingin kamu unduh:", cid, mid, reply_markup=markup, parse_mode="Markdown")
        return

    # Callback Converter Portal
    if call.data in ["set_pdf2word", "set_word2pdf", "set_any2jpg", "set_jpg2pdf", "set_pdf2jpg", "set_pdf2excel"]:
        user_states[cid] = call.data
        info_text = {
            "set_pdf2word": "📄 *Mode PDF ke Word Aktif.*\nKirimkan file dokumen berformat `.pdf` kamu!",
            "set_word2pdf": "📝 *Mode Word ke PDF Aktif.*\nKirimkan file dokumen berformat `.docx` atau `.doc`!",
            "set_any2jpg": "🖼️ *Mode Gambar ke JPG Aktif.*\nKirimkan gambar tipe apa saja (PNG, WEBP, dll)!",
            "set_jpg2pdf": "🖼️➡️📄 *Mode JPG ke PDF Aktif.*\nKirimkan gambar berformat `.jpg` atau `.png`!",
            "set_pdf2jpg": "📄➡️🖼️ *Mode PDF ke JPG Aktif.*\nKirimkan file dokumen berformat `.pdf` kamu!",
            "set_pdf2excel": "📊 *Mode PDF ke Excel Aktif.*\nKirimkan file dokumen `.pdf` yang berisi data tabel!"
        }[call.data]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_convert"))
        bot.edit_message_text(info_text, cid, mid, reply_markup=markup, parse_mode="Markdown")
        return
        
    elif call.data == "back_to_convert":
        user_states[cid] = "convert_menu"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📄 PDF ke Word", callback_data="set_pdf2word"),
            types.InlineKeyboardButton("📝 Word ke PDF", callback_data="set_word2pdf"),
            types.InlineKeyboardButton("🖼️ Gambar ke JPG", callback_data="set_any2jpg"),
            types.InlineKeyboardButton("📄➡️🖼️ PDF ke JPG", callback_data="set_pdf2jpg"),
            types.InlineKeyboardButton("🖼️➡️📄 JPG ke PDF", callback_data="set_jpg2pdf"),
            types.InlineKeyboardButton("📊 PDF ke Excel", callback_data="set_pdf2excel")
        )
        markup.add(types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main"))
        bot.edit_message_text("📁 *File Converter Engine*\nSilakan tentukan jenis konversi dokumen/media kamu:", cid, mid, reply_markup=markup, parse_mode="Markdown")

# --- Handler Dokumen & Gambar (Proses Engine) ---
@bot.message_handler(content_types=['document', 'photo'])
def handle_files(m):
    state = user_states.get(m.chat.id, "chat")
    
    # 1. PDF KE WORD
    if state == "set_pdf2word" and m.document:
        if not m.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(m, "❌ Masukkan file `.pdf` yang valid!")
            return
        loading_msg = bot.reply_to(m, "📥 *Mengunduh file...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file, out_file = m.document.file_name, m.document.file_name.rsplit('.', 1)[0] + '.docx'
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "⚡ *Mengekstrak susunan teks...* `[████▒▒▒▒▒▒]` 40%",
                "📝 *Menyusun berkas Word (.docx)...* `[████████▒▒]` 80%"
            ])
            cv = Converter(in_file)
            cv.convert(out_file, start=0, end=None)
            cv.close()
            
            bot.edit_message_text("🚀 *Mengirim hasil konversi...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            with open(out_file, 'rb') as doc: bot.send_document(m.chat.id, doc, caption="✨ *Konversi PDF ke Word Selesai!*")
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    # 2. WORD KE PDF
    elif state == "set_word2pdf" and m.document:
        if not (m.document.file_name.lower().endswith('.docx') or m.document.file_name.lower().endswith('.doc')):
            bot.reply_to(m, "❌ Masukkan file Word (`.docx`/`.doc`)!")
            return
        loading_msg = bot.reply_to(m, "📥 *Mengunduh file...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            doc_data = bot.download_file(file_path)
            in_file, out_file = m.document.file_name, m.document.file_name.rsplit('.', 1)[0] + '.pdf'
            with open(in_file, 'wb') as f: f.write(doc_data)
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "🗃️ *Memuat LibreOffice Server...* `[████▒▒▒▒▒▒]` 40%",
                "📄 *Mengunci enkapsulasi PDF...* `[█████████▒]` 90%"
            ])
            subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', in_file], check=True, timeout=40)
            
            with open(out_file, 'rb') as pdf: bot.send_document(m.chat.id, pdf, caption="✨ *Konversi Word ke PDF Selesai!*")
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    # 3. GAMBAR APAPUN KE JPG
    elif state == "set_any2jpg":
        file_id = m.document.file_id if m.document else m.photo[-1].file_id
        orig_name = m.document.file_name if m.document else "image.png"
        loading_msg = bot.reply_to(m, "📥 *Mengunduh gambar...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            out_name = orig_name.rsplit('.', 1)[0] + '.jpg'
            
            img = Image.open(io.BytesIO(img_data))
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                img = bg
            else: img = img.convert('RGB')
            
            out_io = io.BytesIO()
            img.save(out_io, format="JPEG", quality=95)
            out_io.seek(0); out_io.name = out_name
            
            bot.send_document(m.chat.id, out_io, caption="✨ *Sukses konversi ke JPG!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    # 4. NEW! GAMBAR (JPG/PNG) KE PDF
    elif state == "set_jpg2pdf":
        file_id = m.document.file_id if m.document else m.photo[-1].file_id
        orig_name = m.document.file_name if m.document else "image.jpg"
        loading_msg = bot.reply_to(m, "📥 *Memproses konversi ke PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            out_name = orig_name.rsplit('.', 1)[0] + '.pdf'
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "🖼️ *Menyelaraskan skala gambar...* `[█████▒▒▒▒▒]` 50%",
                "📄 *Mengonversi struktur berkas PDF...* `[█████████▒]` 90%"
            ], delay=0.3)
            
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
            out_io = io.BytesIO()
            img.save(out_io, format="PDF")
            out_io.seek(0); out_io.name = out_name
            
            bot.send_document(m.chat.id, out_io, caption="✨ *Sukses konversi Gambar ke PDF!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    # 5. NEW! PDF KE JPG (Mengekstrak Halaman Pertama PDF Menjadi Gambar)
    elif state == "set_pdf2jpg" and m.document:
        if not m.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(m, "❌ Masukkan file berformat `.pdf`!")
            return
        loading_msg = bot.reply_to(m, "📥 *Membaca halaman PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file = m.document.file_name
            out_file = in_file.rsplit('.', 1)[0] + '.jpg'
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "📸 *Me-render halaman pertama...* `[██████▒▒▒▒]` 60%",
                "🖼️ *Menyimpan sebagai citra JPG...* `[█████████▒]` 90%"
            ], delay=0.3)
            
            # Eksekusi PyMuPDF
            doc = fitz.open(in_file)
            page = doc.load_page(0) # Ambil halaman pertama (indeks 0)
            pix = page.get_pixmap(dpi=150)
            pix.save(out_file)
            doc.close()
            
            with open(out_file, 'rb') as img:
                bot.send_photo(m.chat.id, img, caption="✨ *Sukses Konversi PDF ke Gambar JPG (Hal 1)!*")
                
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    # 6. NEW! PDF KE EXCEL (Mengekstrak Tabel PDF ke File Spreadsheet)
    elif state == "set_pdf2excel" and m.document:
        if not m.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(m, "❌ Masukkan file berformat `.pdf`!")
            return
        loading_msg = bot.reply_to(m, "📥 *Mengekstrak data tabel PDF...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            in_file = m.document.file_name
            out_file = in_file.rsplit('.', 1)[0] + '.xlsx'
            with open(in_file, 'wb') as f: f.write(pdf_data)
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "📊 *Menganalisis matriks baris & kolom...* `[████▒▒▒▒▒▒]` 40%",
                "📈 *Menyusun lembar sheet Excel...* `[████████▒▒]` 80%"
            ], delay=0.4)
            
            # Eksekusi pdfplumber & pandas
            with pdfplumber.open(in_file) as pdf:
                writer = pd.ExcelWriter(out_file, engine='openpyxl')
                has_tables = False
                for i, page in enumerate(pdf.pages):
                    table = page.extract_table()
                    if table:
                        has_tables = True
                        df_table = pd.DataFrame(table)
                        df_table.to_excel(writer, sheet_name=f'Halaman_{i+1}', index=False, header=False)
                
                if not has_tables:
                    bot.edit_message_text("⚠️ *Gagal:* Tidak ditemukan struktur tabel data yang dapat dibaca di dalam PDF tersebut.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
                    os.remove(in_file); return
                writer.close()
                
            with open(out_file, 'rb') as excel:
                bot.send_document(m.chat.id, excel, caption="✨ *Sukses Ekstrak PDF ke Excel (.xlsx)!*")
                
            os.remove(in_file); os.remove(out_file); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e: bot.edit_message_text(f"❌ *Gagal:* {str(e)}", m.chat.id, loading_msg.message_id)

    elif state in ["convert_menu", "downloader_menu"]:
        bot.reply_to(m, "⚠️ Pilihlah jenis konversi/opsi terlebih dahulu menggunakan tombol yang tersedia.", parse_mode="Markdown")

# --- Handler Teks Utama (Chat AI & Downloader) ---
@bot.message_handler(content_types=['text'])
def handle_text(m):
    state = user_states.get(m.chat.id, "chat")
    
    if state in ["dl_yt", "dl_tt", "dl_ig"]:
        platform_names = {"dl_yt": "YouTube", "dl_tt": "TikTok", "dl_ig": "Instagram"}
        p_name = platform_names[state]
        
        loading_msg = bot.reply_to(m, f"⏳ *[1/3] Menghubungkan ke API {p_name}...* `[▒▒▒▒▒▒▒▒▒▒]`", parse_mode="Markdown")
        bot.send_chat_action(m.chat.id, 'record_video')
        try:
            animate_loading(m.chat.id, loading_msg.message_id, [
                f"📡 *[2/3] Membuka bypass enkripsi {p_name}...* `[█████▒▒▒▒▒]`",
                "⚡ *[3/3] Streaming paket data video ke server...* `[█████████▒]`"
            ], delay=0.5)
            
            out_filename = f"media_{m.chat.id}.mp4"
            ydl_opts = {'format': 'best', 'outtmpl': out_filename, 'quiet': True}
            with YoutubeDL(ydl_opts) as ydl: ydl.download([m.text])
                
            bot.edit_message_text("🚀 *Proses Selesai! Mengunggah klip ke Telegram...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'upload_video')
            with open(out_filename, 'rb') as f: bot.send_video(m.chat.id, f, caption=f"✨ Video {p_name} berhasil diunduh!")
            os.remove(out_filename); bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception: 
            bot.edit_message_text(f"❌ *Gagal mengunduh!* Pastikan link {p_name} valid.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

    elif state in ["convert_menu", "downloader_menu"] or state.startswith("set_"):
        bot.reply_to(m, "⚠️ Harap kirimkan file/dokumen media yang sesuai.\n_Klik menu '💬 Chat AI' untuk mengobrol dengan AI._", parse_mode="Markdown")
    
    elif state == "chat":
        if m.chat.id not in user_chats: 
            user_chats[m.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        loading_msg = bot.reply_to(m, "💭 *AI sedang merangkai jawaban...*", parse_mode="Markdown")
        bot.send_chat_action(m.chat.id, 'typing')
        try:
            reply_text = user_chats[m.chat.id].send_message(m.text).text
            bot.edit_message_text(reply_text, chat_id=m.chat.id, message_id=loading_msg.message_id)
        except Exception:
            bot.edit_message_text("❌ Jaringan AI sedang sibuk. Coba sesaat lagi.", chat_id=m.chat.id, message_id=loading_msg.message_id)

if __name__ == "__main__": 
    print("Bot Converter Ult
