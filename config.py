import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    print("Не указан BOT_TOKEN")

if not ADMIN_ID:
    print("Не указан ADMIN_ID")

ADMIN_ID = int(ADMIN_ID)