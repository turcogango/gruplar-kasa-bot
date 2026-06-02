import ssl
import aiohttp
import json
import re
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ---------------- USERS ---------------- #

with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(USERS, f, indent=4, ensure_ascii=False)

# ---------------- ADMIN ---------------- #

def is_admin(user_id: int):
    admin_ids = os.environ.get("ADMIN_IDS", "").split(",")
    admin_ids = [int(i.strip()) for i in admin_ids if i.strip()]
    return user_id in admin_ids

# ---------------- PANEL ---------------- #

PANELS = {
    "panel1": {
        "url": os.environ.get("PANEL1_URL"),
        "username": os.environ.get("PANEL1_USER"),
        "password": os.environ.get("PANEL1_PASS")
    },
    "panel2": {
        "url": os.environ.get("PANEL2_URL"),
        "username": os.environ.get("PANEL2_USER"),
        "password": os.environ.get("PANEL2_PASS")
    }
}

# ---------------- NUMBER ---------------- #

def extract_number(text: str):
    m = re.search(r'(\d+)', text)
    return m.group(1) if m else None

# ---------------- PANEL UPDATE (CRITICAL FIX) ---------------- #

async def update_havale(panel_config, uuid, value):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_config['url']}/login"

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:

        # LOGIN PAGE
        async with session.get(login_url) as r:
            text = await r.text()

        token = ""
        for line in text.splitlines():
            if 'name="_token"' in line:
                token = line.split('value="')[1].split('"')[0]
                break

        # LOGIN
        await session.post(login_url, data={
            "_token": token,
            "email": panel_config["username"],
            "password": panel_config["password"]
        })

        # EDIT PAGE
        edit_url = f"{panel_config['url']}/users/{uuid}/edit"

        async with session.get(edit_url) as r:
            page = await r.text()

        csrf = ""
        for line in page.splitlines():
            if 'csrf-token' in line:
                csrf = line.split('content="')[1].split('"')[0]
                break

        # UPDATE POST
        await session.post(edit_url, data={
            "_token": csrf,
            "havale_alim": str(value)
        })

# ---------------- SKY AKTİF ---------------- #

async def aktif_sky(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin değil")
            return

        num = extract_number(update.message.text)
        if not num:
            await update.message.reply_text("❌ Numara yok")
            return

        key = f"SKY{num}"

        if key not in USERS:
            await update.message.reply_text("❌ Kullanıcı yok")
            return

        info = USERS[key]

        # JSON update
        USERS[key]["havale_alim"] = 1
        save_users()

        # PANEL update
        await update_havale(PANELS[info["panel"]], info["uuid"], 1)

        await update.message.reply_text(f"✅ {key} AKTİF")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

# ---------------- SKY PASİF ---------------- #

async def pasif_sky(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin değil")
            return

        num = extract_number(update.message.text)
        if not num:
            await update.message.reply_text("❌ Numara yok")
            return

        key = f"SKY{num}"

        if key not in USERS:
            await update.message.reply_text("❌ Kullanıcı yok")
            return

        info = USERS[key]

        # JSON update
        USERS[key]["havale_alim"] = 0
        save_users()

        # PANEL update
        await update_havale(PANELS[info["panel"]], info["uuid"], 0)

        await update.message.reply_text(f"❌ {key} PASİF")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

# ---------------- BOT ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif")

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(MessageHandler(filters.Regex(r'^/aktif'), aktif_sky))
    app.add_handler(MessageHandler(filters.Regex(r'^/pasif'), pasif_sky))
    app.add_handler(CommandHandler("start", start))

    app.run_polling(drop_pending_updates=True)
