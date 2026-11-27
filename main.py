
import os
import sqlite3
import asyncio
from datetime import date, datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

db = sqlite3.connect("zadx.db", check_same_thread=False)

# =========================
# DATABASE
# =========================

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

db.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product TEXT NOT NULL,
    price INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT
)
""")

db.commit()

# =========================
# PRODUCTS
# =========================

PRODUCTS = {
    1: ("تصميم منشور", 100),
    2: ("تصميم شعار", 250),
    3: ("خدمة ترويج حقيقية", 500),
}

FF_PACKS = {
    1: ("100 جوهرة", 1000),
    2: ("310 جوهرة", 2500),
    3: ("520 جوهرة", 4000),
    4: ("1060 جوهرة", 8000),
}

# =========================
# HELPERS
# =========================

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


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
    ])


# =========================
# START
# =========================

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

    context.user_data.pop("waiting_player_id", None)

    await update.message.reply_text(
        "👑 مرحباً بك في ZADX POINTS STORE\n\n"
        f"🪙 رصيدك: {balance(uid)} نقطة\n\n"
        "اختر من القائمة:",
        reply_markup=menu()
    )


# =========================
# SHOP
# =========================

async def show_shop(query):

    keyboard = []

    for pid, (name, price) in PRODUCTS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{name} — {price} نقطة",
                callback_data=f"buy:{pid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "💎 شحن Free Fire",
            callback_data="ff_shop"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 الرئيسية",
            callback_data="home"
        )
    ])

    await query.edit_message_text(
        "🛍️ متجر ZADX\n\nاختر الخدمة التي تريدها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_ff_shop(query):

    keyboard = []

    for pid, (name, price) in FF_PACKS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"💎 {name} — {price} نقطة",
                callback_data=f"ff:{pid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="shop"
        )
    ])

    await query.edit_message_text(
        "💎 متجر شحن Free Fire\n\n"
        "اختر باقة الجواهر:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# CALLBACK BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    register(uid)

    action = query.data

    # BALANCE
    if action == "balance":

        await query.edit_message_text(
            f"🪙 رصيدك: {balance(uid)} نقطة",
            reply_markup=menu()
        )

    # DAILY
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

        await query.edit_message_text(
            msg,
            reply_markup=menu()
        )

    # INVITE
    elif action == "invite":

        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"

        await query.edit_message_text(
            "👥 ادعُ أصدقاءك إلى البوت!\n\n"
            "🎁 تحصل على 20 نقطة عن كل صديق جديد.\n\n"
            f"رابط دعوتك:\n{link}",
            reply_markup=menu()
        )

    # SHOP
    elif action == "shop":

        context.user_data.pop("waiting_player_id", None)
        await show_shop(query)

    # FREE FIRE SHOP
    elif action == "ff_shop":

        await show_ff_shop(query)

    # SELECT FREE FIRE PACK
    elif action.startswith("ff:"):

        pid = int(action.split(":")[1])

        if pid not in FF_PACKS:
            return

        name, price = FF_PACKS[pid]

        if uid != OWNER_ID and balance(uid) < price:

            await query.edit_message_text(
                "❌ نقاطك غير كافية!\n\n"
                f"سعر الباقة: {price} نقطة\n"
                f"رصيدك: {balance(uid)} نقطة",
                reply_markup=home_keyboard()
            )
            return

        context.user_data["waiting_player_id"] = {
            "pack_id": pid,
            "name": name,
            "price": price
        }

        await query.edit_message_text(
            "💎 طلب شحن Free Fire\n\n"
            f"الباقة: {name}\n"
            f"السعر: {price} نقطة\n\n"
            "🆔 أرسل Player ID الخاص بحسابك الآن.\n\n"
            "⚠️ تأكد من صحة الرقم قبل الإرسال.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "❌ إلغاء",
                    callback_data="cancel_ff"
                )]
            ])
        )

    # CANCEL FREE FIRE
    elif action == "cancel_ff":

        context.user_data.pop("waiting_player_id", None)

        await query.edit_message_text(
            "❌ تم إلغاء العملية.",
            reply_markup=menu()
        )

    # BUY OLD PRODUCTS
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
                f"📦 طلب جديد!\n"
                f"المستخدم: {uid}\n"
                f"الخدمة: {name}"
            )

    # ADMIN
    elif action == "admin":

        if uid != OWNER_ID:
            await query.answer(
                "هذه القائمة خاصة بالمالك 👑",
                show_alert=True
            )
            return

        await query.edit_message_text(
            "👑 لوحة المالك\n\n"
            "🪙 رصيدك: ∞\n\n"
            "➕ إضافة نقاط:\n"
            "/addpoints USER_ID AMOUNT\n\n"
            "مثال:\n"
            "/addpoints 123456789 100",
            reply_markup=menu()
        )

    # ADMIN ORDER ACTIONS
    elif action.startswith("order:"):

        if uid != OWNER_ID:
            await query.answer(
                "هذه العملية خاصة بالإدارة!",
                show_alert=True
            )
            return

        parts = action.split(":")

        if len(parts) != 3:
            return

        operation = parts[1]

        try:
            order_id = int(parts[2])
        except ValueError:
            return

        order = db.execute(
            "SELECT user_id, product, price, player_id, status "
            "FROM orders WHERE id=?",
            (order_id,)
        ).fetchone()

        if not order or order[4] != "pending":
            await query.edit_message_text(
                "⚠️ هذا الطلب تمت معالجته من قبل."
            )
            return

        user_id, product, price, player_id, status = order

        if operation == "approve":

            db.execute(
                "UPDATE orders SET status='completed' "
                "WHERE id=? AND status='pending'",
                (order_id,)
            )
            db.commit()

            await context.bot.send_message(
                user_id,
                "✅ تم تأكيد إتمام طلبك!\n\n"
                f"💎 الباقة: {product}\n"
                f"🆔 Player ID: {player_id}\n"
                f"📦 رقم الطلب: #{order_id}"
            )

            await query.edit_message_text(
                f"✅ تم تأكيد الطلب #{order_id}."
            )

        elif operation == "reject":

            db.execute("BEGIN")

            db.execute(
                "UPDATE orders SET status='refunded' "
                "WHERE id=? AND status='pending'",
                (order_id,)
            )

            if user_id != OWNER_ID:
                db.execute(
                    "UPDATE users SET points=points+? WHERE id=?",
                    (price, user_id)
                )

            db.commit()

            await context.bot.send_message(
                user_id,
                "❌ تم إلغاء طلبك.\n\n"
                f"💎 الباقة: {product}\n"
                f"🪙 تمت إعادة {price} نقطة إلى رصيدك.\n"
                f"📦 رقم الطلب: #{order_id}"
            )

            await query.edit_message_text(
                f"↩️ تم إلغاء الطلب #{order_id} وإرجاع النقاط."
            )

    # HOME
    elif action == "home":

        context.user_data.pop("waiting_player_id", None)

        await query.edit_message_text(
            "👑 ZADX POINTS STORE\n\n"
            "اختر من القائمة:",
            reply_markup=menu()
        )


# =========================
# PLAYER ID MESSAGE
# =========================

async def handle_player_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    uid = update.effective_user.id

    pending = context.user_data.get("waiting_player_id")

    if not pending:
        return

    player_id = update.message.text.strip()

    if not player_id.isdigit() or not (5 <= len(player_id) <= 20):

        await update.message.reply_text(
            "❌ Player ID غير صحيح.\n"
            "أرسل الرقم فقط، وحاول مرة أخرى."
        )
        return

    name = pending["name"]
    price = pending["price"]

    register(uid)

    # Atomic points deduction and order creation
    try:
        db.execute("BEGIN IMMEDIATE")

        if uid != OWNER_ID:

            result = db.execute(
                "UPDATE users SET points=points-? "
                "WHERE id=? AND points>=?",
                (price, uid, price)
            )

            if result.rowcount != 1:
                db.rollback()

                context.user_data.pop("waiting_player_id", None)

                await update.message.reply_text(
                    "❌ نقاطك غير كافية الآن.",
                    reply_markup=menu()
                )
                return

        cursor = db.execute(
            """
            INSERT INTO orders
            (user_id, product, price, player_id, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                uid,
                name,
                price,
                player_id,
                datetime.now(timezone.utc).isoformat()
            )
        )

        order_id = cursor.lastrowid

        db.commit()

    except Exception:
        db.rollback()

        await update.message.reply_text(
            "❌ حدث خطأ أثناء تسجيل الطلب. حاول مرة أخرى."
        )
        return

    context.user_data.pop("waiting_player_id", None)

    await update.message.reply_text(
        "✅ تم تسجيل طلبك بنجاح!\n\n"
        f"💎 الباقة: {name}\n"
        f"🆔 Player ID: {player_id}\n"
        f"🪙 السعر: {price} نقطة\n"
        f"📦 رقم الطلب: #{order_id}\n\n"
        "⏳ طلبك قيد المراجعة من الإدارة.",
        reply_markup=menu()
    )

    # Notify owner
    if OWNER_ID:

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ تأكيد إتمام الشحن",
                    callback_data=f"order:approve:{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ رفض وإرجاع النقاط",
                    callback_data=f"order:reject:{order_id}"
                )
            ]
        ])

        try:
            await context.bot.send_message(
                OWNER_ID,
                "📦 طلب Free Fire جديد!\n\n"
                f"رقم الطلب: #{order_id}\n"
                f"المستخدم: {uid}\n"
                f"الباقة: {name}\n"
                f"Player ID: {player_id}\n"
                f"السعر: {price} نقطة\n\n"
                "الحالة: قيد المراجعة",
                reply_markup=keyboard
            )

        except Exception:
            print(f"Could not notify owner about order #{order_id}")


# =========================
# ADD POINTS
# =========================

async def addpoints(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

        await update.message.reply_text(
            "❌ تحقق من الأرقام."
        )


# =========================
# MAIN
# =========================

async def main():

    if not TOKEN or not OWNER_ID:
        raise RuntimeError(
            "Set BOT_TOKEN and OWNER_ID first"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpoints", addpoints))

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_player_id
        )
    )

    print("ZADX POINTS STORE is running!")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
