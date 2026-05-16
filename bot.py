import telebot
from telebot import types
import sqlite3
import logging
from datetime import datetime
import time

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================== SOZLAMALAR ==================
TOKEN = "8641977994:AAHlpHGVWuyYv7W5YtXRmLCLdWrh88HNwuU"  # ← Tokenni qo'ying!

bot = telebot.TeleBot(TOKEN)

ADMINS = [5108926322, 7618889413]

CHANNELS = {
    "hayotmax": {"url": "https://t.me/hayotmax", "title": "HayotMax", "chat_id": "@hayotmax"},
    "uygonishbooks": {"url": "https://t.me/uygonishbooks", "title": "Uyg'onish Books", "chat_id": "@uygonishbooks"},
    "hayotmax_ielts": {"url": "https://t.me/hayotmax_ielts", "title": "HayotMax IELTS", "chat_id": "@hayotmax_ielts"}
}

# ================== DATABASE ==================
conn = sqlite3.connect('ielts_maxing.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    phone TEXT,
    referrer_id INTEGER,
    points INTEGER DEFAULT 0,
    joined_at TEXT,
    is_active INTEGER DEFAULT 1
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER,
    referred_id INTEGER,
    level INTEGER,
    bonus INTEGER,
    date TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_activity (
    user_id INTEGER,
    last_activity TEXT,
    total_messages INTEGER DEFAULT 0
)
''')
conn.commit()

logger.info("✅ Database muvaffaqiyatli yuklandi")

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_activity(user_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO user_activity (user_id, last_activity, total_messages)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET 
        last_activity = excluded.last_activity,
        total_messages = total_messages + 1
    """, (user_id, now))
    conn.commit()

def add_multi_level_bonus(new_user_id, new_name, direct_referrer_id):
    if not direct_referrer_id or direct_referrer_id == new_user_id:
        return

    bonuses = [3, 2, 1]  # 1-daraja +3, 2-daraja +2, 3-daraja +1
    current = direct_referrer_id
    level = 1

    while current and level <= 3:
        bonus = bonuses[level - 1]
        
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (bonus, current))
        cursor.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, level, bonus, date)
            VALUES (?, ?, ?, ?, ?)
        """, (current, new_user_id, level, bonus, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

        try:
            if level == 1:
                msg = f"🎉 <b>Ajoyib tabriklaymiz!</b>\n\n<b>{new_name}</b> sizning to'g'ridan-to'g'ri referalingiz orqali qo'shildi!\n+{bonus} ball qo'shildi 🔥"
            else:
                msg = f"🎊 <b>{level}-daraja bonusi!</b>\n{new_name} sizning {level}-daraja zanjiringiz orqali qo'shildi!\n+{bonus} ball qo'shildi!"
            bot.send_message(current, msg, parse_mode='HTML')
        except Exception as e:
            logger.warning(f"Xabar yuborishda xatolik: {e}")
        
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (current,))
        result = cursor.fetchone()
        current = result[0] if result and result[0] else None
        level += 1


def deactivate_user(user_id):
    cursor.execute("SELECT referrer_id, first_name FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        # Direct referal uchun -3 ball
        cursor.execute("UPDATE users SET points = points - 3 WHERE user_id = ?", (result[0],))
        conn.commit()
        try:
            bot.send_message(result[0], f"⚠️ Sizning to'g'ridan referalingiz <b>{result[1]}</b> botni tark etdi yoki blokladi.\n-3 ball ayirildi.", parse_mode='HTML')
        except:
            pass
    cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()


def check_subscription(user_id):
    for channel in CHANNELS.values():
        try:
            member = bot.get_chat_member(channel["chat_id"], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True


def get_referral_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start={user_id}"


def get_statistics():
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM referrals")
    total_refs = cursor.fetchone()[0]
    return {"total": total, "active": active, "total_refs": total_refs}


def get_user_referral_stats(user_id):
    cursor.execute("SELECT level, COUNT(*) as count FROM referrals WHERE referrer_id = ? GROUP BY level", (user_id,))
    rows = cursor.fetchall()
    total = sum(row[1] for row in rows)
    stats = {row[0]: row[1] for row in rows}
    return total, stats


def get_top_referrers(limit=10):
    cursor.execute("""
        SELECT u.first_name, u.username, u.points, COUNT(r.id) as ref_count
        FROM users u 
        LEFT JOIN referrals r ON u.user_id = r.referrer_id 
        WHERE u.is_active = 1 
        GROUP BY u.user_id 
        ORDER BY ref_count DESC, u.points DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

# ================== KEYBOARDS ==================
def main_keyboard(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🔗 Referal", "📊 Dashboard")
    markup.add("👤 Mening ma'lumotlarim", "📋 Referallarim")
    if is_admin:
        markup.add("⚙️ Admin Panel")
    return markup


def phone_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    return markup

# ================== HANDLERS ==================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username or "yo'q"

    update_activity(user_id)

    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    if not get_user(user_id):
        cursor.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, first_name, username, referrer_id, joined_at) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, first_name, username, referrer_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

        if referrer_id:
            add_multi_level_bonus(user_id, first_name, referrer_id)

    if not check_subscription(user_id):
        sub_text = "📢 <b>IELTS Maxing botga xush kelibsiz!</b>\n\nBotdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for ch in CHANNELS.values():
            sub_text += f"🔸 <a href='{ch['url']}'>{ch['title']}</a>\n"
        sub_text += "\nObuna bo'lib bo'lgach <b>✅ Tekshirish</b> tugmasini bosing."

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
        bot.send_message(message.chat.id, sub_text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=markup)
        return

    user = get_user(user_id)
    if user and not user[3]:  # phone yo'q
        bot.send_message(message.chat.id, "📱 Iltimos, telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        return

    bot.send_message(message.chat.id,
        f"❤️ <b>Assalomu alaykum, {first_name}!</b>\n\n"
        "IELTS Maxing botga xush kelibsiz!\n"
        "Multi-Level Referal tizimi faol: 1-daraja +3 | 2-daraja +2 | 3-daraja +1 ball\n\n"
        "Menyudan tanlang 👇",
        parse_mode='HTML', reply_markup=main_keyboard(user_id in ADMINS))


@bot.my_chat_member_handler()
def handle_my_chat_member(update):
    if update.chat.type == "private":
        if update.new_chat_member.status in ['kicked', 'left']:
            deactivate_user(update.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna muvaffaqiyatli tasdiqlandi!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)


@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
    conn.commit()
    update_activity(user_id)
    
    bot.send_message(message.chat.id, 
        "✅ Telefon raqamingiz muvaffaqiyatli saqlandi!\n\nEndi botdan to'liq foydalanishingiz mumkin ❤️",
        reply_markup=main_keyboard(user_id in ADMINS))


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    update_activity(user_id)

    if not check_subscription(user_id):
        bot.send_message(message.chat.id, "Iltimos, avval kanallarga obuna bo'ling!")
        return

    user = get_user(user_id)
    if user and not user[3]:
        bot.send_message(message.chat.id, "📱 Telefon raqamingizni yuboring.", reply_markup=phone_keyboard())
        return

    is_admin = user_id in ADMINS

    if text == "🔗 Referal":
        link = get_referral_link(user_id)
        total, stats = get_user_referral_stats(user_id)
        bot.send_message(message.chat.id,
            f"🔗 <b>Sizning Referal Linkingiz:</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"📊 Jami referallar: <b>{total}</b>\n"
            f"1-daraja: {stats.get(1,0)} ta | 2-daraja: {stats.get(2,0)} ta | 3-daraja: {stats.get(3,0)} ta\n\n"
            f"Do'stlaringizga yuboring va ko'p ball to'plang! 🔥",
            parse_mode='HTML')

    elif text == "📋 Referallarim":
        total, stats = get_user_referral_stats(user_id)
        cursor.execute("SELECT referred_id, level, date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 20", (user_id,))
        refs = cursor.fetchall()
        
        msg = f"📋 <b>Sizning Referallaringiz</b>\n\nJami: <b>{total}</b>\n\n"
        for _, level, date in refs:
            msg += f"• {level}-daraja • {date[:10]}\n"
        if not refs:
            msg += "Hozircha referallar yo'q. Do'stlaringizni taklif qiling!"
        
        bot.send_message(message.chat.id, msg, parse_mode='HTML')

    elif text == "📊 Dashboard":
        stats = get_statistics()
        user = get_user(user_id)
        points = user[4] if user else 0
        total_ref, _ = get_user_referral_stats(user_id)
        top = get_top_referrers(10)
        
        top_text = "\n🏆 <b>Top 10 Referaller:</b>\n"
        for i, (name, uname, pts, refc) in enumerate(top, 1):
            top_text += f"{i}. {name} — {refc} ta referal ({pts} ball)\n"

        bot.send_message(message.chat.id,
            f"📊 <b>IELTS Maxing Statistika</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['total']}</b>\n"
            f"✅ Faol: <b>{stats['active']}</b>\n"
            f"🔗 Jami referallar: <b>{stats['total_refs']}</b>\n\n"
            f"⭐ Sizning ballaringiz: <b>{points}</b>\n"
            f"👥 Sizning referallaringiz: <b>{total_ref}</b>\n\n"
            f"{top_text}\n❤️ Davom eting!",
            parse_mode='HTML')

    elif text == "👤 Mening ma'lumotlarim":
        user = get_user(user_id)
        bot.send_message(message.chat.id,
            f"👤 <b>Sizning ma'lumotlaringiz:</b>\n\n"
            f"🆔 Telegram ID: <code>{user[0]}</code>\n"
            f"👤 Ism: {user[1]}\n"
            f"🔗 Username: @{user[2] or 'yo\'q'}\n"
            f"📱 Telefon: {user[3] or 'yo\'q'}\n"
            f"⭐ Ball: <b>{user[4]}</b>\n"
            f"📅 Ro'yxatdan o'tgan: {user[5]}\n"
            f"🟢 Status: {'Faol' if user[6] else 'Faol emas'}",
            parse_mode='HTML')

    elif text == "⚙️ Admin Panel" and is_admin:
        stats = get_statistics()
        msg = f"⚙️ <b>ADMIN PANEL</b>\n\nJami: {stats['total']} | Faol: {stats['active']}\n\n"
        cursor.execute("SELECT first_name, username, phone, points FROM users ORDER BY points DESC LIMIT 30")
        for row in cursor.fetchall():
            msg += f"• {row[0]} | @{row[1] or '-'} | {row[2] or '-'} | {row[3]} ball\n"
        bot.send_message(message.chat.id, msg, parse_mode='HTML')

    else:
        bot.send_message(message.chat.id, "❤️ Quyidagi tugmalardan birini bosing:", reply_markup=main_keyboard(is_admin))


# ================== BOTNI ISHGA TUSHIRISH ==================
if __name__ == "__main__":
    logger.info("🚀 IELTS Maxing Bot muvaffaqiyatli ishga tushdi...")
    print("Bot ishlamoqda... (Multi-Level Referal + To'liq funksiyalar)")
    bot.infinity_polling(none_stop=True)