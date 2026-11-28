
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
        SELECT id, user_id, product, price,
               player_id, status
        FROM orders
        ORDER BY id DESC
        LIMIT 8 OFFSET ?
    """, (page * 8,)).fetchall()

    text = (
        "📋 سجل طلبات ZADX\n\n"
        f"📦 مجموع الطلبات: {total}\n"
        f"⏳ قيد المراجعة: {pending}\n"
        f"✅ مكتملة: {completed}\n"
        f"❌ ملغاة: {refunded}\n\n"
        "👇 اضغط على أي طلب لعرض تفاصيله:"
    )

    keyboard = []

    for order in orders:
        oid, user, product, price, player, status = order

        status_icon = {
            "pending": "⏳",
            "completed": "✅",
            "refunded": "❌"
        }.get(status, "❔")

        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} الطلب #{oid} - {product}",
                callback_data=f"order_view:{oid}:{page}"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"admin_orders:{page-1}"
            )
        )

    if (page + 1) * 8 < total:
        navigation.append(
            InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"admin_orders:{page+1}"
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append([
        InlineKeyboardButton(
            "🔄 تحديث",
            callback_data=f"admin_orders:{page}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 لوحة الإدارة",
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
            "❌ الطلب غير موجود.",
            reply_markup=admin_keyboard()
        )
        return

    oid, user, product, price, player, status, created = order

    status_text = {
        "pending": "⏳ قيد المراجعة",
        "completed": "✅ مكتمل",
        "refunded": "❌ ملغى ومسترجع"
    }.get(status, status)

    text = (
        f"📦 تفاصيل الطلب #{oid}\n\n"
        "━━━━━━━━━━━━\n"
        f"👤 المستخدم: {user}\n"
        f"💎 الباقة: {product}\n"
        f"🆔 Player ID: {player}\n"
        f"🪙 السعر: {price} نقطة\n"
        f"📌 الحالة: {status_text}\n"
        f"📅 التاريخ: {created or 'غير متوفر'}\n"
        "━━━━━━━━━━━━"
    )

    keyboard = []

    if status == "pending":
        keyboard.append([
            InlineKeyboardButton(
                "✅ تأكيد إتمام الشحن",
                callback_data=f"order:approve:{oid}"
            )
        ])

        keyboard.append([
            InlineKeyboardButton(
                "❌ رفض وإرجاع النقاط",
                callback_data=f"order:reject:{oid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 رجوع إلى سجل الطلبات",
            callback_data=f"admin_orders:{page}"
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
