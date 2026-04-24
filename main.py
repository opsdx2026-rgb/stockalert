import asyncio
import aiohttp
import numpy as np
import os
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN","8726552111:AAGPZ-DlKsfF4uP57OIK3k7mpWO8QjOCjbs")
CHAT_ID = os.getenv("CHAT_ID","8495972050")

WIB = pytz.timezone("Asia/Jakarta")

# =========================
# TELEGRAM
# =========================
async def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, data={"chat_id": CHAT_ID, "text": msg})

# =========================
# STOCK LIST
# =========================
def get_all_tickers():
    return [
        "BBRI","TLKM","BMRI","BBCA","ASII","MDKA","ANTM","GOTO","ADRO","UNTR",
        "ITMG","PGAS","INDF","ICBP","SMGR","CPIN","JPFA","ERAA","ACES","BRIS",
        "ESSA","HRUM","MEDC","PTBA","TINS","UNVR","SIDO","WSKT","WIKA","BULL",
        "BRMS","BREN","CUAN","ARTO","AMMN","HEAL","MIKA","SILO","KLBF","INCO",
        "LSIP","AALI","TBIG","TOWR","EXCL","ISAT","FREN","PGEO","MAPA","MAPI",
        "UNIQ","DSSA","INDY","DOID","MBAP","DEWA","ELSA","RAJA","SRTG","BUKA",
        "NCKL","ADMR","SMRA","PWON","CTRA","BSDE","KIJA","DMAS","HMSP","GGRM",
        "INDX","BABY","AKSI","MANG","BUVA","MINA","BUMI","COIN","CDIA","PTRO",
        "AKSI","BESS","BBSS","FOLK","WIFI","INET","RATU","COAL","HOPE","NIKL",
        "EMAS","GTSI","HUMI","TOBA","OASA","KPIG","MSIN","MSKY","BINO","BPTR",
        "NICE","BIKE","ISAT","KOBX","JAYA","KAQI","TRIN","TRUE","NZIA","IRSX",
    ]

# =========================
# FETCH DATA
# =========================
async def fetch_stock(session, stock):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock}.JK?range=1d&interval=5m"
    try:
        async with session.get(url, timeout=5) as resp:
            data = await resp.json()
            result = data["chart"]["result"][0]

            closes = result["indicators"]["quote"][0]["close"]
            volumes = result["indicators"]["quote"][0]["volume"]

            return {
                "stock": stock,
                "price": closes[-1],
                "prev": closes[-2],
                "volume": volumes[-1],
                "avg_volume": np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[-1],
                "closes": closes
            }
    except:
        return None

# =========================
# RSI
# =========================
def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50
    deltas = np.diff(prices)
    gain = np.maximum(deltas, 0)
    loss = -np.minimum(deltas, 0)

    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =========================
# SESSION ANALYSIS
# =========================
def analyze(d, session):
    price = d["price"]
    prev = d["prev"]

    change = ((price - prev) / prev) * 100
    vol_ratio = d["volume"] / d["avg_volume"] if d["avg_volume"] else 1
    rsi = calculate_rsi(d["closes"])

    score = 0
    category = ""

    # SESSION LOGIC
    if session == "PRE":
        if vol_ratio > 1.2:
            score += 2
        if 45 < rsi < 65:
            score += 2
        category = "📊 WATCHLIST"

    elif session == "OPEN":
        if change > 3:
            score += 3
        if vol_ratio > 2:
            score += 3
        category = "🚀 BREAKOUT"

    elif session == "MID":
        if 50 < rsi < 70:
            score += 3
        if vol_ratio > 1.5:
            score += 2
        category = "🛡️ CONTINUATION"

    elif session == "CLOSE":
        if rsi > 70 or rsi < 30:
            score += 3
        if vol_ratio > 1.5:
            score += 2
        category = "⚡ REVERSAL"

    entry = price * 1.01
    tp = entry * 1.04
    sl = entry * 0.97

    return {
        "stock": d["stock"],
        "price": round(price),
        "entry": round(entry),
        "tp": round(tp),
        "sl": round(sl),
        "score": score,
        "category": category,
        "change": round(change, 2),
        "vol": round(vol_ratio, 2),
        "rsi": round(rsi, 1)
    }

# =========================
# RUN BOT
# =========================
async def run_bot(session):
    tickers = get_all_tickers()

    async with aiohttp.ClientSession() as session_http:
        tasks = [fetch_stock(session_http, t) for t in tickers]
        data = await asyncio.gather(*tasks)

    data = [d for d in data if d]

    # TOP 100 VOLUME
    top_volume = sorted(data, key=lambda x: x["volume"], reverse=True)[:100]

    results = [analyze(d, session) for d in top_volume]
    results = [r for r in results if r["score"] >= 4]
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:6]

    now = datetime.now(WIB).strftime("%H:%M WIB")

    msg = f"📊 SESSION SIGNAL ({session})\n⏰ {now}\n\n"

    for r in results:
        msg += f"{r['category']} {r['stock']}\n"
        msg += f"Price: {r['price']:,}\n"
        msg += f"Entry: {r['entry']}\n"
        msg += f"TP: {r['tp']}\n"
        msg += f"SL: {r['sl']}\n"
        msg += f"Δ: {r['change']}% | Vol: {r['vol']}x | RSI: {r['rsi']}\n\n"

    if results:
        await send_telegram(msg)

# =========================
# SCHEDULER
# =========================
async def scheduler():
    schedule_map = {
        "08:30": "PRE",
        "09:30": "OPEN",
        "14:00": "MID",
        "15:30": "CLOSE"
    }

    while True:
        now = datetime.now(WIB)
        time_str = now.strftime("%H:%M")
        weekday = now.weekday()

        if weekday < 5 and time_str in schedule_map:
            session = schedule_map[time_str]
            print(f"Running {session} session")
            await run_bot(session)
            await asyncio.sleep(60)

        await asyncio.sleep(20)

# =========================
# START
# =========================
asyncio.run(scheduler())
