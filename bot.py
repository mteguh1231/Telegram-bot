import os
import io
import logging
import telebot
import requests
import time
import xml.etree.ElementTree as ET
from telebot import types
from PIL import Image
from google import genai
from google.genai import types as genai_types
from yt_dlp import YoutubeDL
from duckduckgo_search import DDGS
from supabase import create_client, Client

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- Helpers ---
def simpan_chat(user_id, message, response):
    if supabase:
        supabase.table("chat_history").insert({"user_id": str(user_id), "message": message, "response": response}).execute()

def ambil_memori(user_id):
    if not supabase: return []
    res = supabase.table("chat_history").select("*").eq("user_id", str(user_id)).order("created_at", desc=True).limit(5).execute()
    return res.data[::-1]

def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            return "\n\n".join([f"Sumber: {r['href']}\nInfo: {r['body']}" for r in results]) if results else "Info tidak ditemukan."
    except: return "Gagal akses internet."

def handle_quota_error(bot, message, e):
    if "429" in str(e):
        bot.reply_to(message, "⚠️ *Maaf, kuota harian bot sedang penuh.* Coba lagi besok ya!")
    else:
        bot.reply_to(message, "Sedang ada gangguan teknis pada server AI.")

# --- UI Menu ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 Chat AI"),
        types.KeyboardButton("🌐 Info Dunia"),
        types.KeyboardButton("🛠️ Alat Media"),
        types.KeyboardButton("⚙️ Pengaturan")
    )
    bot.send_message(message.chat.id, "Halo! Pilih menu di bawah:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🤖 Chat AI", "🌐 Info Dunia", "🛠️ Alat Media", "⚙️ Pengaturan"])
def handle_menu_click(message):
    if message.text == "🤖 Chat AI":
        bot.reply_to(message, "Silakan kirim pesan atau pertanyaanmu.")
    elif message.text == "🌐 Info Dunia":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌤️ Cuaca", callback_data="cmd_cuaca"),
            types.InlineKeyboardButton("📰 Berita", callback_data="cmd_berita"),
            types.InlineKeyboardButton("💡 Quote", callback_data="cmd_quote")
        )
        bot.reply_to(message, "Pilih info yang diinginkan:", reply_markup=markup)
    elif message.text == "🛠️ Alat Media":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Download Video", callback_data="media_download"),
            types.InlineKeyboardButton("👁️ Analisis Foto", callback_data="media_vision"),
            types.InlineKeyboardButton("📄 Ringkas Dokumen", callback_data="media_doc")
        )
        bot.reply_to(message, "🛠️ Pusat Alat Media:", reply_markup=markup)
    elif message.text == "⚙️ Pengaturan":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Reset Memori", callback_data="cmd_reset"))
        bot.reply_
        
