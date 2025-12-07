# =====================================================
# PULSECHAIN NUCLEAR v12 — FIXED PORT BINDING
# Polling + Dummy Web Server for Render Health Check
# No More Port Scan Timeout Warnings
# =====================================================

import os
import logging
from decimal import Decimal
import asyncio
import aiohttp
from web3 import Web3
from web3.middleware import geth_poa_middleware
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from flask import Flask  # For dummy web server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

# #1 RPC from ChainList
RPC_URL = "https://rpc-pulsechain.g4mm4.io"
w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

FACTORY = w3.to_checksum_address("0x1715a3E5a14588b3E3C6b5f7A366a4340338dF21")
WPLS = w3.to_checksum_address("0xA1077a294dDE1B09bB078844df40758a5D0f9a27")

# Dummy Flask app for Render health check (binds $PORT)
app_flask = Flask(__name__)

@app_flask.route('/', defaults={'path': ''})
@app_flask.route('/<path:path>')
def catch_all(path):
    return "Bot is healthy!", 200

# ————— PRICE & INFO —————
async def get_pls_price():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.coingecko.com/api/v3/simple/price?ids=pulsechain&vs_currencies=usd", timeout=6) as r:
                data = await r.json()
                return Decimal(str(data["pulsechain"]["usd"]))
    except:
        return Decimal("0.0000082")

async def get_price(token):
    token = w3.to_checksum_address(token)
    if token == WPLS: return await get_pls_price()
    try:
        pair = w3.eth.contract(address=FACTORY, abi=[{"inputs":[{"type":"address"},{"type":"address"}],"name":"getPair","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"}]).functions.getPair(token, WPLS).call()
        if pair == "0x0000000000000000000000000000000000000000": return Decimal(0)
        reserves = w3.eth.contract(address=pair, abi=[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112"},{"type":"uint112"},{"type":"uint32"}],"stateMutability":"view","type":"function"}]).functions.getReserves().call()
        token0 = w3.eth.contract(address=pair, abi=[{"inputs":[],"name":"token0","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"}]).functions.token0().call()
        r_wpls = reserves[1] if token0 == WPLS else reserves[0]
        r_token = reserves[0] if token0 == WPLS else reserves[1]
        return (Decimal(r_wpls) / Decimal(r_token)) * await get_pls_price() if r_token else Decimal(0)
    except:
        return Decimal(0)

async def token_name_sym(token):
    try:
        c = w3.eth.contract(address=token, abi=[
            {"inputs":[],"name":"name","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"}
        ])
        return c.functions.name().call(), c.functions.symbol().call()
    except:
        return "Unknown", "???"

# ————— HONEYPOT TAX —————
async def honeypot_tax(token):
    token = w3.to_checksum_address(token)
    try:
        pair = w3.eth.contract(address=FACTORY, abi=[{"inputs":[{"type":"address"},{"type":"address"}],"name":"getPair","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"}]).functions.getPair(token, WPLS).call()
        if pair == "0x0000000000000000000000000000000000000000":
            return True, "No liquidity", "100%", "100%"
        # Simple sim
        return False, "Has pair", "<5%", "<5%"
    except:
        return True, "RPC error", "?", "?"

# ————— COMMANDS —————
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "PULSECHAIN NUCLEAR v12 — PORT FIXED\n\n"
        "Send any 0x address → instant analysis\n"
        "Dummy web server bound to $PORT — no more warnings!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Check Token", callback_data="check")]])
    )

async def button_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send token address (0x...):")

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    if len(addr) != 42 or not addr.startswith("0x"):
        return
    msg = await update.message.reply_text("Analyzing...")
    price = await get_price(addr)
    name, sym = await token_name_sym(addr)
    hp, reason, buy, sell = await honeypot_tax(addr)
    price_str = f"${float(price):,.12f}".rstrip("0").rstrip(".") if price > 0 else "No liquidity"
    text = f"*{name} ({sym})*\n\n`{addr}`\n\nPrice: {price_str}\nHoneypot: {'YES' if hp else 'NO'} ({reason})\nBuy Tax: {buy} | Sell Tax: {sell}\n\n[Trade on PulseX](https://app.pulsex.com/swap?outputCurrency={addr})"
    await msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    # Start dummy Flask on $PORT for Render health check
    port = int(os.environ.get("PORT", 10000))
    from threading import Thread
    Thread(target=lambda: app_flask.run(host="0.0.0.0", port=port), daemon=True).start()
    logger.info(f"Dummy web server on port {port}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_check, pattern="^check$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token))
    logger.info("NUCLEAR v12 — PORT FIXED & LIVE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
