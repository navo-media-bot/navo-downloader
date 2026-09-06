import os

token = os.getenv("BOT_TOKEN")

if token:
    print("BOT_TOKEN найден")
else:
    print("BOT_TOKEN не найден")
