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

# Mencoba import pdf2docx untuk fitur PDF ke Word
try:
    from pdf2docx import Converter
except ImportError:
    Converter = None

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

user_states = {}
user_chats = {} 

# --- Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    # Animasi Loading Start
    loading_msg = bot.reply_to(m, "🔄 Menyiapkan sistem...")
    time.sleep(0.5)
    bot.edit_message_text("⚙️ Memuat menu...", chat_id=m.chat.id, message_id=loading_msg.message_id)
    time.sleep(0.5)
    
    bot.delete_message(m.chat.id, loading_msg.message_id)
    
    # Menu Keyboard Utama
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("💬 Chat"), 
        types.KeyboardButton("📥 Download"),
        types.KeyboardButton("🛠️ Tools")
    )
    
    bot.send_message(m.chat.id, "🤖 *Bot siap digunakan!*\nSilakan pilih menu di bawah ini:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["💬 Chat", "📥 Download", "🛠️ Tools"])
def menu(m):
    if m.text == "💬 Chat": 
        user_states[m.chat.id] = "chat"
        bot.reply_to(m, "💬 *Mode Chat Aktif.*\nSilakan ngobrol dengan AI!", parse_mode="Markdown")
    elif m.text == "📥 Download": 
        user_states[m.chat.id] = "download"
        bot.reply_to(m, "📥 *Mode Download Aktif.*\nKirim link video yang ingin diunduh:", parse_mode="Markdown")
    elif m.text == "🛠️ Tools": 
        user_states[m.chat.id] = "tools"
        
        # Membuat tombol pilihan (Inline Keyboard) khusus di dalam menu Tools
        markup = types.InlineKeyboardMarkup()
        btn_pdf2word = types.InlineKeyboardButton("📄 PDF ke Word", callback_data="set_pdf2word")
        btn_word2pdf = types.InlineKeyboardButton("📝 Word ke PDF", callback_data="set_word2pdf")
        markup.add(btn_pdf2word, btn_word2pdf)
        
        bot.reply_to(m, "🛠️ *Menu Pilihan Converter:*\nSilakan klik tombol di bawah ini sesuai kebutuhanmu:", reply_markup=markup, parse_mode="Markdown")

# --- Handler untuk Menangkap Klik Tombol Pilihan Tools ---
@bot.callback_query_handler(func=lambda call: call.data in ["set_pdf2word", "set_word2pdf"])
def callback_tools(call):
    if call.data == "set_pdf2word":
        user_states[call.message.chat.id] = "pdf2word"
        bot.edit_message_text("📄 *Mode PDF ke Word Aktif.*\nSilakan kirim file `.pdf` kamu ke sini!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    elif call.data == "set_word2pdf":
        user_states[call.message.chat.id] = "word2pdf"
        bot.edit_message_text("📝 *Mode Word ke PDF Aktif.*\nSilakan kirim file `.docx` atau `.doc` kamu ke sini!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# --- Handler Khusus untuk Mengolah File Dokumen (PDF / Word) ---
@bot.message_handler(content_types=['document'])
def handle_docs(m):
    state = user_states.get(m.chat.id, "chat")
    
    # 1. LOGIKA FITUR PDF KE WORD
    if state == "pdf2word":
        if not m.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(m, "❌ Format salah! Harap kirimkan file dengan ekstensi `.pdf`")
            return
            
        loading_msg = bot.reply_to(m, "⏳ *Mengunduh file PDF dari Telegram...*", parse_mode="Markdown")
        bot.send_chat_action(m.chat.id, 'upload_document')
        
        try:
            file_info = bot.get_file(m.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            pdf_path = m.document.file_name
            docx_path = pdf_path.rsplit('.', 1)[0] + '.docx'
            
            with open(pdf_path, 'wb') as f:
                f.write(downloaded_file)
                
            bot.edit_message_text("🔄 *Sedang mengonversi PDF ke Word (Docx)...*\n_Mohon tunggu sebentar..._", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
            # Eksekusi konversi pustaka pdf2docx
            cv = Converter(pdf_path)
            cv.convert(docx_path, start=0, end=None)
            cv.close()
            
            bot.edit_message_text("🚀 *Mengirim file hasil konversi...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
            with open(docx_path, 'rb') as doc:
                bot.send_document(m.chat.id, doc, caption="✨ *Konversi PDF ke Word Selesai!*", parse_mode="Markdown")
                
            # Hapus file sementara di server biar gak penuh
            os.remove(pdf_path)
            os.remove(docx_path)
            bot.delete_message(m.chat.id, loading_msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ *Gagal konversi:* {str(e)}", m.chat.id, loading_msg.message_id, parse_mode="Markdown")

    # 2. LOGIKA FITUR WORD KE PDF
    elif state == "word2pdf":
        if not (m.document.file_name.lower().endswith('.docx') or m.document.file_name.lower().endswith('.doc')):
            bot.reply_to(m, "❌ Format salah! Harap kirimkan file berformat Word (`.docx` / `.doc`)")
            return
            
        loading_msg = bot.reply_to(m, "⏳ *Mengunduh file Word dari Telegram...*", parse_mode="Markdown")
        bot.send_chat_action(m.chat.id, 'upload_document')
        
        try:
            file_info = bot.get_file(m.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            docx_path = m.document.file_name
            pdf_path = docx_path.rsplit('.', 1)[0] + '.pdf'
            
            with open(docx_path, 'wb') as f:
                f.write(downloaded_file)
                
            bot.edit_message_text("🔄 *Sedang mengonversi Word ke PDF via LibreOffice...*\n_Proses ini memakan waktu beberapa detik..._", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
            # Eksekusi perintah CLI Linux LibreOffice untuk merubah Word ke PDF secara headless
            cmd = ['libreoffice', '--headless', '--convert-to', 'pdf', docx_path]
            subprocess.run(cmd, check=True, timeout=40)
            
            bot.edit_message_text("🚀 *Mengirim file hasil konversi...*", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
            with open(pdf_path, 'rb') as pdf:
                bot.send_document(m.chat.id, pdf, caption="✨ *Konversi Word ke PDF Selesai!*", parse_mode="Markdown")
                
            # Hapus file sementara di server
            os.remove(docx_path)
            os.remove(pdf_path)
            bot.delete_message(m.chat.id, loading_msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ *Gagal konversi:* {str(e)}\n\n_Catatan: Pastikan server hosting kamu sudah terinstall paket 'libreoffice'._", m.chat.id, loading_msg.message_id, parse_mode="Markdown")
            
    else:
        bot.reply_to(m, "💡 Kamu sedang tidak dalam mode konversi dokumen. Silakan pilih menu *🛠️ Tools* terlebih dahulu.", parse_mode="Markdown")

# --- Handler Utama untuk Menangkap Input Teks ---
@bot.message_handler(content_types=['text'])
def handle(m):
    state = user_states.get(m.chat.id, "chat")
    
    # --- FITUR DOWNLOAD VIDEO ---
    if state == "download":
        try:
            loading_msg = bot.reply_to(m, "⏳ *Memproses link...*", parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'record_video')
            
            ydl_opts = {'format': 'best', 'outtmpl': 'media.mp4', 'quiet': True}
            with YoutubeDL(ydl_opts) as ydl: 
                ydl.download([m.text])
                
            bot.edit_message_text("🚀 *Mengirim video...*", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'upload_video')
            
            with open('media.mp4', 'rb') as f: 
                bot.send_video(m.chat.id, f)
            os.remove('media.mp4')
            
            bot.delete_message(m.chat.id, loading_msg.message_id)
            bot.send_message(m.chat.id, "💡 _Kirim link lagi untuk download video lain._", parse_mode="Markdown")
        except Exception as e: 
            bot.edit_message_text("❌ *Gagal mengunduh.* Pastikan link valid.", chat_id=m.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
    
    # --- INFO REKONDISI JIKA USER MASUKIN TEKS SAAT MODE TOOLS ---
    elif state in ["pdf2word", "word2pdf", "tools"]:
        bot.reply_to(m, "⚠️ Kamu sedang dalam mode Alat Converter. *Harap kirimkan file dokumen*, bukan pesan teks.\n\n_Klik menu '💬 Chat' jika ingin kembali mengobrol dengan AI._", parse_mode="Markdown")

    # --- FITUR CHAT AI (DEFAULT) ---
    elif state == "chat":
        if m.chat.id not in user_chats: 
            user_chats[m.chat.id] = ai_client.chats.create(model="gemini-2.5-flash")
        
        try:
            loading_msg = bot.reply_to(m, "💭 *AI sedang berpikir...*", parse_mode="Markdown")
            bot.send_chat_action(m.chat.id, 'typing')
            
            reply_text = user_chats[m.chat.id].send_message(m.text).text
            bot.edit_message_text(reply_text, chat_id=m.chat.id, message_id=loading_msg.message_id)
        except Exception as e:
            bot.edit_message_text("❌ Maaf, sistem AI sedang mengalami kendala.", chat_id=m.chat.id, message_id=loading_msg.message_id)

if __name__ == "__main__": 
    print("Bot Converter & AI sedang berjalan...")
    bot.infinity_polling()
    
