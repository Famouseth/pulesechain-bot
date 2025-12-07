import os
import logging
from decimal import Decimal
import aiohttp
from web3 import Web3
from web3.middleware import geth_poa_middleware
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

w3 = Web3(Web3.HTTPProvider("https://rpc.scan.pulsechain.com"))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

FACTORY = w3.to_checksum_address("0x1715a3E5a14588b3E3C6b5f7A366a4340338dF21")
WPLS = w3.to_checksum_address("0xA1077a294dDE1B09bB078844df40758a5D0f9a27")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Nuclear Bot v6 LIVE on Render!\nSend any 0x address → instant reply",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Check Token", callback_data="c")]])
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.startswith("0x") or len(text) != 42:
        await update.message.reply_text("Invalid")
        return
    msg = await update.message.reply_text("Loading…")
    token = w3.to_checksum_address(text)
    try:
        pair = w3.eth.contract(address=FACTORY, abi=[{"inputs":[{"type":"address"},{"type":"address"}],"name":"getPair","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"}]).functions.getPair(token, WPLS).call()
        reserves = w3.eth.contract(address=pair, abi=[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112"},{"type":"uint112"},{"type":"uint32"}],"stateMutability":"view","type":"function"}]).functions.getReserves().call()
        token0 = w3.eth.contract(address=pair, abi=[{"inputs":[],"name":"token0","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"}]).functions.token0().call()
        price = (Decimal(reserves[1 if token0 == WPLS else 0]) / Decimal(reserves[0 if token0 == WPLS else 1])) * Decimal("0.0000082")
        name = w3.eth.contract(address=token, abi=[{"inputs":[],"name":"name","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"}]).functions.name().call()
        symbol = w3.eth.contract(address=token, abi=[{"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"}]).functions.symbol().call()
    except:
        price, name, symbol = 0, "Unknown", "???"
    price_str = f"${float(price):,.10f}".rstrip("0").rstrip(".") if price > 0 else "No liquidity"
    await msg.edit_text(
        f"*{name} ({symbol})*\n`{token}`\nPrice: {price_str}\n[Trade](https://app.pulsex.com/swap?outputCurrency={token})",
        parse_mode="Markdown", disable_web_page_preview=True
    )

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check))
app.run_polling()
