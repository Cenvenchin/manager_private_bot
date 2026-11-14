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

pending_income_amounts = {}

def parse_amount(amount_text):
    normalized = (
        amount_text.strip()
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace(",", ".")
    )

    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
        raise ValueError(
            "Введи корректную сумму. Например: 1500 или 1500,50"
        )

    amount = Decimal(normalized)

    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")

    return int(amount * 100)

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("💵 Добавить доход"), KeyboardButton("📊 Статистика"))
    markup.row(KeyboardButton("🗓️ Доходы за период"), KeyboardButton("📋 История доходов"))

    return markup

@bot.message_handler(func=lambda message: message.text == "💵 Добавить доход")
def add_income_start(message):

    prompt = bot.send_message(
        message.chat.id,
        "💰 Введите сумму дохода в рублях:\n"
        "Для отмены напишите: Отмена"
    )

    bot.register_next_step_handler(
        prompt,
        process_income_amount
    )


def process_income_amount(message):

    if cancel_income(message):
        bot.send_message(
            message.chat.id,
            "Добавление дохода отменено.",
            reply_markup=main_menu()
        )
        return

    try:
        amount_kopecks = parse_amount(message.text or "")
    except ValueError as error:
        prompt = bot.send_message(
            message.chat.id,
            f"⚠️ {error}\nПопробуй ещё раз."
        )
        bot.register_next_step_handler(prompt, process_income_amount)
        return

    pending_income_amounts[message.from_user.id] = amount_kopecks

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "Пропустить",
        callback_data="skip_income_service"
    ))

    prompt = bot.send_message(
        message.chat.id,
        "📝 Моежете указать источник дохода или описание услуги.\n\n"
        "Например: Маникюр.\n\n"
        "Если не хотите указывать источник дохода:\n"
        "Можете нажать кнопку Пропустить.",
        reply_markup=markup
    )

    bot.register_next_step_handler(
        prompt,
        process_income_service,
        amount_kopecks
    )

def cancel_income(message):
    return (message.text or "").strip().lower() in (
        "отмена",
        "❌ отмена"
    )

def save_income_and_finish(chat_id, telegram_id, amount_kopecks, service):

    user = get_user_by_telegram_id(telegram_id)

    if not user or user["status"] != "active":
        bot.send_message(chat_id, "Нет доступа.")
        return

    add_income(
        user_id=user["id"],
        amount=amount_kopecks,
        service=service
    )

    rubles, kopecks = divmod(amount_kopecks, 100)

    bot.send_message(
        chat_id,
        "✅ Ваш доход сохранён!\n\n"
        f"💰 Сумма: {rubles:,}".replace(",", " ")
        + f",{kopecks:02d} ₽\n"
        f"📝 Источник дохода: {service or 'Без комментария'}",
        reply_markup=main_menu()
    )


def process_income_service(message, amount_kopecks):

    telegram_id = message.from_user.id

    if cancel_income(message):
        pending_income_amounts.pop(telegram_id, None)
        bot.send_message(
            message.chat.id,
            "Добавление дохода отменено.",
            reply_markup=main_menu()
        )
        return

    service = (message.text or "").strip()

    pending_income_amounts.pop(telegram_id, None)

    save_income_and_finish(
        message.chat.id,
        telegram_id,
        amount_kopecks,
        service
    )


@bot.callback_query_handler(
    func=lambda call: call.data == "skip_income_service"
)
def skip_income_service(call):

    bot.answer_callback_query(call.id)

    telegram_id = call.from_user.id

    amount_kopecks = pending_income_amounts.pop(
        telegram_id,
        None
    )

    if amount_kopecks is None:
        bot.send_message(
            call.message.chat.id,
            "Операция не найдена."
        )
        return

    bot.clear_step_handler_by_chat_id(call.message.chat.id)

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None
    )

    save_income_and_finish(
        call.message.chat.id,
        telegram_id,
        amount_kopecks,
        ""
    )


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