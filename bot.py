import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

BOT_TOKEN = os.getenv("8382786338:AAG5PIqTogDL0UDW0RJnNEXUAt1PtHhRo38")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Bot hidup 🚀")

def main():
    print("TOKEN:", repr(BOT_TOKEN))

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
