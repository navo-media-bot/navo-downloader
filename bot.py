import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart, Command

import yt_dlp

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

dp = Dispatcher()

URL_RE = re.compile(r"https?://\S+", re.I)

SUPPORTED_HOSTS = (
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "tiktok.com",
)


def is_supported_url(url: str) -> bool:
    url = url.lower()
    return any(host in url for host in SUPPORTED_HOSTS)


def download_video(url: str, folder: str):
    output = str(Path(folder) / "%(title).80s-%(id)s.%(ext)s")

    options = {
        "outtmpl": output,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": 49 * 1024 * 1024,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

        filepath = ydl.prepare_filename(info)
        mp4 = str(Path(filepath).with_suffix(".mp4"))

        if Path(mp4).exists():
            filepath = mp4

        if not Path(filepath).exists():
            files = list(Path(folder).glob("*"))

            if not files:
                raise FileNotFoundError("Video file not found")

            filepath = str(files[0])

        return filepath, info


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я Navo Downloader.\n"
        "Отправь мне публичную ссылку на видео "
        "из YouTube, TikTok или Instagram.\n\n"
        "⬇️ Я попробую скачать его и отправить тебе."
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📥 Поддерживаются:\n\n"
        "▶️ YouTube\n"
        "🎵 TikTok\n"
        "📸 Instagram\n\n"
        "Просто отправь ссылку."
    )


@dp.message(F.text)
async def handle_link(message: Message):

    match = URL_RE.search(message.text)

    if not match:
        await message.answer("❌ Отправь ссылку на видео.")
        return

    url = match.group(0).rstrip(".,!?)]}")

    if not is_supported_url(url):
        await message.answer(
            "❌ Пока поддерживаются только "
            "YouTube, TikTok и Instagram."
        )
        return

    status = await message.answer("⏬ Скачиваю видео...")

    folder = tempfile.mkdtemp(prefix="navo_")

    try:
        try:
            filepath, info = await asyncio.to_thread(
                download_video,
                url,
                folder
            )

        except Exception:
            logging.exception("Download error")

            await status.edit_text(
                "❌ Не получилось скачать видео.\n\n"
                "Возможно, видео приватное, ссылка недействительна "
                "или файл слишком большой."
            )

            return

        await status.edit_text("📤 Отправляю видео...")

        title = info.get("title") or "video"

        safe_title = re.sub(
            r'[\\/:*?"<>|]+',
            "_",
            title
        )[:80]

        if not safe_title:
            safe_title = "video"

        video = FSInputFile(
            filepath,
            filename=f"{safe_title}.mp4"
        )

        try:
            await message.answer_video(
                video=video,
                caption="✅ Готово!"
            )

        except Exception:
            await message.answer_document(
                document=video,
                caption="✅ Готово!"
            )

        await status.delete()

    finally:
        shutil.rmtree(
            folder,
            ignore_errors=True
        )


async def main():
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
