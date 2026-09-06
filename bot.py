import asyncio
import logging
import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

import yt_dlp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile,
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeChat,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")

ADMIN_ID = 6770975543
DATABASE = "navo.db"

dp = Dispatcher()

HOSTS = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
)

URL_RE = re.compile(
    r"https?://\S+",
    re.IGNORECASE
)

broadcast_mode = False


# =========================
# БАЗА ДАННЫХ
# =========================

def init_db():
    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            blocked INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            success INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_user(message: Message):
    if not message.from_user:
        return

    user = message.from_user

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username,
        user.first_name,
    ))

    conn.commit()
    conn.close()


def is_blocked(user_id):
    conn = sqlite3.connect(DATABASE)

    row = conn.execute(
        "SELECT blocked FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    return bool(row and row[0])


def add_download(user_id, url, success):
    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        INSERT INTO downloads (
            user_id,
            url,
            success
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        url,
        1 if success else 0,
    ))

    conn.commit()
    conn.close()


# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(user_id):
    return user_id == ADMIN_ID


def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка",
                    callback_data="admin_broadcast"
                )
            ],
        ]
    )


# =========================
# АДМИН-ПАНЕЛЬ
# =========================

@dp.message(Command("admin"))
async def admin(message: Message):
    save_user(message)

    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ Доступ запрещён."
        )
        return

    await message.answer(
        "👑 <b>Navo Downloader</b>\n\n"
        "⚙️ Админ-панель\n\n"
        "Выбери раздел:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True
        )
        return

    conn = sqlite3.connect(DATABASE)

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    blocked = conn.execute(
        "SELECT COUNT(*) FROM users WHERE blocked=1"
    ).fetchone()[0]

    downloads = conn.execute(
        "SELECT COUNT(*) FROM downloads"
    ).fetchone()[0]

    successful = conn.execute(
        "SELECT COUNT(*) FROM downloads WHERE success=1"
    ).fetchone()[0]

    conn.close()

    await callback.message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"🚫 Заблокировано: <b>{blocked}</b>\n"
        f"⬇️ Запросов: <b>{downloads}</b>\n"
        f"✅ Успешных скачиваний: <b>{successful}</b>",
        parse_mode="HTML",
    )

    await callback.answer()


@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True
        )
        return

    conn = sqlite3.connect(DATABASE)

    rows = conn.execute("""
        SELECT
            user_id,
            username,
            first_name,
            blocked
        FROM users
        ORDER BY joined_at DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:
        await callback.message.answer(
            "👥 Пока никто не пользовался ботом."
        )
        await callback.answer()
        return

    text = "👥 <b>Последние пользователи</b>\n\n"

    for user_id, username, first_name, blocked in rows:
        name = first_name or "Без имени"

        if username:
            name += f" (@{username})"

        status = "🚫" if blocked else "✅"

        text += (
            f"{status} {name}\n"
            f"ID: <code>{user_id}</code>\n\n"
        )

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    global broadcast_mode

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True
        )
        return

    broadcast_mode = True

    await callback.message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь следующим сообщением текст рассылки.\n\n"
        "Для отмены отправь /cancel.",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(Command("cancel"))
async def cancel_broadcast(message: Message):
    global broadcast_mode

    if not is_admin(message.from_user.id):
        return

    broadcast_mode = False

    await message.answer(
        "❌ Рассылка отменена."
)
