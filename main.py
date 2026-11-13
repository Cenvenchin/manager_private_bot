import telebot
from telebot import types
from dotenv import load_dotenv
import re
from decimal import Decimal
import os

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, ensure_admin, register_user, get_user_by_telegram_id, add_income


load_dotenv()

if not BOT_TOKEN:
    print("Не найден BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

def create_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)

    money_button = types.InlineKeyboardButton(
        "💵 Добавить доход",
        callback_data="add_money"
    )

    stats_button = types.InlineKeyboardButton(
        "📊 Статистика",
        callback_data="stats"
    )

    period_button = types.InlineKeyboardButton(
        "🗓️ Доходы за период",
        callback_data="period"
    )

    history_button = types.InlineKeyboardButton(
        "📋 История доходов",
        callback_data="history"
    )

    markup.add(money_button, stats_button)
    markup.add(period_button, history_button)

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
            reply_markup=create_main_menu()
        )



if __name__ == "__main__":
    init_db()
    ensure_admin(ADMIN_ID)

    print("Бот запущен!")

    bot.infinity_polling()