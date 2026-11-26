
import os
import sqlite3
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

db = sqlite3.connect("zadx.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    last_daily TEXT
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    invited INTEGER PRIMARY KEY,
    inviter INTEGER
)
""")
db.commit()

PRODUCTS = {
    1: ("تصميم منشور", 100),
    2: ("تصميم شعار", 250),
    3: ("خدمة ترويج حقيقية", 500),
}

def register(user_id):
    db.execute(
        "INSERT OR IGNORE INTO users (id, points) VALUES (?, 0)",
        (user_id,)
    )
    db.commit()

def balance(user_id):
    if user_id == OWNER_ID:
        return "∞"
    row = db.execute(
        "SELECT points FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    return row[0] if row else 0

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 رصيدي", callback_data="balance")],
        [InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily")],
        [InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="invite")],
        [InlineKeyboardButton("🛍️ المتجر", callback_data="shop")],
        [InlineKeyboardButton("👑 الإدارة", callback_data="admin")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    register(uid)

    if context.args:
        try:
            inviter = int(context.args[0])
            if inviter != uid:
                exists = db.execute(
                    "SELECT invited FROM referrals WHERE invited=?",
                    (uid,)
                ).fetchone()

                if not exists:
                    register(inviter)
                    db.execute(
                        "INSERT INTO referrals VALUES (?, ?)",
                        (uid, inviter)
                    )
                    db.execute(
                        "UPDATE users SET points=points+20 WHERE id=?",
                        (inviter,)
                    )
                    db.commit()
        except ValueError:
            pass

    await update.message.reply_text(
        "👑 مرحباً بك في ZADX POINTS STORE\n\n"
        f"🪙 رصيدك: {balance(uid)} نقطة\n\n"
        "اختر من القائمة:",
        reply_markup=menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    register(uid)
    action = query.data

    if action == "balance":
        await query.edit_message_text(
            f"🪙 رصيدك: {balance(uid)} نقطة",
            reply_markup=menu()
        )

    elif action == "daily":
        today = str(date.today())
        row = db.execute(
            "SELECT last_daily FROM users WHERE id=?",
            (uid,)
        ).fetchone()

        if row[0] == today:
            msg = "⏳ لقد أخذت مكافأتك اليوم. عُد غداً!"
        else:
            if uid != OWNER_ID:
                db.execute(
                    "UPDATE users SET points=points+10, last_daily=? WHERE id=?",
                    (today, uid)
                )
            else:
                db.execute(
                    "UPDATE users SET last_daily=? WHERE id=?",
                    (today, uid)
                )
            db.commit()
            msg = "🎉 حصلت على 10 نقاط!"

        await query.edit_message_text(msg, reply_markup=menu())

    elif action == "invite":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"
        await query.edit_message_text(
            "👥 ادعُ أصدقاءك إلى البوت!\n\n"
            "🎁 تحصل على 20 نقطة عن كل صديق جديد.\n\n"
            f"رابط دعوتك:\n{link}",
            reply_markup=menu()
        )

    elif action == "shop":
        keyboard = []
        for pid, (name, price) in PRODUCTS.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} — {price} نقطة",
                    callback_data=f"buy:{pid}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("🔙 الرئيسية", callback_data="home")
        ])
        await query.edit_message_text(
            "🛍️ متجر ZADX\nاختر الخدمة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action.startswith("buy:"):
        pid = int(action.split(":")[1])
        if pid not in PRODUCTS:
            return
        name, price = PRODUCTS[pid]

        if uid != OWNER_ID:
            row = db.execute(
                "SELECT points FROM users WHERE id=?",
                (uid,)
            ).fetchone()

            if row[0] < price:
                await query.edit_message_text(
                    "❌ نقاطك غير كافية!",
                    reply_markup=menu()
                )
                return

            db.execute(
                "UPDATE users SET points=points-? WHERE id=?",
                (price, uid)
            )
            db.commit()

        await query.edit_message_text(
            f"✅ تم تسجيل طلبك!\n\n"
            f"الخدمة: {name}\n"
            f"السعر: {price} نقطة\n"
            "تواصل مع الإدارة لإتمام الخدمة.",
            reply_markup=menu()
        )

        if OWNER_ID:
            await context.bot.send_message(
                OWNER_ID,
                f"📦 طلب جديد!\nالمستخدم: {uid}\nالخدمة: {name}"
            )

    elif action == "admin":
        if uid != OWNER_ID:
            await query.answer("هذه القائمة خاصة بالمالك 👑", show_alert=True)
            return

        await query.edit_message_text(
            "👑 لوحة المالك\n\n"
            "🪙 رصيدك: ∞\n"
            "➕ لإضافة نقاط:\n"
            "/addpoints USER_ID AMOUNT\n"
            "مثال: /addpoints 123456789 100",
            reply_markup=menu()
        )

    elif action == "home":
        await query.edit_message_text(
            "👑 ZADX POINTS STORE\nاختر من القائمة:",
            reply_markup=menu()
        )

async def addpoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "استعمل:\n/addpoints USER_ID AMOUNT"
        )
        return

    try:
        target = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError

        register(target)
        db.execute(
            "UPDATE users SET points=points+? WHERE id=?",
            (amount, target)
        )
        db.commit()

        await update.message.reply_text(
            f"✅ تمت إضافة {amount} نقطة للمستخدم {target}"
        )
    except ValueError:
        await update.message.reply_text("❌ تحقق من الأرقام.")

async def main():
    if not TOKEN or not OWNER_ID:
        raise RuntimeError("Set BOT_TOKEN and OWNER_ID first")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpoints", addpoints))
    app.add_handler(CallbackQueryHandler(buttons))

    print("ZADX POINTS STORE is running!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
