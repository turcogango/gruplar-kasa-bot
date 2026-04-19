import ssl
import aiohttp
import json
from datetime import datetime, timedelta
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

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

with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

def load_devirs():
    try:
        with open("devir.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

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

        deposit_total = float(data.get("deposit", [0])[0] or 0)
        withdraw_total = float(data.get("withdraw", [0])[0] or 0)
        delivery_total = float(data.get("delivery", [0, 0])[1] or 0)

        net = deposit_total - withdraw_total - delivery_total

        return deposit_total, withdraw_total, delivery_total, net


async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Kasa verileri alınıyor...")

    try:
        admin_ids = os.environ.get("ADMIN_IDS", "").split(",")
        admin_ids = [int(i.strip()) for i in admin_ids if i.strip()]

        user_id = update.effective_user.id
        if user_id not in admin_ids:
            await msg.edit_text("Bu komutu sadece adminler kullanabilir.")
            return

        command = update.message.text.lstrip("/").upper()
        username = command.replace("KASA", "SKY")

        if username not in USERS:
            await msg.edit_text("Kullanıcı bulunamadı.")
            return

        def tr(x):
            return f"{int(x):,}".replace(",", ".")

        info = USERS[username]
        panel = info["panel"]
        uuid = info["uuid"]

        deposit_total, withdraw_total, delivery_total, net = await fetch_user_amount(
            PANELS[panel], uuid
        )

        devirs = load_devirs()
        devir = float(devirs.get(username, 0))

        total = net + devir

        await msg.edit_text(
            f"{username} KASA\n"
            f"Yatırım: {tr(deposit_total)} TL\n"
            f"Çekim: {tr(withdraw_total)} TL\n"
            f"Teslimat: {tr(delivery_total)} TL\n"
            f"Net: {tr(net)} TL\n"
            f"Devir: {tr(devir)} TL\n"
            f"TOPLAM: {tr(total)} TL"
        )

    except Exception as e:
        await msg.edit_text(f"Hata oluştu:\n{e}")


async def gunceladres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H")


async def gandalf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("")


async def esref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("")


if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bulunamadı")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r'^/kasa\d+$'), kasa))
    app.add_handler(CommandHandler("gunceladres", gunceladres))
    app.add_handler(CommandHandler("gandalf", gandalf))
    app.add_handler(CommandHandler("esref", esref))

    app.run_polling()
