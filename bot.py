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

# --- Pengaman Import Library (Mencegah Crash jika belum terinstal) ---
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

# --- Setup Konfigurasi Utama ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

user_states = {}
user_chats = {} 

# --- Fungsi Efek Animasi Premium ---
def animate_loading(chat_id, message_id, steps, delay=0.4):
    """Mengubah teks secara dinamis untuk memberikan efek loading yang mewah"""
    for step in steps:
        try:
            bot.edit_message_text(step, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
            time.sleep(delay)
        except Exception:
            pass

# --- Helper Menu Utama Keyboard Bottom ---
def send_main_menu(chat_id, text="🤖 *Bot Utama Siap!*\nSilakan pilih menu di bawah ini:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("💬 Chat AI"), 
        types.KeyboardButton("📥 Downloader"),
        types.KeyboardButton("📁 Convert File")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- Handlers Perintah /start ---
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

# --- Handlers Navigasi Menu Utama ---
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
        bot.reply_to(m, "📁 *File Converter Engine*\nSilakan tentukan jenis konversi dokumen/media kamu:", reply_markup=markup, parse_mode="Markdown")

# --- Callbacks Navigation & Sistem Back ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    
    if call.data == "back_to_main":
        user_states[cid] = "chat"
        bot.delete_message(cid, mid)
        send_main_menu(cid, text="🔙 *Kembali ke Menu Utama.*\nSilakan pilih fitur kembali:")
        return

    # Callback untuk Portal Downloader
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

    # Callback untuk Portal Converter
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

# --- Handler Dokumen & Gambar (Proses Mesin Konversi) ---
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
            with open(out_file, 'rb') as doc: bot.send_document(m.chat.id, doc
            
