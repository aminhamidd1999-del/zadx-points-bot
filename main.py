import os
import sqlite3
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
    1: ("ØªØµÙÙÙ ÙÙØ´ÙØ±", 100),
    2: ("ØªØµÙÙÙ Ø´Ø¹Ø§Ø±", 250),
    3: ("Ø®Ø¯ÙØ© ØªØ±ÙÙØ¬ Ø­ÙÙÙÙØ©", 500),
}

FF_PACKS = {
    1: ("100 Ø¬ÙÙØ±Ø©", 1000),
    2: ("310 Ø¬ÙÙØ±Ø©", 2500),
    3: ("520 Ø¬ÙÙØ±Ø©", 4000),
    4: ("1060 Ø¬ÙÙØ±Ø©", 8000),
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
        return "â"

    row = db.execute(
        "SELECT points FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    return row[0] if row else 0


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ðª Ø±ØµÙØ¯Ù", callback_data="balance")],
        [InlineKeyboardButton("ð Ø§ÙÙÙØ§ÙØ£Ø© Ø§ÙÙÙÙÙØ©", callback_data="daily")],
        [InlineKeyboardButton("ð¥ Ø¯Ø¹ÙØ© Ø§ÙØ£ØµØ¯ÙØ§Ø¡", callback_data="invite")],
        [InlineKeyboardButton("ðï¸ Ø§ÙÙØªØ¬Ø±", callback_data="shop")],
        [InlineKeyboardButton("ð Ø§ÙØ¥Ø¯Ø§Ø±Ø©", callback_data="admin")]
    ])


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ð  Ø§ÙØ±Ø¦ÙØ³ÙØ©", callback_data="home")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "ð Ø³Ø¬Ù Ø¬ÙÙØ¹ Ø§ÙØ·ÙØ¨Ø§Øª",
            callback_data="admin_orders"
        )],
        [InlineKeyboardButton(
            "â Ø·Ø±ÙÙØ© Ø¥Ø¶Ø§ÙØ© Ø§ÙÙÙØ§Ø·",
            callback_data="admin_points"
        )],
        [InlineKeyboardButton(
            "ð  Ø§ÙØ±Ø¦ÙØ³ÙØ©",
            callback_data="home"
        )]
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
        "ð ÙØ±Ø­Ø¨Ø§Ù Ø¨Ù ÙÙ ZADX POINTS STORE\n\n"
        f"ðª Ø±ØµÙØ¯Ù: {balance(uid)} ÙÙØ·Ø©\n\n"
        "Ø§Ø®ØªØ± ÙÙ Ø§ÙÙØ§Ø¦ÙØ©:",
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
                f"{name} â {price} ÙÙØ·Ø©",
                callback_data=f"buy:{pid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "ð Ø´Ø­Ù Free Fire",
            callback_data="ff_shop"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "ð Ø§ÙØ±Ø¦ÙØ³ÙØ©",
            callback_data="home"
        )
    ])

    await query.edit_message_text(
        "ðï¸ ÙØªØ¬Ø± ZADX\n\nØ§Ø®ØªØ± Ø§ÙØ®Ø¯ÙØ© Ø§ÙØªÙ ØªØ±ÙØ¯ÙØ§:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_ff_shop(query):
    keyboard = []

    for pid, (name, price) in FF_PACKS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"ð {name} â {price} ÙÙØ·Ø©",
                callback_data=f"ff:{pid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "ð Ø±Ø¬ÙØ¹",
            callback_data="shop"
        )
    ])

    await query.edit_message_text(
        "ð ÙØªØ¬Ø± Ø´Ø­Ù Free Fire\n\n"
        "Ø§Ø®ØªØ± Ø¨Ø§ÙØ© Ø§ÙØ¬ÙØ§ÙØ±:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ADMIN ORDERS HISTORY
# =========================

async def show_admin_orders(query, page=0):
    total = db.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    counts = db.execute("""
        SELECT status, COUNT(*)
        FROM orders
        GROUP BY status
    """).fetchall()

    stats = dict(counts)
    pending = stats.get("pending", 0)
    completed = stats.get("completed", 0)
    refunded = stats.get("refunded", 0)

    orders = db.execute("""
        SELECT id, product, status
        FROM orders
        ORDER BY id DESC
        LIMIT 8 OFFSET ?
    """, (page * 8,)).fetchall()

    text = (
        "ð Ø³Ø¬Ù Ø·ÙØ¨Ø§Øª ZADX\n\n"
        f"ð¦ ÙØ¬ÙÙØ¹ Ø§ÙØ·ÙØ¨Ø§Øª: {total}\n"
        f"â³ ÙÙØ¯ Ø§ÙÙØ±Ø§Ø¬Ø¹Ø©: {pending}\n"
        f"â ÙÙØªÙÙØ©: {completed}\n"
        f"â ÙÙØºØ§Ø©: {refunded}\n\n"
        "ð Ø§Ø¶ØºØ· Ø¹ÙÙ Ø£Ù Ø·ÙØ¨ ÙØ¹Ø±Ø¶ ØªÙØ§ØµÙÙÙ:"
    )

    keyboard = []

    for order_id, product, status in orders:
        status_icon = {
            "pending": "â³",
            "completed": "â",
            "refunded": "â"
        }.get(status, "â")

        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} Ø§ÙØ·ÙØ¨ #{order_id} - {product}",
                callback_data=f"order_view:{order_id}:{page}"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "â¬ï¸ Ø§ÙØ³Ø§Ø¨Ù",
                callback_data=f"admin_orders:{page-1}"
            )
        )

    if (page + 1) * 8 < total:
        navigation.append(
            InlineKeyboardButton(
                "Ø§ÙØªØ§ÙÙ â¡ï¸",
                callback_data=f"admin_orders:{page+1}"
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append([
        InlineKeyboardButton(
            "ð ØªØ­Ø¯ÙØ«",
            callback_data=f"admin_orders:{page}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "ð ÙÙØ­Ø© Ø§ÙØ¥Ø¯Ø§Ø±Ø©",
            callback_data="admin"
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_admin_order_details(query, order_id, page=0):
    order = db.execute("""
        SELECT id, user_id, product, price,
               player_id, status, created_at
        FROM orders
        WHERE id=?
    """, (order_id,)).fetchone()

    if not order:
        await query.edit_message_text(
            "â Ø§ÙØ·ÙØ¨ ØºÙØ± ÙÙØ¬ÙØ¯.",
            reply_markup=admin_keyboard()
        )
        return

    oid, user, product, price, player, status, created = order

    status_text = {
        "pending": "â³ ÙÙØ¯ Ø§ÙÙØ±Ø§Ø¬Ø¹Ø©",
        "completed": "â ÙÙØªÙÙ",
        "refunded": "â ÙÙØºÙ ÙÙØ³ØªØ±Ø¬Ø¹"
    }.get(status, status)

    text = (
        f"ð¦ ØªÙØ§ØµÙÙ Ø§ÙØ·ÙØ¨ #{oid}\n\n"
        "ââââââââââââ\n"
        f"ð¤ Ø§ÙÙØ³ØªØ®Ø¯Ù: {user}\n"
        f"ð Ø§ÙØ¨Ø§ÙØ©: {product}\n"
        f"ð Player ID: {player}\n"
        f"ðª Ø§ÙØ³Ø¹Ø±: {price} ÙÙØ·Ø©\n"
        f"ð Ø§ÙØ­Ø§ÙØ©: {status_text}\n"
        f"ð Ø§ÙØªØ§Ø±ÙØ®: {created or 'ØºÙØ± ÙØªÙÙØ±'}\n"
        "ââââââââââââ"
    )

    keyboard = []

    if status == "pending":
        keyboard.append([
            InlineKeyboardButton(
                "â ØªØ£ÙÙØ¯ Ø¥ØªÙØ§Ù Ø§ÙØ´Ø­Ù",
                callback_data=f"order:approve:{oid}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                "â Ø±ÙØ¶ ÙØ¥Ø±Ø¬Ø§Ø¹ Ø§ÙÙÙØ§Ø·",
                callback_data=f"order:reject:{oid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "ð Ø±Ø¬ÙØ¹ Ø¥ÙÙ Ø³Ø¬Ù Ø§ÙØ·ÙØ¨Ø§Øª",
            callback_data=f"admin_orders:{page}"
        )
    ])

    await query.edit_message_text(
        text,
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

    if action == "balance":
        await query.edit_message_text(
            f"ðª Ø±ØµÙØ¯Ù: {balance(uid)} ÙÙØ·Ø©",
            reply_markup=menu()
        )

    elif action == "daily":
        today = str(date.today())

        row = db.execute(
            "SELECT last_daily FROM users WHERE id=?",
            (uid,)
        ).fetchone()

        if row[0] == today:
            msg = "â³ ÙÙØ¯ Ø£Ø®Ø°Øª ÙÙØ§ÙØ£ØªÙ Ø§ÙÙÙÙ. Ø¹ÙØ¯ ØºØ¯Ø§Ù!"
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
            msg = "ð Ø­ØµÙØª Ø¹ÙÙ 10 ÙÙØ§Ø·!"

        await query.edit_message_text(msg, reply_markup=menu())

    elif action == "invite":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"

        await query.edit_message_text(
            "ð¥ Ø§Ø¯Ø¹Ù Ø£ØµØ¯ÙØ§Ø¡Ù Ø¥ÙÙ Ø§ÙØ¨ÙØª!\n\n"
            "ð ØªØ­ØµÙ Ø¹ÙÙ 20 ÙÙØ·Ø© Ø¹Ù ÙÙ ØµØ¯ÙÙ Ø¬Ø¯ÙØ¯.\n\n"
            f"Ø±Ø§Ø¨Ø· Ø¯Ø¹ÙØªÙ:\n{link}",
            reply_markup=menu()
        )

    elif action == "shop":
        context.user_data.pop("waiting_player_id", None)
        await show_shop(query)

    elif action == "ff_shop":
        await show_ff_shop(query)

    elif action.startswith("ff:"):
        try:
            pid = int(action.split(":")[1])
        except ValueError:
            return

        if pid not in FF_PACKS:
            return

        name, price = FF_PACKS[pid]

        if uid != OWNER_ID and balance(uid) < price:
            await query.edit_message_text(
                "â ÙÙØ§Ø·Ù ØºÙØ± ÙØ§ÙÙØ©!\n\n"
                f"Ø³Ø¹Ø± Ø§ÙØ¨Ø§ÙØ©: {price} ÙÙØ·Ø©\n"
                f"Ø±ØµÙØ¯Ù: {balance(uid)} ÙÙØ·Ø©",
                reply_markup=home_keyboard()
            )
            return

        context.user_data["waiting_player_id"] = {
            "pack_id": pid,
            "name": name,
            "price": price
        }

        await query.edit_message_text(
            "ð Ø·ÙØ¨ Ø´Ø­Ù Free Fire\n\n"
            f"Ø§ÙØ¨Ø§ÙØ©: {name}\n"
            f"Ø§ÙØ³Ø¹Ø±: {price} ÙÙØ·Ø©\n\n"
            "ð Ø£Ø±Ø³Ù Player ID Ø§ÙØ®Ø§Øµ Ø¨Ø­Ø³Ø§Ø¨Ù Ø§ÙØ¢Ù.\n\n"
            "â ï¸ ØªØ£ÙØ¯ ÙÙ ØµØ­Ø© Ø§ÙØ±ÙÙ ÙØ¨Ù Ø§ÙØ¥Ø±Ø³Ø§Ù.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("â Ø¥ÙØºØ§Ø¡", callback_data="cancel_ff")]
            ])
        )

    elif action == "cancel_ff":
        context.user_data.pop("waiting_player_id", None)
        await query.edit_message_text(
            "â ØªÙ Ø¥ÙØºØ§Ø¡ Ø§ÙØ¹ÙÙÙØ©.",
            reply_markup=menu()
        )

    elif action.startswith("buy:"):
        try:
            pid = int(action.split(":")[1])
        except ValueError:
            return

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
                    "â ÙÙØ§Ø·Ù ØºÙØ± ÙØ§ÙÙØ©!",
                    reply_markup=menu()
                )
                return

            db.execute(
                "UPDATE users SET points=points-? WHERE id=?",
                (price, uid)
            )
            db.commit()

        await query.edit_message_text(
            f"â ØªÙ ØªØ³Ø¬ÙÙ Ø·ÙØ¨Ù!\n\n"
            f"Ø§ÙØ®Ø¯ÙØ©: {name}\n"
            f"Ø§ÙØ³Ø¹Ø±: {price} ÙÙØ·Ø©\n"
            "ØªÙØ§ØµÙ ÙØ¹ Ø§ÙØ¥Ø¯Ø§Ø±Ø© ÙØ¥ØªÙØ§Ù Ø§ÙØ®Ø¯ÙØ©.",
            reply_markup=menu()
        )

        if OWNER_ID:
            await context.bot.send_message(
                OWNER_ID,
                f"ð¦ Ø·ÙØ¨ Ø¬Ø¯ÙØ¯!\n"
                f"Ø§ÙÙØ³ØªØ®Ø¯Ù: {uid}\n"
                f"Ø§ÙØ®Ø¯ÙØ©: {name}"
            )

    elif action == "admin":
        if uid != OWNER_ID:
            await query.edit_message_text(
                "â ÙØ°Ù Ø§ÙÙØ§Ø¦ÙØ© Ø®Ø§ØµØ© Ø¨Ø§ÙÙØ§ÙÙ."
            )
            return

        await query.edit_message_text(
            "ð ÙÙØ­Ø© Ø¥Ø¯Ø§Ø±Ø© ZADX\n\n"
            "ðª Ø±ØµÙØ¯Ù: â\n\n"
            "Ø§Ø®ØªØ± Ø§ÙØ¹ÙÙÙØ© Ø§ÙØªÙ ØªØ±ÙØ¯ÙØ§:",
            reply_markup=admin_keyboard()
        )

    elif action == "admin_points":
        if uid != OWNER_ID:
            return

        await query.edit_message_text(
            "â Ø¥Ø¶Ø§ÙØ© ÙÙØ§Ø· ÙÙÙØ³ØªØ®Ø¯Ù:\n\n"
            "/addpoints USER_ID AMOUNT\n\n"
            "ÙØ«Ø§Ù:\n/addpoints 123456789 100",
            reply_markup=admin_keyboard()
        )

    elif action == "admin_orders" or action.startswith("admin_orders:"):
        if uid != OWNER_ID:
            await query.answer(
                "ÙØ°Ù Ø§ÙÙØ§Ø¦ÙØ© Ø®Ø§ØµØ© Ø¨Ø§ÙÙØ§ÙÙ!",
                show_alert=True
            )
            return

        page = 0
        if ":" in action:
            try:
                page = max(0, int(action.split(":")[1]))
            except ValueError:
                page = 0

        await show_admin_orders(query, page)

    elif action.startswith("order_view:"):
        if uid != OWNER_ID:
            await query.answer(
                "ÙØ°Ù Ø§ÙØ¹ÙÙÙØ© Ø®Ø§ØµØ© Ø¨Ø§ÙØ¥Ø¯Ø§Ø±Ø©!",
                show_alert=True
            )
            return

        try:
            parts = action.split(":")
            order_id = int(parts[1])
            page = int(parts[2])
            await show_admin_order_details(query, order_id, page)
        except (ValueError, IndexError):
            await query.edit_message_text(
                "â Ø­Ø¯Ø« Ø®Ø·Ø£ ÙÙ Ø±ÙÙ Ø§ÙØ·ÙØ¨."
            )

    elif action.startswith("order:"):
        if uid != OWNER_ID:
            await query.answer(
                "ÙØ°Ù Ø§ÙØ¹ÙÙÙØ© Ø®Ø§ØµØ© Ø¨Ø§ÙØ¥Ø¯Ø§Ø±Ø©!",
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
                "â ï¸ ÙØ°Ø§ Ø§ÙØ·ÙØ¨ ØªÙØª ÙØ¹Ø§ÙØ¬ØªÙ ÙÙ ÙØ¨Ù.",
                reply_markup=admin_keyboard()
            )
            return

        user_id, product, price, player_id, status = order

        if operation == "approve":
            result = db.execute(
                "UPDATE orders SET status='completed' "
                "WHERE id=? AND status='pending'",
                (order_id,)
            )
            db.commit()

            if result.rowcount == 1:
                await context.bot.send_message(
                    user_id,
                    "â ØªÙ ØªØ£ÙÙØ¯ Ø¥ØªÙØ§Ù Ø·ÙØ¨Ù!\n\n"
                    f"ð Ø§ÙØ¨Ø§ÙØ©: {product}\n"
                    f"ð Player ID: {player_id}\n"
                    f"ð¦ Ø±ÙÙ Ø§ÙØ·ÙØ¨: #{order_id}"
                )

                await query.edit_message_text(
                    f"â ØªÙ ØªØ£ÙÙØ¯ Ø§ÙØ·ÙØ¨ #{order_id}.",
                    reply_markup=admin_keyboard()
                )

        elif operation == "reject":
            db.execute("BEGIN IMMEDIATE")

            result = db.execute(
                "UPDATE orders SET status='refunded' "
                "WHERE id=? AND status='pending'",
                (order_id,)
            )

            if result.rowcount == 1 and user_id != OWNER_ID:
                db.execute(
                    "UPDATE users SET points=points+? WHERE id=?",
                    (price, user_id)
                )

            db.commit()

            if result.rowcount == 1:
                await context.bot.send_message(
                    user_id,
                    "â ØªÙ Ø¥ÙØºØ§Ø¡ Ø·ÙØ¨Ù.\n\n"
                    f"ð Ø§ÙØ¨Ø§ÙØ©: {product}\n"
                    f"ðª ØªÙØª Ø¥Ø¹Ø§Ø¯Ø© {price} ÙÙØ·Ø© Ø¥ÙÙ Ø±ØµÙØ¯Ù.\n"
                    f"ð¦ Ø±ÙÙ Ø§ÙØ·ÙØ¨: #{order_id}"
                )

                await query.edit_message_text(
                    f"â©ï¸ ØªÙ Ø¥ÙØºØ§Ø¡ Ø§ÙØ·ÙØ¨ #{order_id} ÙØ¥Ø±Ø¬Ø§Ø¹ Ø§ÙÙÙØ§Ø·.",
                    reply_markup=admin_keyboard()
                )

    elif action == "home":
        context.user_data.pop("waiting_player_id", None)
        await query.edit_message_text(
            "ð ZADX POINTS STORE\n\n"
            "Ø§Ø®ØªØ± ÙÙ Ø§ÙÙØ§Ø¦ÙØ©:",
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
            "â Player ID ØºÙØ± ØµØ­ÙØ­.\n"
            "Ø£Ø±Ø³Ù Ø§ÙØ±ÙÙ ÙÙØ·Ø ÙØ­Ø§ÙÙ ÙØ±Ø© Ø£Ø®Ø±Ù."
        )
        return

    name = pending["name"]
    price = pending["price"]

    register(uid)

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
                    "â ÙÙØ§Ø·Ù ØºÙØ± ÙØ§ÙÙØ© Ø§ÙØ¢Ù.",
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
            "â Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«ÙØ§Ø¡ ØªØ³Ø¬ÙÙ Ø§ÙØ·ÙØ¨. Ø­Ø§ÙÙ ÙØ±Ø© Ø£Ø®Ø±Ù."
        )
        return

    context.user_data.pop("waiting_player_id", None)

    await update.message.reply_text(
        "â ØªÙ ØªØ³Ø¬ÙÙ Ø·ÙØ¨Ù Ø¨ÙØ¬Ø§Ø­!\n\n"
        f"ð Ø§ÙØ¨Ø§ÙØ©: {name}\n"
        f"ð Player ID: {player_id}\n"
        f"ðª Ø§ÙØ³Ø¹Ø±: {price} ÙÙØ·Ø©\n"
        f"ð¦ Ø±ÙÙ Ø§ÙØ·ÙØ¨: #{order_id}\n\n"
        "â³ Ø·ÙØ¨Ù ÙÙØ¯ Ø§ÙÙØ±Ø§Ø¬Ø¹Ø© ÙÙ Ø§ÙØ¥Ø¯Ø§Ø±Ø©.",
        reply_markup=menu()
    )

    if OWNER_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "â ØªØ£ÙÙØ¯ Ø¥ØªÙØ§Ù Ø§ÙØ´Ø­Ù",
                callback_data=f"order:approve:{order_id}"
            )],
            [InlineKeyboardButton(
                "â Ø±ÙØ¶ ÙØ¥Ø±Ø¬Ø§Ø¹ Ø§ÙÙÙØ§Ø·",
                callback_data=f"order:reject:{order_id}"
            )]
        ])

        try:
            await context.bot.send_message(
                OWNER_ID,
                "ð¦ Ø·ÙØ¨ Free Fire Ø¬Ø¯ÙØ¯!\n\n"
                f"Ø±ÙÙ Ø§ÙØ·ÙØ¨: #{order_id}\n"
                f"Ø§ÙÙØ³ØªØ®Ø¯Ù: {uid}\n"
                f"Ø§ÙØ¨Ø§ÙØ©: {name}\n"
                f"Player ID: {player_id}\n"
                f"Ø§ÙØ³Ø¹Ø±: {price} ÙÙØ·Ø©\n\n"
                "Ø§ÙØ­Ø§ÙØ©: ÙÙØ¯ Ø§ÙÙØ±Ø§Ø¬Ø¹Ø©",
                reply_markup=keyboard
            )
        except Exception as exc:
            print(f"Could not notify owner about order #{order_id}: {exc}")


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
            "Ø§Ø³ØªØ¹ÙÙ:\n/addpoints USER_ID AMOUNT"
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
            f"â ØªÙØª Ø¥Ø¶Ø§ÙØ© {amount} ÙÙØ·Ø© ÙÙÙØ³ØªØ®Ø¯Ù {target}"
        )

    except ValueError:
        await update.message.reply_text(
            "â ØªØ­ÙÙ ÙÙ Ø§ÙØ£Ø±ÙØ§Ù."
        )


# =========================
# MAIN
# =========================

def main():
    if not TOKEN or not OWNER_ID:
        raise RuntimeError(
            "Set BOT_TOKEN and OWNER_ID first"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpoints", addpoints))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_player_id
        )
    )

    print("ZADX POINTS STORE is running!")

    app.run_polling()


if __name__ == "__main__":
    main()
