import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден."
    )


dp = Dispatcher()

ADMIN_ID = 6770975543


def is_admin(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == ADMIN_ID


@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if not is_admin(message):
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return

    await message.answer(
        "👑 Navo Admin\n\n"
        "📊 Статистика\n"
        "👥 Пользователи\n"
        "📢 Рассылка\n"
        "🚫 Заблокированные"
    )

URL_RE = re.compile(
    r"https?://\S+",
    re.IGNORECASE
)

SUPPORTED_HOSTS = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
)


def is_supported_url(url: str) -> bool:
    url_lower = url.lower()

    return any(
        host in url_lower
        for host in SUPPORTED_HOSTS
    )


def download_video(url: str, folder: str):
    output_template = str(
        Path(folder) /
        "%(title).80s-%(id)s.%(ext)s"
    )

    options = {
        "outtmpl": output_template,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": 49 * 1024 * 1024,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

        filepath = ydl.prepare_filename(info)

    path = Path(filepath)

    mp4_path = path.with_suffix(".mp4")

    if mp4_path.exists():
        path = mp4_path

    if not path.exists():
        files = [
            p for p in Path(folder).iterdir()
            if p.is_file()
        ]

        if not files:
            raise FileNotFoundError(
                "Скачанный файл не найден."
            )

        path = files[0]

    return str(path), info


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я Navo Downloader.\n"
        "Отправь публичную ссылку на видео "
        "из YouTube, TikTok или Instagram.\n\n"
        "⏬ Я попробую скачать его и отправить тебе."
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📥 Поддерживаются:\n\n"
        "▶️ YouTube\n"
        "🎵 TikTok\n"
        "📸 Instagram\n\n"
        "Просто отправь ссылку на видео."
    )


@dp.message(F.text)
async def link_handler(message: Message):
    text = message.text or ""

    match = URL_RE.search(text)

    if not match:
        await message.answer(
            "❌ Отправь ссылку на видео."
        )
        return

    url = match.group(0).rstrip(
        ".,!?)]}"
    )

    if not is_supported_url(url):
        await message.answer(
            "❌ Поддерживаются только "
            "YouTube, TikTok и Instagram."
        )
        return

    status = await message.answer(
        "⏬ Скачиваю видео..."
    )

    folder = tempfile.mkdtemp(
        prefix="navo_"
    )

    try:
        try:
            filepath, info = await asyncio.to_thread(
                download_video,
                url,
                folder
            )

        except Exception:
            logging.exception(
                "Ошибка скачивания"
            )

            await status.edit_text(
                "❌ Не удалось скачать видео.\n\n"
                "Возможно:\n"
                "• видео приватное;\n"
                "• ссылка недействительна;\n"
                "• сайт временно не поддерживается;\n"
                "• видео слишком большое."
            )

            return

        await status.edit_text(
            "📤 Отправляю видео..."
        )

        title = info.get(
            "title",
            "video"
        )

        safe_title = re.sub(
            r'[\\/:*?"<>|]+',
            "_",
            title
        ).strip()

        safe_title = safe_title[:80]

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

        try:
            await status.delete()
        except Exception:
            pass

    finally:
        shutil.rmtree(
            folder,
            ignore_errors=True
        )


async def main():
    bot = Bot(
        token=TOKEN
    )

    try:
        print("ЗАПУСК БОТА")
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
