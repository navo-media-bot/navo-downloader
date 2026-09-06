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
    Message,
    FSInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeChat,
)


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден. Добавь токен бота в переменную BOT_TOKEN."
    )

ADMIN_ID = 6770975543
DATABASE = "navo.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

dp = Dispatcher()


# =========================
# БАЗА ДАННЫХ
# =========================

def init_db():
    conn = sqlite3.connect(DATABASE)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            blocked INTEGER DEFAULT 0
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
        """
    )

    conn.commit()
    conn.close()


def save_user(message: Message):
    if not message.from_user:
        return

    user = message.from_user

    conn = sqlite3.connect(DATABASE)

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
        """,
        (
            user.id,
            user.username,
            user.first_name,
        ),
    )

    conn.commit()
    conn.close()


def is_blocked(user_id: int) -> bool:
    conn = sqlite3.connect(DATABASE)

    row = conn.execute(
        "SELECT blocked FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return bool(row and row[0])


def get_stats():
    conn = sqlite3.connect(DATABASE)

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    blocked = conn.execute(
        "SELECT COUNT(*) FROM users WHERE blocked = 1"
    ).fetchone()[0]

    downloads = conn.execute(
        "SELECT COUNT(*) FROM downloads"
    ).fetchone()[0]

    successful = conn.execute(
        "SELECT COUNT(*) FROM downloads WHERE success = 1"
    ).fetchone()[0]

    conn.close()

    return users, blocked, downloads, successful


def add_download(user_id: int, url: str, success: bool):
    conn = sqlite3.connect(DATABASE)

    conn.execute(
        """
        INSERT INTO downloads (
            user_id,
            url,
            success
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            url,
            1 if success else 0,
        ),
    )

    conn.commit()
    conn.close()


# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin_user(user_id: int) -> bool:
    return user_id == ADMIN_ID


# =========================
# АДМИН-КЛАВИАТУРА
# =========================

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="stats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="users",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка",
                    callback_data="broadcast",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Заблокированные",
                    callback_data="blocked",
                )
            ],
        ]
    )


# =========================
# КОМАНДА /ADMIN
# =========================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not message.from_user:
        return

    save_user(message)

    if not is_admin_user(message.from_user.id):
        await message.answer(
            "⛔ Доступ запрещён."
        )
        return

    await message.answer(
        "👑 <b>Navo Downloader</b>\n\n"
        "⚙️ Панель администратора\n\n"
        "Выбери раздел:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


# =========================
# СТАТИСТИКА
# =========================

@dp.callback_query(F.data == "stats")
async def stats_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )
        return

    users, blocked, downloads, successful = get_stats()

    text = (
        "📊 <b>Статистика Navo Downloader</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"🚫 Заблокировано: <b>{blocked}</b>\n"
        f"⬇️ Запросов на скачивание: <b>{downloads}</b>\n"
        f"✅ Успешных скачиваний: <b>{successful}</b>"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
    )

    await callback.answer()


# =========================
# ПОЛЬЗОВАТЕЛИ
# =========================

@dp.callback_query(F.data == "users")
async def users_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )
        return

    conn = sqlite3.connect(DATABASE)

    rows = conn.execute(
        """
        SELECT user_id, username, first_name, blocked
        FROM users
        ORDER BY joined_at DESC
        LIMIT 20
        """
    ).fetchall()

    conn.close()

    if not rows:
        await callback.message.answer(
            "👥 Пользователей пока нет."
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
        parse_mode="HTML",
    )

    await callback.answer()


# =========================
# ЗАБЛОКИРОВАННЫЕ
# =========================

@dp.callback_query(F.data == "blocked")
async def blocked_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )
        return

    conn = sqlite3.connect(DATABASE)

    rows = conn.execute(
        """
        SELECT user_id, username, first_name
        FROM users
        WHERE blocked = 1
        ORDER BY joined_at DESC
        """
    ).fetchall()

    conn.close()

    if not rows:
        await callback.message.answer(
            "🚫 Заблокированных пользователей нет."
        )
        await callback.answer()
        return

    text = "🚫 <b>Заблокированные</b>\n\n"

    for user_id, username, first_name in rows:
        name = first_name or "Без имени"

        if username:
            name += f" (@{username})"

        text += (
            f"• {name}\n"
            f"ID: <code>{user_id}</code>\n\n"
        )

    await callback.message.answer(
        text,
        parse_mode="HTML",
    )

    await callback.answer()
