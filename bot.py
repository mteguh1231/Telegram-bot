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
from supabase import create_client, Client

try:
    from pdf2docx import Converter
except ImportError:
    Converter = None

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
    """Membuat efek teks loading yang berubah secara dinamis untuk kesan premium"""
    for step in steps:
        try:
            bot.edit_message_text(step, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
            time.sleep(delay)
        except Exception:
            pass # Menghindari error jika proses asli terlalu cepat selesai

# --- Helper Menu Utama ---
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("💬 Chat AI"), 
        types.KeyboardButton("📥 Downloader"),
        types.KeyboardButton("📁 Convert File")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    # Animasi Loading Start Premium
    loading_msg = bot.reply_to(m, "⚡ *Menginisialisasi Bot...* `[▒▒▒▒▒▒▒▒▒▒] 0%`", parse_mode="Markdown")
    time.sleep(0.3)
    bot.edit_message_text("⚙️ *Memuat Database & AI...* `[████▒▒▒▒▒▒] 40%`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.3)
    bot.edit_message_text("🚀 *Menyelaraskan Sistem...* `[████████▒▒] 80%`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.3)
    bot.edit_message_text("✨ *Sistem Siap!* `[██████████] 100%`", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    time.sleep(0.3)
    
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
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📄 PDF ke Word (.docx)", callback_data="set_pdf2word"),
            types.InlineKeyboardButton("📝 Word ke PDF (.pdf)", callback_data="set_word2pdf"),
            types.InlineKeyboardButton("🖼️ Gambar Apapun ke JPG", callback_data="set_any2jpg"),
            types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")
        )
        bot.reply_to(m, "📁 *File Converter Engine*\nSilakan tentukan jenis konversi dokumen/media kamu:", reply_markup=markup, parse_mode="Markdown")

# --- Callbacks (Navigasi & Pilihan Sub-Menu) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    
    # Fitur Back / Kembali ke Menu Utama
    if call.data == "back_to_main":
        user_states[cid] = "chat"
        bot.delete_message(cid, mid)
        send_main_menu(cid, text="🔙 *Kembali ke Menu Utama.*\nSilakan pilih fitur kembali:")
        return

    # Sub-Menu Downloader
    if call.data in ["dl_yt", "dl_tt", "dl_ig"]:
        platform = {"dl_yt": "YouTube", "dl_tt": "TikTok", "dl_ig": "Instagram"}[call.data]
        user_states[cid] = call.data
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_downloader"))
        bot.edit_message_text(f"📥 *Mode Unduh {platform} Aktif.*\nSilakan kirimkan tautan/link video {platform} kamu!", cid, mid, reply_markup=markup, parse_mode="Markdown")
        
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

    # Sub-Menu Converter
    elif call.data in ["set_pdf2word", "set_word2pdf", "set_any2jpg"]:
        user_states[cid] = call.data
        info_text = {
            "set_pdf2word": "📄 *Mode PDF ke Word Aktif.*\nKirimkan file dokumen berformat `.pdf` kamu!",
            "set_word2pdf": "📝 *Mode Word ke PDF Aktif.*\nKirimkan file dokumen berformat `.docx` atau `.doc`!",
            "set_any2jpg": "🖼️ *Mode Convert ke JPG Aktif.*\nKirimkan gambar jenis apa saja (PNG, WEBP, BMP, dll) sebagai *File/Document*!"
        }[call.data]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="back_to_convert"))
        bot.edit_message_text(info_text, cid, mid, reply_markup=markup, parse_mode="Markdown")
        
    elif call.data == "back_to_convert":
        user_states[cid] = "convert_menu"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📄 PDF ke Word (.docx)", callback_data="set_pdf2word"),
            types.InlineKeyboardButton("📝 Word ke PDF (.pdf)", callback_data="set_word2pdf"),
            types.InlineKeyboardButton("🖼️ Gambar Apapun ke JPG", callback_data="set_any2jpg"),
            types.InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")
        )
        bot.edit_message_text("📁 *File Converter Engine*\nSilakan tentukan jenis konversi dokumen/media kamu:", cid, mid, reply_markup=markup, parse_mode="Markdown")

# --- Handler Dokumen & Gambar (Proses Konversi File) ---
@bot.message_handler(content_types=['document', 'photo'])
def handle_files(m):
    state = user_states.get(m.chat.id, "chat")
    
    # 1. CONVERT: PDF KE WORD
    if state == "set_pdf2word" and m.document:
        if not m.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(m, "❌ *Format Gagal!* Sistem hanya menerima file berekstensi `.pdf`", parse_mode="Markdown")
            return
        
        loading_msg = bot.reply_to(m, "📥 *Mengunduh PDF dari cloud Telegram...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            pdf_data = bot.download_file(file_path)
            
            in_file = m.document.file_name
            out_file = in_file.rsplit('.', 1)[0] + '.docx'
            
            with open(in_file, 'wb') as f: f.write(pdf_data)
                
            animate_loading(m.chat.id, loading_msg.message_id, [
                "🔄 *Membaca struktur layout PDF...* `[▓▒▒▒▒▒▒▒▒▒]` 15%",
                "⚡ *Mengekstrak teks & elemen tabel...* `[████▒▒▒▒▒▒]` 45%",
                "📝 *Menyusun ulang ke dokumen Word...* `[████████▒▒]` 80%"
            ])
            
            cv = Converter(in_file)
            cv.convert(out_file, start=0, end=None)
            cv.close()
            
            bot.edit_message_text("🚀 *Konversi Selesai! Mengirimkan hasil...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            with open(out_file, 'rb') as doc:
                bot.send_document(m.chat.id, doc, caption="✨ *Sukses konversi PDF ke Word!*")
            
            os.remove(in_file)
            os.remove(out_file)
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ *Gagal Konversi:* {str(e)}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

    # 2. CONVERT: WORD KE PDF
    elif state == "set_word2pdf" and m.document:
        if not (m.document.file_name.lower().endswith('.docx') or m.document.file_name.lower().endswith('.doc')):
            bot.reply_to(m, "❌ *Format Gagal!* Kirimkan file dokumen Word (`.docx`/`.doc`)", parse_mode="Markdown")
            return
            
        loading_msg = bot.reply_to(m, "📥 *Mengunduh file Word...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(m.document.file_id).file_path
            doc_data = bot.download_file(file_path)
            
            in_file = m.document.file_name
            out_file = in_file.rsplit('.', 1)[0] + '.pdf'
            
            with open(in_file, 'wb') as f: f.write(doc_data)
                
            animate_loading(m.chat.id, loading_msg.message_id, [
                "🗃️ *Mempersiapkan LibreOffice Virtual Engine...* `[▒▒▒▒▒▒▒▒▒▒]` 10%",
                "⚙️ *Rendering halaman dokumen...* `[█████▒▒▒▒▒]` 50%",
                "📄 *Mengunci enkapsulasi objek PDF...* `[█████████▒]` 90%"
            ])
            
            subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', in_file], check=True, timeout=40)
            
            bot.edit_message_text("🚀 *Konversi Selesai! Mengirimkan file...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            with open(out_file, 'rb') as pdf:
                bot.send_document(m.chat.id, pdf, caption="✨ *Sukses konversi Word ke PDF!*")
                
            os.remove(in_file)
            os.remove(out_file)
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ *Gagal Konversi:* {str(e)}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

    # 3. CONVERT: APAPUN KE JPG
    elif state == "set_any2jpg":
        # Menangani file gambar yang dikirim sebagai dokumen maupun photo biasa
        file_id = m.document.file_id if m.document else m.photo[-1].file_id
        orig_name = m.document.file_name if m.document else "image.png"
        
        loading_msg = bot.reply_to(m, "📥 *Mengunduh berkas gambar...*", parse_mode="Markdown")
        try:
            file_path = bot.get_file(file_id).file_path
            img_data = bot.download_file(file_path)
            
            out_name = orig_name.rsplit('.', 1)[0] + '.jpg'
            
            animate_loading(m.chat.id, loading_msg.message_id, [
                "🖼️ *Membuka kompresi piksel gambar...* `[███▒▒▒▒▒▒▒]` 30%",
                "🎨 *Membangun matriks spektrum RGB baru...* `[███████▒▒▒]` 70%"
            ], delay=0.3)
            
            img = Image.open(io.BytesIO(img_data))
            # Konversi RGBA (transparan) ke RGB standar sebelum disimpan ke JPG
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                img = bg
            else:
                img = img.convert('RGB')
                
            out_io = io.BytesIO()
            img.save(out_io, format="JPEG", quality=95)
            out_io.seek(0)
            out_io.name = out_name
            
            bot.edit_message_text("🚀 *Mengirimkan hasil kompresi JPG...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            bot.send_document(m.chat.id, out_io, caption="✨ *Sukses konversi ke format JPG standard!*")
            bot.delete_message(m.chat.id, loading_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ *Gagal Konversi Gambar:* {str(e)}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
    elif state in ["convert_menu", "downloader_menu"]:
        bot.reply_to(m, "⚠️ *Aksi Ditolak.* Harap pilih opsi sub-menu di tombol inline terlebih dahulu.", parse_mode="Markdown")

# --- Handler Utama Teks (Proses Chat & Downloader) ---
@bot.message_handler(content_types=['text'])
def handle_text(m):
    state = user_states.get(m.chat.id, "chat")
    
    # LOGIKA PENGUNDUH MEDIA (YOUTUBE, TIKTOK, INSTAGRAM)
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
            
            with YoutubeDL(ydl_opts) as ydl: 
                ydl.download([m.text])
                
            bot.edit_message_text("🚀 *Proses Selesai! Mengunggah klip ke Telegram...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'upload_video')
            
            with open(out_filename, 'rb') as f: 
                bot.send_video(m.chat.id, f, caption=f"✨ Video {p_name} berhasil diunduh!")
                
            os.remove(out_filename)
            bot.delete_message(m.chat.id, loading_msg.message_id)
            
        except Exception as e: 
            bot.edit_message_text(f"❌ *Gagal mengunduh!* Pastikan link {p_name} valid atau coba link video lainnya.", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

    # LOGIKA RE-KONDISI JIKA USER MASUKIN TEKS SAAT MODE PILIHAN FILE
    elif state in ["set_pdf2word", "set_word2pdf", "convert_menu", "downloader_menu"]:
        bot.reply_to(m, "⚠️ Harap kirimkan berkas/file media yang sesuai, bukan instruksi teks.\n_Klik menu '💬 Chat AI' untuk mengobrol._", parse_mode="Markdown")
    
    # CHAT AI UTAMA (DEFAULT STATE)
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
    print("Bot Terstruktur Premium Aktif...")
    bot.infinity_polling()
            
