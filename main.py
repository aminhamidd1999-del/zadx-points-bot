
# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import date, datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Free Fire test mode: no real top-up and no points deduction
FF_TEST_MODE = True

db = sqlite3.connect("zadx.db", check_same_thread=False)
db.execute("PRAGMA foreign_keys = ON")

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
    player_id TEXT NOT NULL DEFAULT 'غير مطلوب',
    status TEXT DEFAULT 'pending',
    created_at TEXT
)
""")

# Safe database migrations
columns = {
    row[1] for row in db.execute(
        "PRAGMA table_info(orders)"
    ).fetchall()
}

if "is_test" not in columns:
    db.execute(
        "ALTER TABLE orders ADD COLUMN is_test INTEGER DEFAULT 0"
    )

if "provider_ref" not in columns:
    db.execute(
        "ALTER TABLE orders ADD COLUMN provider_ref TEXT"
    )

if "provider_status" not in columns:
    db.execute(
        "ALTER TABLE orders ADD COLUMN provider_status TEXT"
    )

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

def register(user_id: int):
    db.execute(
        "INSERT OR IGNORE INTO users (id, points) VALUES (?, 0)",
        (user_id,),
    )
    db.commit()


def balance(user_id: int):
    if user_id == OWNER_ID:
        return "∞"

    row = db.execute(
        "SELECT points FROM users WHERE id=?",
        (user_id,),
    ).fetchone()

    return row[0] if row else 0


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 رصيدي", callback_data="balance")],
        [InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily")],
        [InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="invite")],
        [InlineKeyboardButton("🛍️ المتجر", callback_data="shop")],
        [InlineKeyboardButton("👑 الإدارة", callback_data="admin")],
    ])


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 سجل جميع الطلبات", callback_data="admin_orders")],
        [InlineKeyboardButton("➕ طريقة إضافة النقاط", callback_data="admin_points")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")],
    ])


async def notify_owner(context, message, reply_markup=None):
    if OWNER_ID:
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=message,
                reply_markup=reply_markup,
            )
        except Exception as exc:
            print(f"تعذر إرسال إشعار للمالك: {exc}")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


# =========================
# SIMULATED PROVIDER
# =========================

def simulate_provider_topup(order_id, player_id, product):
    """
    محاكاة محلية فقط.
    لا يوجد اتصال بمزوّد حقيقي.
    لا يتم شحن الجواهر أو خصم النقاط.
    """

    if not player_id.isdigit():
        return {
            "success": False,
            "reference": None,
            "status": "simulated_failed",
        }

    reference = f"SIM-ZADX-{order_id:06d}"

    return {
        "success": True,
        "reference": reference,
        "status": "simulated_success",
    }


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
                    (uid,),
                ).fetchone()

                if not exists:
                    register(inviter)

                    db.execute(
                        "INSERT INTO referrals (invited, inviter) VALUES (?, ?)",
                        (uid, inviter),
                    )

                    db.execute(
                        "UPDATE users SET points=points+20 WHERE id=?",
                        (inviter,),
                    )
                    db.commit()

                    try:
                        await context.bot.send_message(
                            inviter,
                            "🎉 دخل صديق جديد عن طريق رابط دعوتك! تحصلت على 20 نقطة.",
                        )
                    except Exception:
                        pass

        except ValueError:
            pass

    context.user_data.pop("waiting_player_id", None)

    await update.message.reply_text(
        "👑 مرحباً بك في ZADX POINTS STORE\n\n"
        f"🪙 رصيدك: {balance(uid)} نقطة\n\n"
        "اختر من القائمة:",
        reply_markup=menu(),
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
                callback_data=f"buy:{pid}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("💎 شحن Free Fire 🧪", callback_data="ff_shop")
    ])

    keyboard.append([
        InlineKeyboardButton("🔙 الرئيسية", callback_data="home")
    ])

    await query.edit_message_text(
        "🛍️ متجر ZADX\n\nاختر الخدمة التي تريدها:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_ff_shop(query):
    keyboard = []

    for pid, (name, price) in FF_PACKS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🧪 {name} — {price} نقطة",
                callback_data=f"ff:{pid}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="shop")
    ])

    await query.edit_message_text(
        "💎 متجر شحن Free Fire\n\n"
        "🧪 وضع تجريبي فقط.\n"
        "لا يتم شحن الجواهر ولا خصم النقاط.\n"
        "الأسعار المعروضة تجريبية وليست أسعار مزوّد.\n\n"
        "اختر باقة للتجربة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
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

    test_total = db.execute(
        "SELECT COUNT(*) FROM orders WHERE is_test=1"
    ).fetchone()[0]

    orders = db.execute("""
        SELECT id, product, status, is_test
        FROM orders
        ORDER BY id DESC
        LIMIT 8 OFFSET ?
    """, (page * 8,)).fetchall()

    text = (
        "📋 سجل طلبات ZADX\n\n"
        f"📦 مجموع الطلبات: {total}\n"
        f"⏳ قيد المراجعة: {pending}\n"
        f"✅ مكتملة: {completed}\n"
        f"❌ ملغاة: {refunded}\n"
        f"🧪 طلبات تجريبية: {test_total}\n\n"
        "👇 اضغط على أي طلب لعرض تفاصيله:"
    )

    keyboard = []

    for order_id, product, status, is_test in orders:
        status_icon = {
            "pending": "⏳",
            "completed": "✅",
            "refunded": "❌",
        }.get(status, "❔")

        test_icon = "🧪 " if is_test else ""

        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} {test_icon}الطلب #{order_id} - {product}",
                callback_data=f"order_view:{order_id}:{page}",
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"admin_orders:{page-1}",
            )
        )

    if (page + 1) * 8 < total:
        navigation.append(
            InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"admin_orders:{page+1}",
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append([
        InlineKeyboardButton(
            "🔄 تحديث",
            callback_data=f"admin_orders:{page}",
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 لوحة الإدارة",
            callback_data="admin",
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_admin_order_details(query, order_id, page=0):
    order = db.execute("""
        SELECT id, user_id, product, price,
               player_id, status, created_at, is_test,
               provider_ref, provider_status
        FROM orders
        WHERE id=?
    """, (order_id,)).fetchone()

    if not order:
        await query.edit_message_text(
            "❌ الطلب غير موجود.",
            reply_markup=admin_keyboard(),
        )
        return

    (
        oid, user, product, price, player,
        status, created, is_test,
        provider_ref, provider_status
    ) = order

    status_text = {
        "pending": "⏳ قيد المراجعة",
        "completed": "✅ مكتمل",
        "refunded": "❌ ملغى وتم إرجاع النقاط",
    }.get(status, status)

    test_text = (
        "🧪 طلب تجريبي - لا يوجد شحن حقيقي"
        if is_test else
        "طلب عادي"
    )

    text = (
        f"📦 تفاصيل الطلب #{oid}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 المستخدم: {user}\n"
        f"🛍️ الخدمة/الباقة: {product}\n"
        f"🆔 Player ID: {player}\n"
        f"🪙 السعر: {price} نقطة\n"
        f"📌 الحالة: {status_text}\n"
        f"🧪 النوع: {test_text}\n"
        f"🔖 رقم عملية المزوّد: {provider_ref or 'لم تتم المحاكاة'}\n"
        f"🧪 نتيجة المزوّد: {provider_status or 'لم تتم بعد'}\n"
        f"📅 التاريخ: {created or 'غير متوفر'}\n"
        "━━━━━━━━━━━━━━"
    )

    keyboard = []

    if status == "pending":
        keyboard.append([
            InlineKeyboardButton(
                "✅ تأكيد الطلب",
                callback_data=f"order:approve:{oid}",
            )
        ])

        keyboard.append([
            InlineKeyboardButton(
                "❌ رفض الطلب",
                callback_data=f"order:reject:{oid}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 الرجوع إلى سجل الطلبات",
            callback_data=f"admin_orders:{page}",
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
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
            f"🪙 رصيدك: {balance(uid)} نقطة",
            reply_markup=menu(),
        )

    elif action == "daily":
        today = str(date.today())

        row = db.execute(
            "SELECT last_daily FROM users WHERE id=?",
            (uid,),
        ).fetchone()

        if row and row[0] == today:
            msg = "⏳ لقد أخذت مكافأتك اليوم. عُد غداً!"
        else:
            if uid != OWNER_ID:
                db.execute(
                    "UPDATE users SET points=points+10, last_daily=? WHERE id=?",
                    (today, uid),
                )
            else:
                db.execute(
                    "UPDATE users SET last_daily=? WHERE id=?",
                    (today, uid),
                )

            db.commit()
            msg = "🎉 تحصلت على 10 نقاط!"

        await query.edit_message_text(msg, reply_markup=menu())

    elif action == "invite":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"

        await query.edit_message_text(
            "👥 ادعُ أصدقاءك إلى البوت!\n\n"
            "🎁 تحصل على 20 نقطة عن كل صديق جديد.\n\n"
            f"رابط دعوتك:\n{link}",
            reply_markup=menu(),
        )

    elif action == "shop":
        context.user_data.pop("waiting_player_id", None)
        await show_shop(query)

    elif action == "ff_shop":
        await show_ff_shop(query)

    # Free Fire test purchase
    elif action.startswith("ff:"):
        if not FF_TEST_MODE:
            await query.edit_message_text(
                "❌ متجر Free Fire غير متاح حالياً.",
                reply_markup=menu(),
            )
            return

        try:
            pid = int(action.split(":")[1])
        except ValueError:
            return

        if pid not in FF_PACKS:
            return

        name, price = FF_PACKS[pid]

        context.user_data["waiting_player_id"] = {
            "pack_id": pid,
            "name": name,
            "price": price,
            "is_test": True,
        }

        await query.edit_message_text(
            "🧪 طلب تجريبي - Free Fire\n\n"
            f"الباقة: {name}\n"
            f"السعر التجريبي: {price} نقطة\n\n"
            "⚠️ هذا اختبار فقط.\n"
            "لن يتم شحن الجواهر ولن يتم خصم النقاط.\n\n"
            "🆔 أرسل Player ID للتجربة:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ إلغاء",
                        callback_data="cancel_ff",
                    )
                ]
            ]),
        )

    elif action == "cancel_ff":
        context.user_data.pop("waiting_player_id", None)

        await query.edit_message_text(
            "❌ تم إلغاء العملية.",
            reply_markup=menu(),
        )

    # Normal services
    elif action.startswith("buy:"):
        try:
            pid = int(action.split(":")[1])
        except ValueError:
            return

        if pid not in PRODUCTS:
            return

        name, price = PRODUCTS[pid]

        try:
            db.execute("BEGIN IMMEDIATE")

            if uid != OWNER_ID:
                result = db.execute(
                    "UPDATE users SET points=points-? "
                    "WHERE id=? AND points>=?",
                    (price, uid, price),
                )

                if result.rowcount != 1:
                    db.rollback()

                    await query.edit_message_text(
                        "❌ نقاطك غير كافية لشراء هذه الخدمة.",
                        reply_markup=home_keyboard(),
                    )
                    return

            cursor = db.execute("""
                INSERT INTO orders
                (user_id, product, price, player_id,
                 status, created_at, is_test)
                VALUES (?, ?, ?, ?, 'pending', ?, 0)
            """, (
                uid,
                name,
                price,
                "غير مطلوب",
                now_utc(),
            ))

            order_id = cursor.lastrowid
            db.commit()

        except Exception as exc:
            db.rollback()
            print(f"خطأ في تسجيل طلب الخدمة: {exc}")

            await query.edit_message_text(
                "❌ حدث خطأ أثناء تسجيل الطلب. حاول مرة أخرى.",
                reply_markup=menu(),
            )
            return

        await query.edit_message_text(
            "✅ تم تسجيل طلبك بنجاح!\n\n"
            f"📦 رقم الطلب: #{order_id}\n"
            f"الخدمة: {name}\n"
            f"السعر: {price} نقطة\n\n"
            "⏳ طلبك قيد المراجعة من الإدارة.",
            reply_markup=menu(),
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ تأكيد إتمام الطلب",
                    callback_data=f"order:approve:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ رفض وإرجاع النقاط",
                    callback_data=f"order:reject:{order_id}",
                )
            ],
        ])

        await notify_owner(
            context,
            "📦 طلب خدمة جديد!\n\n"
            f"رقم الطلب: #{order_id}\n"
            f"المستخدم: {uid}\n"
            f"الخدمة: {name}\n"
            f"السعر: {price} نقطة\n"
            "الحالة: قيد المراجعة",
            keyboard,
        )

    elif action == "admin":
        if uid != OWNER_ID:
            await query.edit_message_text(
                "❌ هذه القائمة خاصة بالمالك."
            )
            return

        await query.edit_message_text(
            "👑 لوحة إدارة ZADX\n\n"
            "🪙 رصيدك: ∞\n\n"
            "اختر العملية التي تريدها:",
            reply_markup=admin_keyboard(),
        )

    elif action == "admin_points":
        if uid != OWNER_ID:
            return

        await query.edit_message_text(
            "➕ إضافة نقاط للمستخدم:\n\n"
            "/addpoints USER_ID AMOUNT\n\n"
            "مثال:\n/addpoints 123456789 100",
            reply_markup=admin_keyboard(),
        )

    elif action == "admin_orders" or action.startswith("admin_orders:"):
        if uid != OWNER_ID:
            await query.edit_message_text(
                "❌ سجل الطلبات خاص بالمالك."
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
            await query.edit_message_text(
                "❌ هذه العملية خاصة بالإدارة."
            )
            return

        try:
            parts = action.split(":")
            order_id = int(parts[1])
            page = int(parts[2])

            await show_admin_order_details(
                query,
                order_id,
                page,
            )

        except (ValueError, IndexError):
            await query.edit_message_text(
                "❌ حدث خطأ في رقم الطلب."
            )

    # Approve / reject orders
    elif action.startswith("order:"):
        if uid != OWNER_ID:
            await query.edit_message_text(
                "❌ هذه العملية خاصة بالإدارة."
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

        order = db.execute("""
            SELECT user_id, product, price,
                   player_id, status, is_test
            FROM orders
            WHERE id=?
        """, (order_id,)).fetchone()

        if not order or order[4] != "pending":
            await query.edit_message_text(
                "⚠️ هذا الطلب تمت معالجته من قبل.",
                reply_markup=admin_keyboard(),
            )
            return

        user_id, product, price, player_id, status, is_test = order

        if operation == "approve":

            provider_result = None

            if is_test:
                provider_result = simulate_provider_topup(
                    order_id,
                    player_id,
                    product,
                )

                provider_ref = provider_result["reference"]
                provider_status = provider_result["status"]

                if provider_result["success"]:
                    result = db.execute("""
                        UPDATE orders
                        SET status='completed',
                            provider_ref=?,
                            provider_status=?
                        WHERE id=? AND status='pending'
                    """, (
                        provider_ref,
                        provider_status,
                        order_id,
                    ))
                else:
                    result = db.execute("""
                        UPDATE orders
                        SET provider_ref=?,
                            provider_status=?
                        WHERE id=? AND status='pending'
                    """, (
                        provider_ref,
                        provider_status,
                        order_id,
                    ))

            else:
                result = db.execute(
                    "UPDATE orders SET status='completed' "
                    "WHERE id=? AND status='pending'",
                    (order_id,),
                )

            db.commit()

            if result.rowcount == 1:

                if is_test and provider_result["success"]:
                    user_message = (
                        "🧪 نجحت محاكاة المزوّد!\n\n"
                        f"💎 الباقة: {product}\n"
                        f"🆔 Player ID: {player_id}\n"
                        f"📦 رقم الطلب: #{order_id}\n"
                        f"🔖 رقم العملية التجريبي: {provider_ref}\n\n"
                        "✅ المزوّد التجريبي أعاد نتيجة نجاح.\n"
                        "⚠️ لا يوجد شحن حقيقي ولم يتم خصم نقاط."
                    )

                elif is_test:
                    user_message = (
                        "🧪 فشلت محاكاة المزوّد.\n\n"
                        f"📦 رقم الطلب: #{order_id}\n"
                        "⚠️ لم يتم شحن الجواهر ولم تخصم أي نقاط."
                    )

                else:
                    user_message = (
                        "✅ تم تأكيد إتمام طلبك!\n\n"
                        f"📦 الخدمة: {product}\n"
                        f"🆔 Player ID: {player_id}\n"
                        f"رقم الطلب: #{order_id}"
                    )

                try:
                    await context.bot.send_message(
                        user_id,
                        user_message,
                    )
                except Exception as exc:
                    print(f"تعذر إرسال إشعار للمستخدم: {exc}")

                admin_message = f"✅ تمت معالجة الطلب #{order_id}."

                if is_test:
                    admin_message += (
                        "\n\n🧪 نتيجة محاكاة المزوّد: "
                        f"{provider_result['status']}"
                        f"\n🔖 رقم العملية: {provider_ref or 'لا يوجد'}"
                        "\n⚠️ لم يحدث شحن حقيقي."
                    )

                await query.edit_message_text(
                    admin_message,
                    reply_markup=admin_keyboard(),
                )

        elif operation == "reject":
            try:
                db.execute("BEGIN IMMEDIATE")

                result = db.execute(
                    "UPDATE orders SET status='refunded' "
                    "WHERE id=? AND status='pending'",
                    (order_id,),
                )

                if result.rowcount == 1 and user_id != OWNER_ID and not is_test:
                    db.execute(
                        "UPDATE users SET points=points+? WHERE id=?",
                        (price, user_id),
                    )

                db.commit()

            except Exception as exc:
                db.rollback()
                print(f"خطأ في إرجاع النقاط: {exc}")

                await query.edit_message_text(
                    "❌ حدث خطأ أثناء إلغاء الطلب."
                )
                return

            if result.rowcount == 1:
                if is_test:
                    user_message = (
                        "❌ تم رفض طلبك التجريبي.\n\n"
                        f"📦 الباقة: {product}\n"
                        f"رقم الطلب: #{order_id}\n\n"
                        "🧪 لم يتم خصم أي نقاط، لأنه طلب تجريبي."
                    )
                else:
                    user_message = (
                        "❌ تم إلغاء طلبك.\n\n"
                        f"📦 الخدمة: {product}\n"
                        f"🪙 تمت إعادة {price} نقطة إلى رصيدك.\n"
                        f"رقم الطلب: #{order_id}"
                    )

                try:
                    await context.bot.send_message(
                        user_id,
                        user_message,
                    )
                except Exception as exc:
                    print(f"تعذر إرسال إشعار للمستخدم: {exc}")

                await query.edit_message_text(
                    f"↩️ تم إلغاء الطلب #{order_id}.",
                    reply_markup=admin_keyboard(),
                )

    elif action == "home":
        context.user_data.pop("waiting_player_id", None)

        await query.edit_message_text(
            "👑 ZADX POINTS STORE\n\nاختر من القائمة:",
            reply_markup=menu(),
        )


# =========================
# PLAYER ID MESSAGE
# =========================

async def handle_player_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    uid = update.effective_user.id
    pending = context.user_data.get("waiting_player_id")

    if not pending:
        return

    player_id = (update.message.text or "").strip()

    if not player_id.isdigit() or not (5 <= len(player_id) <= 20):
        await update.message.reply_text(
            "❌ Player ID غير صحيح.\n"
            "أرسل الأرقام فقط، وحاول مرة أخرى."
        )
        return

    name = pending["name"]
    price = pending["price"]
    is_test = bool(pending.get("is_test", False))

    register(uid)

    try:
        db.execute("BEGIN IMMEDIATE")

        if uid != OWNER_ID and not is_test:
            result = db.execute(
                "UPDATE users SET points=points-? "
                "WHERE id=? AND points>=?",
                (price, uid, price),
            )

            if result.rowcount != 1:
                db.rollback()
                context.user_data.pop("waiting_player_id", None)

                await update.message.reply_text(
                    "❌ نقاطك غير كافية الآن.",
                    reply_markup=menu(),
                )
                return

        cursor = db.execute("""
            INSERT INTO orders
            (user_id, product, price, player_id,
             status, created_at, is_test)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (
            uid,
            name,
            price,
            player_id,
            now_utc(),
            1 if is_test else 0,
        ))

        order_id = cursor.lastrowid
        db.commit()

    except Exception as exc:
        db.rollback()
        print(f"خطأ أثناء تسجيل الطلب: {exc}")

        await update.message.reply_text(
            "❌ حدث خطأ أثناء تسجيل الطلب. حاول مرة أخرى."
        )
        return

    context.user_data.pop("waiting_player_id", None)

    if is_test:
        user_message = (
            "🧪 تم تسجيل طلبك التجريبي!\n\n"
            f"💎 الباقة: {name}\n"
            f"🆔 Player ID: {player_id}\n"
            f"📦 رقم الطلب: #{order_id}\n\n"
            "⚠️ لم يتم شحن الجواهر.\n"
            "⚠️ لم يتم خصم أي نقاط.\n"
            "الطلب ينتظر مراجعة الإدارة."
        )
    else:
        user_message = (
            "✅ تم تسجيل طلبك بنجاح!\n\n"
            f"💎 الباقة: {name}\n"
            f"🆔 Player ID: {player_id}\n"
            f"🪙 السعر: {price} نقطة\n"
            f"📦 رقم الطلب: #{order_id}\n\n"
            "⏳ طلبك قيد المراجعة من الإدارة."
        )

    await update.message.reply_text(
        user_message,
        reply_markup=menu(),
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأكيد الطلب",
                callback_data=f"order:approve:{order_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ رفض الطلب",
                callback_data=f"order:reject:{order_id}",
            )
        ],
    ])

    await notify_owner(
        context,
        "📦 طلب Free Fire جديد!\n\n"
        f"رقم الطلب: #{order_id}\n"
        f"المستخدم: {uid}\n"
        f"الباقة: {name}\n"
        f"Player ID: {player_id}\n"
        f"السعر التجريبي: {price} نقطة\n"
        f"النوع: {'🧪 تجريبي' if is_test else 'عادي'}\n"
        "الحالة: قيد المراجعة",
        keyboard,
    )


# =========================
# ADD POINTS
# =========================

async def addpoints(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != OWNER_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "طريقة الاستعمال:\n"
            "/addpoints USER_ID AMOUNT\n\n"
            "مثال:\n"
            "/addpoints 123456789 100"
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
            (amount, target),
        )
        db.commit()

        await update.message.reply_text(
            f"✅ تمت إضافة {amount} نقطة للمستخدم {target}."
        )

        try:
            await context.bot.send_message(
                target,
                f"🎁 تمت إضافة {amount} نقطة إلى رصيدك في ZADX POINTS STORE.",
            )
        except Exception:
            pass

    except ValueError:
        await update.message.reply_text(
            "❌ تحقق من الأرقام والمبلغ."
        )


# =========================
# MAIN
# =========================

def main():
    if not TOKEN or not OWNER_ID:
        raise RuntimeError(
            "يجب ضبط BOT_TOKEN و OWNER_ID في متغيرات البيئة."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpoints", addpoints))
    app.add_handler(CallbackQueryHandler(buttons))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_player_id,
        )
    )

    print("ZADX POINTS STORE is running!")

    app.run_polling()


if __name__ == "__main__":
    main()
