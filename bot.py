#!/usr/bin/env python3
"""
Charlotte On The Run — Telegram event bot.

Only shows events happening now (started ≤1h ago) or in the future.
Events with extracted dates are sorted soonest-first; recent undated
articles appear after them.

Commands
────────
/events      All upcoming events across all regions
/today       Events happening today
/tonight     Tonight's events (5 PM onward)
/weekend     This Friday–Sunday
/nearby      Charlotte metro & suburbs (≤30 min drive)
/free        Free events, all regions
/charlotte   Charlotte metro
/triad       Greensboro / Winston-Salem
/greenville  Greenville SC
/asheville   Asheville / WNC
/triangle    Raleigh / Durham / Chapel Hill
/search <kw> Search by keyword in title or description
/stats       Database stats and last fetch time
/refresh     Manually trigger a feed fetch  (owner only)
/help        Show this list
"""

import os
from html import escape

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import asyncio
import logging
from datetime import datetime, date as date_t, timezone, timedelta
from fetcher import query_events, get_stats, run_fetch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
    from telegram.constants import ParseMode
except ImportError:
    raise SystemExit("Run: pip install python-telegram-bot>=20.0")

TOKEN    = os.environ["TELEGRAM_TOKEN"]
OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))

# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_date(event_date: str | None, event_time: str | None, pub_date: str | None) -> str:
    parts = []
    if event_date:
        try:
            d = date_t.fromisoformat(event_date)
            today = date_t.today()
            if d == today:
                day_label = "Today"
            elif d == today + timedelta(days=1):
                day_label = "Tomorrow"
            else:
                day_label = d.strftime("%a %b %-d")
            parts.append(f"🗓 {day_label}")
        except ValueError:
            pass
    if event_time:
        try:
            h, mi = map(int, event_time.split(":"))
            suffix = "AM" if h < 12 else "PM"
            h12    = h % 12 or 12
            parts.append(f"⏰ {h12}:{mi:02d} {suffix}" if mi else f"⏰ {h12} {suffix}")
        except ValueError:
            pass
    if not parts and pub_date:
        try:
            dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            parts.append(f"📰 posted {dt.strftime('%b %-d')}")
        except ValueError:
            pass
    return "  ".join(parts)


def _esc(value: object) -> str:
    return escape("" if value is None else str(value), quote=False)

def fmt_event(e: dict, i: int) -> str:
    title = _esc(e["title"][:85])
    region = _esc(e["region"])
    price = f"  💰 {_esc(e['price'])}" if e.get("price") else ""
    source = _esc(e["source"])
    date_line = _fmt_date(e.get("event_date"), e.get("event_time"), e.get("pub_date"))
    link = f"\n   🔗 {_esc(e['link'])}" if e.get("link") else ""
    date_part = f"\n   {_esc(date_line)}" if date_line else ""
    return (
        f"<b>{i}. {title}</b>\n"
        f"   📍 {region}{price}{date_part}\n"
        f"   <i>{source}</i>{link}"
    )

def fmt_list(events: list[dict], header: str) -> str:
    if not events:
        return (
            f"<b>{_esc(header)}</b>\n\n"
            "No events found matching that filter.\n"
            "Try /refresh to pull the latest feeds, or broaden your search."
        )
    lines = [f"<b>{_esc(header)}</b> - {len(events)} result{'s' if len(events) != 1 else ''}\n"]
    for i, e in enumerate(events, 1):
        lines.append(fmt_event(e, i))
        lines.append("")
    return "\n".join(lines)

async def send_chunked(update: Update, text: str):
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if current and len(candidate) > 4000:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(
            chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

# ── Helpers ───────────────────────────────────────────────────────────────────

def _weekend_label() -> str:
    today   = date_t.today()
    weekday = today.weekday()
    sat = today + timedelta(days=(5 - weekday) % 7)
    sun = sat + timedelta(days=1)
    fri = sat - timedelta(days=1)
    return f"{fri.strftime('%b %-d')}–{sun.strftime('%b %-d')}"

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today   = date_t.today().strftime("%A, %B %-d")
    weekend = _weekend_label()
    msg = (
        f"<b>Charlotte On The Run</b> 🎟\n"
        f"<i>{today} · upcoming events only</i>\n\n"

        "<b>By time</b>\n"
        "/events — Everything coming up, all regions\n"
        "/today — Only events happening today\n"
        "/tonight — Tonight from 5 PM onward\n"
        f"/weekend — This weekend ({weekend})\n\n"

        "<b>By place</b>\n"
        "/nearby — Charlotte metro & suburbs (≤30 min)\n"
        "/charlotte — Charlotte\n"
        "/triad — Greensboro / Winston-Salem\n"
        "/greenville — Greenville SC\n"
        "/asheville — Asheville / WNC\n"
        "/triangle — Raleigh / Durham / Chapel Hill\n\n"

        "<b>Filter</b>\n"
        "/free — Free events anywhere in range\n"
        "/search <code>&lt;word&gt;</code> — Search titles and descriptions\n\n"

        "<b>Info</b>\n"
        "/stats — Event counts and last fetch time\n"
        "/refresh — Re-pull all feeds <i>(owner only)</i>\n\n"

        "<i>Only shows events that haven't started yet, or started in the last hour.</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def cmd_events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(limit=12)
    await send_chunked(update, fmt_list(events, "Upcoming events — all regions"))

async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(date_filter="today", limit=12)
    label  = date_t.today().strftime("%A %b %-d")
    await send_chunked(update, fmt_list(events, f"Today — {label}"))

async def cmd_tonight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(date_filter="tonight", limit=12)
    await send_chunked(update, fmt_list(events, "Tonight (5 PM onward)"))

async def cmd_weekend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(date_filter="weekend", limit=15)
    await send_chunked(update, fmt_list(events, f"Weekend — {_weekend_label()}"))

async def cmd_nearby(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(distance_max="30min", limit=12)
    await send_chunked(update, fmt_list(events, "Nearby — Charlotte & suburbs (≤30 min)"))

async def cmd_free(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(free_only=True, limit=12)
    await send_chunked(update, fmt_list(events, "Free events — all regions"))

async def cmd_charlotte(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(region="Charlotte", limit=12)
    await send_chunked(update, fmt_list(events, "Charlotte metro"))

async def cmd_triad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(region="Triad", limit=12)
    await send_chunked(update, fmt_list(events, "Piedmont Triad"))

async def cmd_greenville(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(region="Greenville", limit=12)
    await send_chunked(update, fmt_list(events, "Greenville SC"))

async def cmd_asheville(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(region="Asheville", limit=12)
    await send_chunked(update, fmt_list(events, "Asheville / WNC"))

async def cmd_triangle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    events = query_events(region="Triangle", limit=12)
    await send_chunked(update, fmt_list(events, "Triangle NC"))

async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kw = " ".join(ctx.args).strip()
    if not kw:
        await update.message.reply_text("Usage: /search <keyword>\nExample: /search jazz")
        return
    events = query_events(keyword=kw, limit=12)
    await send_chunked(update, fmt_list(events, f'Search: "{kw}"'))

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    lines = [
        "<b>DB Stats</b> 📊\n",
        f"Total events: <b>{s['total']}</b>  ({s['dated']} with specific dates)",
        f"Last fetch: <code>{_esc(s['last_fetch'])}</code> (+{s['last_new']} new)\n",
        "<b>By region:</b>",
    ]
    for region, cnt in s["by_region"]:
        lines.append(f"  {_esc(region)}: {cnt}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def cmd_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Owner-only command.")
        return
    await update.message.reply_text("Fetching feeds… (~30 sec)")
    try:
        totals = await asyncio.get_event_loop().run_in_executor(None, run_fetch)
        await update.message.reply_text(
            f"Done. +{totals['new']} new  "
            f"{totals['skipped']} skipped  "
            f"{totals['dropped']} dropped  "
            f"{totals['errors']} errors"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Try /help")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",      cmd_help))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("events",     cmd_events))
    app.add_handler(CommandHandler("today",      cmd_today))
    app.add_handler(CommandHandler("tonight",    cmd_tonight))
    app.add_handler(CommandHandler("weekend",    cmd_weekend))
    app.add_handler(CommandHandler("nearby",     cmd_nearby))
    app.add_handler(CommandHandler("free",       cmd_free))
    app.add_handler(CommandHandler("charlotte",  cmd_charlotte))
    app.add_handler(CommandHandler("triad",      cmd_triad))
    app.add_handler(CommandHandler("greenville", cmd_greenville))
    app.add_handler(CommandHandler("asheville",  cmd_asheville))
    app.add_handler(CommandHandler("triangle",   cmd_triangle))
    app.add_handler(CommandHandler("search",     cmd_search))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("refresh",    cmd_refresh))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    log.info("Bot started.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
