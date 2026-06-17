import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.environ["BOT_TOKEN"]
ADMIN_IDS  = list(map(int, os.environ.get("ADMIN_IDS","").split(","))) if os.environ.get("ADMIN_IDS") else []
CHANNEL_ID = os.environ.get("CHANNEL_ID","")   # majburiy obuna kanali (ixtiyoriy)
DB_PATH    = "/app/data/movies.json"

os.makedirs("/app/data", exist_ok=True)

# ── DB ────────────────────────────────────────────────────
def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    return {"movies":{}}

def save_db(db):
    with open(DB_PATH,"w",encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

# ── Obuna ─────────────────────────────────────────────────
async def is_subscribed(uid, ctx):
    if not CHANNEL_ID: return True
    try:
        m = await ctx.bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ("member","administrator","creator")
    except: return True

def sub_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga obuna bo'l", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"),
        InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
    ]])

# ── /start ────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not await is_subscribed(u.id, ctx):
        await update.message.reply_text("⚠️ Botdan foydalanish uchun kanalga obuna bo'ling!", reply_markup=sub_kb())
        return
    kb = [
        [InlineKeyboardButton("🎬 Barcha kinolar", callback_data="all_movies")],
        [InlineKeyboardButton("🗂 Janr bo'yicha", callback_data="genres")],
    ]
    if u.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
    await update.message.reply_text(
        f"🎬 <b>Kino Botga Xush Kelibsiz!</b>\n\nSalom, {u.first_name}! 👋\n\nKino nomini yozing yoki menyudan tanlang:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)
    )

# ── Obuna callback ─────────────────────────────────────────
async def cb_check_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if await is_subscribed(q.from_user.id, ctx):
        await q.edit_message_text("✅ Rahmat! /start bosing.")
    else:
        await q.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)

# ── Barcha kinolar ─────────────────────────────────────────
async def cb_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db = load_db()
    if not db["movies"]:
        await q.edit_message_text("📭 Hozircha kinolar yo'q."); return
    btns = [[InlineKeyboardButton(f"🎬 {m['title']} ({m.get('year','?')})", callback_data=f"mv_{mid}")]
            for mid,m in list(db["movies"].items())[:20]]
    btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="home")])
    await q.edit_message_text("🎬 <b>Kinolar:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

# ── Janrlar ───────────────────────────────────────────────
async def cb_genres(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db = load_db()
    genres = sorted({m.get("genre","") for m in db["movies"].values() if m.get("genre")})
    if not genres:
        await q.edit_message_text("📭 Janrlar yo'q."); return
    btns = [[InlineKeyboardButton(g, callback_data=f"genre_{g}")] for g in genres]
    btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="home")])
    await q.edit_message_text("🗂 <b>Janr tanlang:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

async def cb_genre_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    genre = q.data[6:]
    db = load_db()
    filtered = {mid:m for mid,m in db["movies"].items() if m.get("genre")==genre}
    if not filtered:
        await q.edit_message_text(f"📭 '{genre}' janrida kino yo'q."); return
    btns = [[InlineKeyboardButton(f"🎬 {m['title']}", callback_data=f"mv_{mid}")] for mid,m in filtered.items()]
    btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="genres")])
    await q.edit_message_text(f"🗂 <b>{genre}</b>:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

# ── Kino detail ───────────────────────────────────────────
async def cb_movie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    mid = q.data[3:]
    db = load_db(); m = db["movies"].get(mid)
    if not m:
        await q.edit_message_text("❌ Topilmadi."); return
    txt = (f"🎬 <b>{m['title']}</b>\n"
           f"📅 Yil: {m.get('year','?')}\n"
           f"🎭 Janr: {m.get('genre','?')}\n\n"
           f"📝 {m.get('desc','Tavsif yoq')}")
    btns = [
        [InlineKeyboardButton("▶️ Ko'rish / Yuklab olish", callback_data=f"dl_{mid}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="all_movies")]
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

# ── Yuborish (file_id orqali) ─────────────────────────────
async def cb_download(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("⏳ Yuklanmoqda...")
    if not await is_subscribed(q.from_user.id, ctx):
        await q.message.reply_text("⚠️ Avval kanalga obuna bo'ling!", reply_markup=sub_kb()); return
    mid = q.data[3:]
    db = load_db(); m = db["movies"].get(mid)
    if not m:
        await q.message.reply_text("❌ Topilmadi."); return
    await ctx.bot.send_video(
        chat_id=q.from_user.id,
        video=m["file_id"],
        caption=f"🎬 <b>{m['title']}</b>",
        parse_mode="HTML",
        supports_streaming=True
    )

# ── Qidiruv ───────────────────────────────────────────────
async def search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_subscribed(update.effective_user.id, ctx):
        await update.message.reply_text("⚠️ Avval kanalga obuna bo'ling!", reply_markup=sub_kb()); return
    # Admin holatini tekshir
    state = ctx.user_data.get("state","")
    uid = update.effective_user.id
    if uid in ADMIN_IDS and state:
        await admin_collect(update, ctx); return
    txt = update.message.text.strip().lower()
    db = load_db()
    results = {mid:m for mid,m in db["movies"].items() if txt in m["title"].lower()}
    if not results:
        await update.message.reply_text(f"🔍 '<b>{update.message.text}</b>' topilmadi.", parse_mode="HTML"); return
    btns = [[InlineKeyboardButton(f"🎬 {m['title']} ({m.get('year','?')})", callback_data=f"mv_{mid}")]
            for mid,m in list(results.items())[:10]]
    await update.message.reply_text("🔍 Natijalar:", reply_markup=InlineKeyboardMarkup(btns))

# ── Admin panel ───────────────────────────────────────────
async def cb_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return
    db = load_db()
    btns = [
        [InlineKeyboardButton("➕ Kino qo'shish", callback_data="adm_add")],
        [InlineKeyboardButton("🗑 Kino o'chirish", callback_data="adm_del_list")],
        [InlineKeyboardButton("📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="home")],
    ]
    await q.edit_message_text(f"⚙️ <b>Admin Panel</b>\n\nJami: <b>{len(db['movies'])}</b> kino",
                              parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

async def cb_adm_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS: return
    ctx.user_data["state"] = "wait_video"
    await q.edit_message_text(
        "📤 <b>Kino qo'shish</b>\n\n"
        "Video faylni yuboring.\n"
        "<i>Eslatma: video Telegram serverida saqlanadi — disk kerak emas!</i>",
        parse_mode="HTML"
    )

async def cb_adm_del_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS: return
    db = load_db()
    if not db["movies"]:
        await q.edit_message_text("📭 O'chirish uchun kino yo'q."); return
    btns = [[InlineKeyboardButton(f"🗑 {m['title']}", callback_data=f"adm_del_{mid}")]
            for mid,m in db["movies"].items()]
    btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await q.edit_message_text("🗑 Qaysi kinoni o'chirasiz?", reply_markup=InlineKeyboardMarkup(btns))

async def cb_adm_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS: return
    mid = q.data[8:]
    db = load_db(); m = db["movies"].pop(mid, None)
    if m: save_db(db); await q.edit_message_text(f"✅ <b>{m['title']}</b> o'chirildi.", parse_mode="HTML")
    else: await q.edit_message_text("❌ Topilmadi.")

async def cb_adm_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db = load_db()
    genres = {}
    for m in db["movies"].values():
        g = m.get("genre","Boshqa"); genres[g] = genres.get(g,0)+1
    gtxt = "\n".join(f"  • {g}: {c}" for g,c in genres.items()) or "  —"
    await q.edit_message_text(
        f"📊 <b>Statistika</b>\n\nJami: <b>{len(db['movies'])}</b>\n\nJanrlar:\n{gtxt}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]])
    )

# ── Video qabul (admin) ───────────────────────────────────
async def recv_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS: return
    if ctx.user_data.get("state") != "wait_video": return
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ Video fayl yuboring."); return
    ctx.user_data["new"] = {"file_id": video.file_id}
    ctx.user_data["state"] = "wait_title"
    await update.message.reply_text("✅ Video qabul qilindi!\n\n🎬 <b>Kino nomini kiriting:</b>", parse_mode="HTML")

# ── Admin matn to'plash ───────────────────────────────────
async def admin_collect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.get("state","")
    txt = update.message.text.strip()
    if state == "wait_title":
        ctx.user_data["new"]["title"] = txt
        ctx.user_data["state"] = "wait_year"
        await update.message.reply_text("📅 <b>Yilni kiriting</b> (masalan: 2024):", parse_mode="HTML")
    elif state == "wait_year":
        ctx.user_data["new"]["year"] = txt
        ctx.user_data["state"] = "wait_genre"
        await update.message.reply_text("🎭 <b>Janrni kiriting</b> (masalan: Komediya):", parse_mode="HTML")
    elif state == "wait_genre":
        ctx.user_data["new"]["genre"] = txt
        ctx.user_data["state"] = "wait_desc"
        await update.message.reply_text("📝 <b>Qisqacha tavsif:</b>", parse_mode="HTML")
    elif state == "wait_desc":
        import uuid
        new = ctx.user_data["new"]
        new["desc"] = txt
        db = load_db()
        mid = str(uuid.uuid4())[:8]
        db["movies"][mid] = new
        save_db(db)
        ctx.user_data["state"] = None
        await update.message.reply_text(
            f"✅ <b>{new['title']}</b> qo'shildi!\n🆔 <code>{mid}</code>", parse_mode="HTML"
        )

# ── Home callback ─────────────────────────────────────────
async def cb_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("🎬 Barcha kinolar", callback_data="all_movies")],
        [InlineKeyboardButton("🗂 Janr bo'yicha", callback_data="genres")],
    ]
    if q.from_user.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
    await q.edit_message_text("🎬 <b>Asosiy menyu:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ── Main ──────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb_check_sub,    pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_all,          pattern="^all_movies$"))
    app.add_handler(CallbackQueryHandler(cb_genres,       pattern="^genres$"))
    app.add_handler(CallbackQueryHandler(cb_genre_filter, pattern="^genre_"))
    app.add_handler(CallbackQueryHandler(cb_movie,        pattern="^mv_"))
    app.add_handler(CallbackQueryHandler(cb_download,     pattern="^dl_"))
    app.add_handler(CallbackQueryHandler(cb_admin,        pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(cb_adm_add,      pattern="^adm_add$"))
    app.add_handler(CallbackQueryHandler(cb_adm_del_list, pattern="^adm_del_list$"))
    app.add_handler(CallbackQueryHandler(cb_adm_del,      pattern="^adm_del_"))
    app.add_handler(CallbackQueryHandler(cb_adm_stats,    pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(cb_home,         pattern="^home$"))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, recv_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    logger.info("Bot ishga tushdi (file_id rejimi)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
