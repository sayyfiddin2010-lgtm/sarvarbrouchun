import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime

# ================== SOZLAMALAR ==================
TOKEN = "8641977994:AAHlpHGVWuyYv7W5YtXRmLCLdWrh88HNwuU"   # ← Tokeningizni qo'ying

bot = telebot.TeleBot(TOKEN)

# Adminlar
ADMINS = [5108926322, 7618889413]

# Kanallar
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
    referred_name TEXT,
    date TEXT
)
''')
conn.commit()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def create_user(user_id, first_name, username, referrer_id=None):
    joined_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, first_name, username, referrer_id, points, joined_at, is_active)
        VALUES (?, ?, ?, ?, 0, ?, 1)
    """, (user_id, first_name, username, referrer_id, joined_at))
    conn.commit()
    
    if referrer_id:
        cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        cursor.execute("INSERT INTO referrals (referrer_id, referred_id, referred_name, date) VALUES (?, ?, ?, ?)",
                      (referrer_id, user_id, first_name, joined_at))
        conn.commit()

def update_phone(user_id, phone):
    cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
    conn.commit()

def deactivate_user(user_id):
    """Foydalanuvchi bloklaganda yoki chiqib ketganda"""
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:  # referrer bor
        referrer_id = result[0]
        cursor.execute("UPDATE users SET points = points - 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        
        bot.send_message(referrer_id, 
                        "⚠️ Siz taklif qilgan foydalanuvchi botni tark etdi yoki blokladi.\n"
                        "Sizdan 1 ball ayirildi.", parse_mode='HTML')
    
    cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

def check_subscription(user_id):
    for ch in CHANNELS.values():
        try:
            member = bot.get_chat_member(ch["chat_id"], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def get_referral_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start={user_id}"

def get_top_users(limit=10):
    cursor.execute("SELECT first_name, username, points FROM users WHERE is_active=1 ORDER BY points DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_all_users_for_admin():
    cursor.execute("""
        SELECT u.first_name, u.username, u.phone, u.points, 
               (SELECT first_name FROM users WHERE user_id = u.referrer_id) as referrer_name
        FROM users u ORDER BY u.points DESC
    """)
    return cursor.fetchall()

# ================== KEYBOARDS ==================
def main_keyboard(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🔗 Referal", "📊 Dashboard")
    markup.add("👤 Mening ma'lumotlarim")
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
    username = message.from_user.username
    
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 else None
    
    if not get_user(user_id):
        create_user(user_id, first_name, username, referrer_id)
    
    if not check_subscription(user_id):
        sub_text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for ch in CHANNELS.values():
            sub_text += f"• <a href='{ch['url']}'>{ch['title']}</a>\n"
        sub_text += "\nObuna bo'lgandan so'ng <b>✅ Tekshirish</b> tugmasini bosing."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
        bot.send_message(message.chat.id, sub_text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=markup)
        return
    
    user = get_user(user_id)
    if user and not user[3]:  # phone yo'q
        bot.send_message(message.chat.id, 
                        "📱 Iltimos, telefon raqamingizni yuboring:",
                        reply_markup=phone_keyboard())
        return
    
    bot.send_message(message.chat.id, 
                    f"❤️ Assalomu alaykum, <b>{first_name}</b>!\nIELTS Maxing botga xush kelibsiz!\n\nMenyudan tanlang:",
                    reply_markup=main_keyboard(user_id in ADMINS), parse_mode='HTML')

@bot.my_chat_member_handler()
def handle_my_chat_member(update):
    """Foydalanuvchi botni bloklaganda yoki chiqib ketganda ishlaydi"""
    if update.chat.type == "private":  # faqat private chat (PM)
        new_status = update.new_chat_member.status
        old_status = update.old_chat_member.status
        
        if new_status in ['kicked', 'left'] or (new_status == 'banned'):
            deactivate_user(update.from_user.id)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "check_sub":
        if check_subscription(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Hali ham barcha kanallarga obuna bo'lmadingiz.", show_alert=True)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    update_phone(user_id, phone)
    
    bot.send_message(message.chat.id, 
                    "✅ Telefon raqamingiz qabul qilindi!\nEndi botdan to'liq foydalanishingiz mumkin ❤️",
                    reply_markup=main_keyboard(user_id in ADMINS))

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    
    if not check_subscription(user_id):
        bot.send_message(message.chat.id, "Iltimos, avval kanallarga obuna bo'ling!")
        return
    
    user = get_user(user_id)
    if user and not user[3]:
        bot.send_message(message.chat.id, "Iltimos, telefon raqamingizni yuboring.", reply_markup=phone_keyboard())
        return
    
    if text == "🔗 Referal":
        link = get_referral_link(user_id)
        bot.send_message(message.chat.id,
                        f"🔗 <b>Sizning referal linkingiz:</b>\n\n<code>{link}</code>\n\n"
                        "Do'stlaringizga yuboring. Har bir yangi do'st uchun +1 ball! ❤️",
                        parse_mode='HTML')
    
    elif text == "📊 Dashboard":
        user = get_user(user_id)
        points = user[4] if user else 0
        top = get_top_users(10)
        
        top_text = "\n🏆 <b>Top 10:</b>\n"
        for i, (name, uname, pts) in enumerate(top, 1):
            top_text += f"{i}. {name} — {pts} ball\n"
        
        bot.send_message(message.chat.id,
                        f"📊 <b>Dashboard</b>\n\n"
                        f"Ballaringiz: <b>{points}</b>\n"
                        f"{top_text}",
                        parse_mode='HTML')
    
    elif text == "👤 Mening ma'lumotlarim":
        user = get_user(user_id)
        bot.send_message(message.chat.id,
                        f"👤 <b>Ma'lumotlaringiz:</b>\n\n"
                        f"🆔 ID: <code>{user[0]}</code>\n"
                        f"👤 Ism: {user[1]}\n"
                        f"🔗 Username: @{user[2] or 'yo\'q'}\n"
                        f"📱 Telefon: {user[3]}\n"
                        f"⭐ Ball: {user[4]}\n"
                        f"📅 Ro'yxatdan o'tgan: {user[5]}",
                        parse_mode='HTML')
    
    elif text == "⚙️ Admin Panel" and user_id in ADMINS:
        users = get_all_users_for_admin()
        msg = f"⚙️ <b>Admin Panel</b>\nJami foydalanuvchilar: {len(users)}\n\n"
        for u in users[:30]:
            msg += f"• {u[0]} | @{u[1] or '—'} | {u[2]} | {u[3]} ball | Ref: {u[4] or '—'}\n"
        bot.send_message(message.chat.id, msg, parse_mode='HTML')

    else:
        bot.send_message(message.chat.id, "Quyidagi tugmalardan foydalaning ❤️", 
                        reply_markup=main_keyboard(user_id in ADMINS))

# ================== BOTNI ISHGA TUSHIRISH ==================
if __name__ == "__main__":
    print("✅ IELTS Maxing boti muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()