import ssl
import aiohttp
import json
import re
from datetime import datetime, timedelta
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ---------------- PANEL CONFIG ---------------- #

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

# ---------------- USERS ---------------- #

with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(USERS, f, indent=4, ensure_ascii=False)

def load_devirs():
    try:
        with open("devir.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ---------------- ADMIN ---------------- #

def is_admin(user_id: int):
    admin_ids = os.environ.get("ADMIN_IDS", "").split(",")
    admin_ids = [int(i.strip()) for i in admin_ids if i.strip()]
    return user_id in admin_ids

# ---------------- NUMBER PARSER ---------------- #

def extract_number(text: str):
    match = re.search(r'(\d+)', text)
    return match.group(1) if match else None

# ---------------- SKY SYSTEM ---------------- #

async def aktif_sky(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sadece admin")
            return

        num = extract_number(update.message.text)
        if not num:
            await update.message.reply_text("❌ Numara yok")
            return

        key = f"SKY{num}"

        if key not in USERS:
            await update.message.reply_text("❌ Kullanıcı yok")
            return

        USERS[key]["havale_alim"] = 1
        save_users()

        await update.message.reply_text(f"✅ {key} AKTİF")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

async def pasif_sky(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sadece admin")
            return

        num = extract_number(update.message.text)
        if not num:
            await update.message.reply_text("❌ Numara yok")
            return

        key = f"SKY{num}"

        if key not in USERS:
            await update.message.reply_text("❌ Kullanıcı yok")
            return

        USERS[key]["havale_alim"] = 0
        save_users()

        await update.message.reply_text(f"❌ {key} PASİF")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

# ---------------- PANEL FETCH ---------------- #

async def fetch_user_amount(panel_config, user_uuid):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_config['url']}/login"
    reports_url = f"{panel_config['url']}/reports/quickly"

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        async with session.get(login_url) as r:
            text = await r.text()

        token = ""
        for line in text.splitlines():
            if 'name="_token"' in line:
                token = line.split('value="')[1].split('"')[0]
                break

        await session.post(login_url, data={
            "_token": token,
            "email": panel_config['username'],
            "password": panel_config['password']
        })

        async with session.get(reports_url) as r:
            text = await r.text()

        csrf = ""
        for line in text.splitlines():
            if 'csrf-token' in line:
                csrf = line.split('content="')[1].split('"')[0]
                break

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": csrf, "Content-Type": "application/json"},
            json={"site": "", "dateone": today, "datetwo": today, "bank": "", "user": user_uuid}
        ) as r:
            data = await r.json()

        return (
            float(data.get("deposit", [0])[0] or 0),
            float(data.get("withdraw", [0])[0] or 0),
            float(data.get("delivery", [0, 0])[1] or 0)
        )

# ---------------- KASA ---------------- #

async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Yükleniyor...")

    try:
        command = update.message.text.lstrip("/").upper()
        username = command.replace("KASA", "SKY")

        if username not in USERS:
            await msg.edit_text("Kullanıcı yok")
            return

        def tr(x): return f"{int(x):,}".replace(",", ".")

        info = USERS[username]

        dep, wd, dlv = await fetch_user_amount(PANELS[info["panel"]], info["uuid"])

        commission = dep * 0.025
        net = dep - wd - dlv - commission

        devirs = load_devirs()
        devir = float(devirs.get(username, 0))

        total = net + devir

        await msg.edit_text(
            f"{username} KASA\n"
            f"Yatırım: {tr(dep)}\n"
            f"Çekim: {tr(wd)}\n"
            f"Teslimat: {tr(dlv)}\n"
            f"Komisyon: {tr(commission)}\n"
            f"Net: {tr(net)}\n"
            f"Devir: {tr(devir)}\n"
            f"TOPLAM: {tr(total)}"
        )

    except Exception as e:
        await msg.edit_text(f"Hata: {e}")

# ---------------- SIMPLE ---------------- #

async def gunceladres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("OK")

# ---------------- FORWARD ---------------- #

BOT_USERNAME = os.environ.get("BOT_USERNAME")

HEDEF_GRUPLAR = [
    int(x) for x in os.environ.get("TARGET_GROUPS", "").split(",") if x.strip()
]

async def forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    text = msg.text or msg.caption or ""

    if not BOT_USERNAME or BOT_USERNAME.lower() not in text.lower():
        return

    for hedef in HEDEF_GRUPLAR:
        try:
            if msg.text:
                await context.bot.send_message(hedef, msg.text)
            else:
                await context.bot.copy_message(hedef, msg.chat_id, msg.message_id)
        except:
            pass

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # kasa
    app.add_handler(MessageHandler(filters.Regex(r'^/kasa\d+$'), kasa))

    # aktif pasif (HER FORMAT)
    app.add_handler(MessageHandler(filters.Regex(r'^/aktif'), aktif_sky))
    app.add_handler(MessageHandler(filters.Regex(r'^/pasif'), pasif_sky))

    app.add_handler(CommandHandler("gunceladres", gunceladres))

    app.add_handler(MessageHandler(filters.ALL, forward_handler))

    app.run_polling(drop_pending_updates=True)
