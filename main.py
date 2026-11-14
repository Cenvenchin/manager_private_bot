import telebot
from dotenv import load_dotenv
import re
from decimal import Decimal
from telebot.types import (ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                           InlineKeyboardMarkup,
                           InlineKeyboardButton)
import os

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, ensure_admin, register_user, get_user_by_telegram_id, add_income


load_dotenv()

if not BOT_TOKEN:
    print("Не найден BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("💵 Добавить доход"), KeyboardButton("📊 Статистика"))
    markup.row(KeyboardButton("🗓️ Доходы за период"), KeyboardButton("📋 История доходов"))

    return markup


@bot.message_handler(commands=['start'])
def start(message):

    telegram_id = message.from_user.id


    user, created = register_user(
        telegram_id=telegram_id,
        first_name=message.from_user.first_name,
        username=message.from_user.username
    )

    if created and telegram_id != ADMIN_ID:

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "Не указан"
        )

        try:
            bot.send_message(
                ADMIN_ID,
                "🆕 Новый пользователь зарегистрировался!\n\n"
                f"Имя: {message.from_user.first_name}\n"
                f"Username: {username}\n"
                f"Telegram ID: {telegram_id}"
            )
        except Exception as error:
            print(f"Не удалось уведомить администратора: {error}")

    if user["status"] == "active":

        bot.send_message(
            message.chat.id,
            "Привет! Это бот для учёта доходов 💵\n"
            "выберите действие в меню:",
            reply_markup=main_menu()
        )



if __name__ == "__main__":
    init_db()
    ensure_admin(ADMIN_ID)

    print("Бот запущен!")

    bot.infinity_polling()