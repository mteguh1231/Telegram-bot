import os
import telebot

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Bot berhasil terhubung ke Railway!")

if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot sedang berjalan...")
    bot.infinity_polling()
    
