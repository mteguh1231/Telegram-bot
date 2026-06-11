import os, io, logging, telebot
from telebot import types
from PIL import Image
from google import genai
from yt_dlp import YoutubeDL

# --- Pengaman Import Library ---
try: from rembg import remove
except: remove = None

# --- Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# MENGGUNAKAN NAMA MODEL YANG LEBIH KOMPATIBEL
MODEL_NAME = "gemini-1.5-flash-001" 

user_states = {}
user_chats = {}

def send_main_menu(chat_id, text="🤖 *Bot Siap!* Silakan pilih menu:"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "🛠️ Utility Tools")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(m): send_main_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text in ["💬 Chat AI", "🤖 AI Vision", "📥 Downloader", "🛠️ Utility Tools"])
def menu(m):
    user_states[m.chat.id] = m.text
    bot.reply_to(m, f"✅ Mode {m.text} aktif. Silakan kirimkan data/file yang diperlukan.")

@bot.message_handler(content_types=['photo', 'text'])
def handle_all(m):
    state = user_states.
    
