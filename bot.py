cat > bot.py <<'PY'
import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
raise RuntimeError("BOT_TOKEN не найден")

dp = Dispatcher()

HOSTS = (
"youtube.com",
"youtu.be",
"tiktok.com",
"instagram.com",
)

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

def supported(url):
return any(host in url.lower() for host in HOSTS)

def download(url, folder):
output = str(Path(folder) / "%(title).80s-%(id)s.%(ext)s")

options = {  
    "outtmpl": output,  
    "format": "best[ext=mp4]/best",  
    "noplaylist": True,  
    "quiet": True,  
    "no_warnings": True,  
    "restrictfilenames": True,  
}  

with yt_dlp.YoutubeDL(options) as ydl:  
    info = ydl.extract_info(url, download=True)  
    filename = ydl.prepare_filename(info)  

path = Path(filename)  

if not path.exists():  
    files = list(Path(folder).glob("*"))  
    files = [x for x in files if x.is_file()]  

    if not files:  
        raise FileNotFoundError("Файл не найден")  

    path = files[0]  

return path, info

@dp.message(CommandStart())
async def start(message: Message):
await message.answer(
"👋 Привет!\n\n"
"Я Navo Downloader.\n\n"
"📥 Отправь публичную ссылку на видео "
"из YouTube, TikTok или Instagram."
)

@dp.message(F.text)
async def video(message: Message):
match = URL_RE.search(message.text or "")

if not match:  
    await message.answer("❌ Отправь ссылку на видео.")  
    return  

url = match.group(0).rstrip(".,!?)]}")  

if not supported(url):  
    await message.answer(  
        "❌ Поддерживаются YouTube, TikTok и Instagram."  
    )  
    return  

status = await message.answer("⏬ Скачиваю...")  

folder = tempfile.mkdtemp(prefix="navo_")  

try:  
    try:  
        path, info = await asyncio.to_thread(  
            download,  
            url,  
            folder  
        )  
    except Exception:  
        logging.exception("DOWNLOAD ERROR")  
        await status.edit_text(  
            "❌ Не удалось скачать видео."  
        )  
        return  

    await status.edit_text("📤 Отправляю...")  

    title = info.get("title", "video")  
    title = re.sub(r'[\\/:*?"<>|]+', "_", title)[:80]  

    file = FSInputFile(  
        str(path),  
        filename=f"{title}.mp4"  
    )  

    try:  
        await message.answer_video(  
            file,  
            caption="✅ Готово!"  
        )  
    except Exception:  
        await message.answer_document(  
            file,  
            caption="✅ Готово!"  
        )  

    await status.delete()  

finally:  
    shutil.rmtree(folder, ignore_errors=True)

async def main():
bot = Bot(token=TOKEN)

print("🚀 NAVO DOWNLOADER")  
print("✅ Токен найден")  
print("⏳ Бот запущен и ждёт сообщения")  

try:  
    await dp.start_polling(bot)  
finally:  
    await bot.session.close()

if name == "main":
asyncio.run(main())
PY
