import ssl
import aiohttp
import json
import re
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
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

def is_admin(user_id):
    admin_ids = os.environ.get("ADMIN_IDS", "").split(",")
    return str(user_id) in admin_ids

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

# ---------------- PARSE SKY ---------------- #

def parse_user(text):
    text = text.upper().replace("/", "")
    text = text.replace("AKTIF", "").replace("PASIF", "")
    text = text.replace("SKY", "")
    num = re.search(r"\d+", text)
    return num.group() if num else None

# ---------------- PANEL LOGIN + UPDATE ---------------- #

async def update_panel(panel, uuid, value):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    base = panel["url"]

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:

        # LOGIN
        async with session.get(f"{base}/login") as r:
            html = await r.text()

        token = ""
        for line in html.splitlines():
            if 'name="_token"' in line:
                token = line.split('value="')[1].split('"')[0]
                break

        await session.post(f"{base}/login", data={
            "_token": token,
            "email": panel["username"],
            "password": panel["password"]
        })

        # PATCH UPDATE
        url = f"{base}/users/{uuid}"

        await session.post(url, data={
            "_method": "PATCH",
            "_token": token,
            "havale_alim": str(value)
        })

# ---------------- COMMAND HANDLER ---------------- #

async def aktif_pasif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin değil")
            return

        text = update.message.text.upper()

        value = 1 if "AKTIF" in text else 0

        num = parse_user(text)
        if not num:
            await update.message.reply_text("❌ Kullanıcı bulunamadı")
            return

        key = f"SKY{num}"

        if key not in USERS:
            await update.message.reply_text("❌ SKY kullanıcı yok")
            return

        user = USERS[key]

        # JSON update
        USERS[key]["havale_alim"] = value
        save_users()

        # PANEL update
        await update_panel(PANELS[user["panel"]], user["uuid"], value)

        await update.message.reply_text(f"✅ {key} {'AKTİF' if value==1 else 'PASİF'}")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r'^(\/)?(aktif|pasif)'), aktif_pasif))

    app.run_polling(drop_pending_updates=True)
