# bot.py
# IELTS Maxing Bot - Referal link to'liq ishlaydigan versiya

import os
import sqlite3
from datetime import datetime
from typing import Tuple, List

import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    CallbackQuery, Message
)
from dotenv import load_dotenv

# ==================== KONFIGURATSIYA ====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_1 = int(os.getenv("ADMIN_1", 0))
ADMIN_2 = int(os.getenv("ADMIN_2", 0))
ZET_ID = int(os.getenv("ZET_ID", 0))

ADMIN_IDS = [ADMIN_1, ADMIN_2, ZET_ID]
ADMIN_IDS = [aid for aid in ADMIN_IDS if aid != 0]

CHANNELS = {
    "HayotMax": "@hayotmax",
    "Uyg'onish Books": "@uygonishbooks",
    "HayotMax IELTS": "@hayotmax_ielts"
}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            referrer_id INTEGER DEFAULT NULL,
            refer_ball INTEGER DEFAULT 0,
            joined_date TEXT NOT NULL,
            username TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database tayyor")

init_db()

def get_db_connection():
    return sqlite3.connect('database.db')

def user_exists(user_id: int) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone() is not None
    conn.close()
    return result

def register_user(user_id: int, full_name: str, phone: str, username: str, referrer_id: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute('''
        INSERT INTO users (user_id, full_name, phone, referrer_id, refer_ball, joined_date, username, is_active)
        VALUES (?, ?, ?, ?, 0, ?, ?, 1)
    ''', (user_id, full_name, phone, referrer_id, now, username))
    conn.commit()
    
    # Agar referrer bo'lsa, unga ball qo'shamiz
    if referrer_id and referrer_id != user_id:
        c.execute("SELECT 1 FROM users WHERE user_id = ?", (referrer_id,))
        if c.fetchone():
            c.execute("UPDATE users SET refer_ball = refer_ball + 1 WHERE user_id = ?", (referrer_id,))
            c.execute('''
                INSERT INTO referrals (referrer_id, referred_id, date)
                VALUES (?, ?, ?)
            ''', (referrer_id, user_id, now))
            conn.commit()
            
            try:
                new_ball = get_user_ball(referrer_id)
                bot.send_message(
                    referrer_id,
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"Sizning referal linkingiz orqali <b>{full_name}</b> ismli foydalanuvchi botga qo'shildi!\n"
                    f"⭐ Sizning ballaringiz <b>+1</b> ga oshdi. (Jami: {new_ball})"
                )
            except:
                pass
    
    conn.close()

def get_user_ball(user_id: int) -> int:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT refer_ball FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_total_users_count() -> int:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    result = c.fetchone()[0]
    conn.close()
    return result

def get_top10_users() -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT full_name, refer_ball FROM users 
        WHERE is_active = 1 
        ORDER BY refer_ball DESC LIMIT 10
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_all_users_for_admin() -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, full_name, phone, refer_ball, username, joined_date, is_active, referrer_id 
        FROM users ORDER BY refer_ball DESC
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_referral_tree() -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT r.referrer_id, u1.full_name, u1.username, r.referred_id, u2.full_name, u2.username, r.date
        FROM referrals r
        JOIN users u1 ON r.referrer_id = u1.user_id
        JOIN users u2 ON r.referred_id = u2.user_id
        ORDER BY r.date DESC
    ''')
    result = c.fetchall()
    conn.close()
    return result

def update_user_activity(user_id: int, is_active: int):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
    conn.commit()
    conn.close()

def get_referred_users(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, full_name, username, phone, joined_date
        FROM users WHERE referrer_id = ?
    ''', (user_id,))
    result = c.fetchall()
    conn.close()
    return result

def change_user_ball(user_id: int, change: int, admin_id: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET refer_ball = refer_ball + ? WHERE user_id = ? AND refer_ball + ? >= 0", 
              (change, user_id, change))
    conn.commit()
    c.execute("SELECT refer_ball FROM users WHERE user_id = ?", (user_id,))
    new_ball = c.fetchone()[0]
    conn.close()
    return new_ball

def deduct_ball_for_unsubscribe(user_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0]:
        referrer_id = result[0]
        c.execute("UPDATE users SET refer_ball = refer_ball - 1 WHERE user_id = ? AND refer_ball > 0", (referrer_id,))
        conn.commit()
        try:
            new_ball = get_user_ball(referrer_id)
            bot.send_message(
                referrer_id,
                f"⚠️ <b>Diqqat!</b>\n\nSiz taklif qilgan foydalanuvchi kanaldan chiqdi.\nSizning ballaringizdan <b>-1</b> ayirildi. (Jami: {new_ball})"
            )
        except:
            pass
    conn.close()

# ==================== OBUNA TEKSHIRISH ====================
def check_subscriptions(user_id: int) -> Tuple[bool, List[str]]:
    not_subscribed = []
    for name, channel_username in CHANNELS.items():
        try:
            member = bot.get_chat_member(channel_username, user_id)
            if member.status in ["left", "kicked"]:
                not_subscribed.append(name)
        except Exception:
            not_subscribed.append(name)
    return len(not_subscribed) == 0, not_subscribed

# ==================== TUGMALAR ====================
def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("👥 Referal"),
        KeyboardButton("📊 Dashboard"),
        KeyboardButton("👤 Mening ma'lumotlarim")
    ]
    keyboard.add(*buttons)
    
    if user_id in ADMIN_IDS:
        keyboard.add(KeyboardButton("⚙️ Admin panel"))
    
    return keyboard

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    for name, link in CHANNELS.items():
        keyboard.add(InlineKeyboardButton(f"📢 {name}", url=f"https://t.me/{link[1:]}"))
    keyboard.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    return keyboard

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👥 Barcha foydalanuvchilar", callback_data="admin_users"),
        InlineKeyboardButton("🔗 Kim kimni taklif qilgan", callback_data="admin_referrals"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton("⚡ ZET ballini o'zgartirish", callback_data="admin_zet_ball"),
        InlineKeyboardButton("❌ Yopish", callback_data="admin_close")
    )
    return keyboard

def get_zet_ball_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ +1 ball", callback_data="zet_add"),
        InlineKeyboardButton("➖ -1 ball", callback_data="zet_remove")
    )
    keyboard.add(InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back"))
    return keyboard

# ==================== HANDLERLAR ====================
@bot.message_handler(commands=['start'])
def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text
    
    # 🔥 REFERAL ID NI OLISH 🔥
    referrer_id = None
    if ' ' in text:
        parts = text.split(' ')
        if len(parts) > 1 and parts[1].isdigit():
            referrer_id = int(parts[1])
            if referrer_id == user_id:
                referrer_id = None
    
    print(f"📌 User: {user_id}, Referrer: {referrer_id}")  # Debug
    
    # Obunani tekshirish
    is_subscribed, not_subscribed = check_subscriptions(user_id)
    
    if not is_subscribed:
        text_msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for name in not_subscribed:
            text_msg += f"🔹 {name}\n"
        text_msg += "\n✅ Obuna bo'lgach tugmani bosing!"
        bot.send_message(user_id, text_msg, reply_markup=get_subscription_keyboard())
        return
    
    # Ro'yxatdan o'tmagan bo'lsa
    if not user_exists(user_id):
        msg = bot.send_message(
            user_id,
            "🌟 <b>IELTS Maxing</b> botiga xush kelibsiz!\n\n📝 <b>Ismingizni kiriting:</b>",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, process_fullname, referrer_id, username)
    else:
        send_main_menu(user_id)

def process_fullname(message: Message, referrer_id: int, username: str):
    user_id = message.from_user.id
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        msg = bot.send_message(user_id, "❌ Ismingizni to'g'ri kiriting (kamida 2 harf):")
        bot.register_next_step_handler(msg, process_fullname, referrer_id, username)
        return
    
    phone_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    phone_keyboard.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    
    msg = bot.send_message(
        user_id,
        "📞 <b>Telefon raqamingizni yuboring:</b>",
        reply_markup=phone_keyboard
    )
    bot.register_next_step_handler(msg, process_phone, full_name, referrer_id, username)

def process_phone(message: Message, full_name: str, referrer_id: int, username: str):
    user_id = message.from_user.id
    
    if not message.contact:
        msg = bot.send_message(
            user_id, 
            "❌ Tugma orqali raqam yuboring!",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        )
        bot.register_next_step_handler(msg, process_phone, full_name, referrer_id, username)
        return
    
    phone = message.contact.phone_number
    
    # Ro'yxatga olish
    register_user(user_id, full_name, phone, username, referrer_id)
    
    if referrer_id and referrer_id != user_id:
        msg_text = f"✅ <b>{full_name}</b>, ro'yxatdan o'tdingiz!\n\n🎉 Siz referal link orqali keldingiz! Taklif qilgan insonga <b>+1 ball</b> qo'shildi."
    else:
        msg_text = f"✅ <b>{full_name}</b>, ro'yxatdan o'tdingiz!"
    
    bot.send_message(user_id, msg_text, reply_markup=get_main_keyboard(user_id))

def send_main_menu(user_id: int):
    text = "🏠 <b>Asosiy menyu</b>"
    bot.send_message(user_id, text, reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda message: message.text == "👥 Referal")
def handle_referal(message: Message):
    user_id = message.from_user.id
    
    if not user_exists(user_id):
        bot.send_message(user_id, "❌ /start bosing!")
        return
    
    # Obunani tekshirish
    is_subscribed, _ = check_subscriptions(user_id)
    if not is_subscribed:
        bot.send_message(user_id, "❌ Kanallarga obuna bo'ling!", reply_markup=get_subscription_keyboard())
        return
    
    ball = get_user_ball(user_id)
    bot_username = bot.get_me().username
    referal_link = f"https://t.me/{bot_username}?start={user_id}"
    referred_count = len(get_referred_users(user_id))
    
    text = (
        "🌟 <b>Referal tizimi</b> 🌟\n\n"
        f"📊 Sizning ballaringiz: <b>{ball}</b>\n"
        f"👥 Taklif qilganlar: <b>{referred_count}</b> ta\n\n"
        "🔗 <b>Referal linkingiz:</b>\n"
        f"<code>{referal_link}</code>\n\n"
        "💡 Do'stingiz linkni bossa, u ro'yxatdan o'tganda siz <b>+1 ball</b> olasiz!"
    )
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "📊 Dashboard")
def handle_dashboard(message: Message):
    user_id = message.from_user.id
    
    if not user_exists(user_id):
        bot.send_message(user_id, "❌ /start bosing!")
        return
    
    is_subscribed, _ = check_subscriptions(user_id)
    if not is_subscribed:
        bot.send_message(user_id, "❌ Kanallarga obuna bo'ling!", reply_markup=get_subscription_keyboard())
        return
    
    total_users = get_total_users_count()
    top10 = get_top10_users()
    
    text = f"📈 <b>Dashboard</b> 📈\n\n"
    text += f"👥 <b>Umumiy foydalanuvchilar:</b> {total_users}\n\n"
    text += "🏆 <b>Top 10:</b>\n"
    
    if top10:
        for i, (name, ball) in enumerate(top10, 1):
            text += f"{i}. {name[:20]} - {ball} ball\n"
    else:
        text += "📭 Ma'lumot yo'q\n"
    
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "👤 Mening ma'lumotlarim")
def handle_my_info(message: Message):
    user_id = message.from_user.id
    
    if not user_exists(user_id):
        bot.send_message(user_id, "❌ /start bosing!")
        return
    
    is_subscribed, _ = check_subscriptions(user_id)
    if not is_subscribed:
        bot.send_message(user_id, "❌ Kanallarga obuna bo'ling!", reply_markup=get_subscription_keyboard())
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT full_name, phone, refer_ball, joined_date, username, referrer_id FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        username_text = f"@{user[4]}" if user[4] else "Yo'q"
        
        referrer_text = "Yo'q"
        if user[5]:
            conn2 = get_db_connection()
            c2 = conn2.cursor()
            c2.execute("SELECT full_name FROM users WHERE user_id = ?", (user[5],))
            ref = c2.fetchone()
            if ref:
                referrer_text = ref[0]
            conn2.close()
        
        text = (
            "👤 <b>Ma'lumotlarim</b>\n\n"
            f"📛 Ism: {user[0]}\n"
            f"📞 Tel: {user[1]}\n"
            f"⭐ Ball: {user[2]}\n"
            f"👤 Nom: {username_text}\n"
            f"📅 Qo'shilgan: {user[3]}\n"
            f"👥 Kim taklif qilgan: {referrer_text}\n"
        )
        bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "⚙️ Admin panel")
def handle_admin_panel(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "❌ Admin emassiz!")
        return
    
    bot.send_message(user_id, "⚙️ <b>Admin panel</b>", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call: CallbackQuery):
    user_id = call.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Admin emassiz!", show_alert=True)
        return
    
    if call.data == "admin_users":
        users = get_all_users_for_admin()
        text = "👥 <b>Barcha foydalanuvchilar:</b>\n\n"
        
        for user in users[:30]:
            username_text = f"@{user[4]}" if user[4] else "Yo'q"
            status = "✅ Faol" if user[6] else "❌ Faol emas"
            
            referrer_text = "Yo'q"
            if user[7]:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT full_name FROM users WHERE user_id = ?", (user[7],))
                ref = c.fetchone()
                if ref:
                    referrer_text = ref[0]
                conn.close()
            
            text += (
                f"🆔 ID: <code>{user[0]}</code>\n"
                f"📛 Ism: {user[1]}\n"
                f"📞 Tel: {user[2]}\n"
                f"👤 Username: {username_text}\n"
                f"⭐ Ball: {user[3]}\n"
                f"👥 Kim taklif qilgan: {referrer_text}\n"
                f"📅 Qo'shilgan: {user[5]}\n"
                f"{status}\n{'-'*30}\n"
            )
        
        bot.edit_message_text(text[:4000], user_id, call.message.message_id)
    
    elif call.data == "admin_referrals":
        refs = get_referral_tree()
        if refs:
            text = "🔗 <b>Kim kimni taklif qilgan:</b>\n\n"
            for ref in refs[:30]:
                text += f"👤 {ref[1]} (@{ref[2]}) → 👤 {ref[4]} (@{ref[5]})\n📅 {ref[6]}\n{'-'*20}\n"
            bot.edit_message_text(text[:4000], user_id, call.message.message_id)
        else:
            bot.edit_message_text("📭 Referal yo'q", user_id, call.message.message_id)
    
    elif call.data == "admin_stats":
        total = get_total_users_count()
        conn = get_db_connection()
        c = conn.cursor()
        total_balls = c.execute("SELECT SUM(refer_ball) FROM users").fetchone()[0] or 0
        total_refs = c.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        conn.close()
        
        text = (
            "📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: {total}\n"
            f"⭐ Jami ballar: {total_balls}\n"
            f"🔗 Referallar: {total_refs}\n"
            f"👑 Adminlar: {len(ADMIN_IDS)}\n"
        )
        bot.edit_message_text(text, user_id, call.message.message_id)
    
    elif call.data == "admin_zet_ball":
        text = f"⚡ <b>ZET balli</b>\n\n"
        text += f"ZET ID: <code>{ZET_ID}</code>\n"
        text += f"Joriy ball: <b>{get_user_ball(ZET_ID)}</b>\n"
        bot.edit_message_text(text, user_id, call.message.message_id, reply_markup=get_zet_ball_keyboard())
    
    elif call.data == "admin_back":
        bot.edit_message_text("⚙️ <b>Admin panel</b>", user_id, call.message.message_id, reply_markup=get_admin_keyboard())
    
    elif call.data == "admin_close":
        bot.delete_message(user_id, call.message.message_id)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ["zet_add", "zet_remove"])
def handle_zet_ball(call: CallbackQuery):
    admin_id = call.from_user.id
    
    if admin_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Admin emassiz!", show_alert=True)
        return
    
    change = 1 if call.data == "zet_add" else -1
    new_ball = change_user_ball(ZET_ID, change, admin_id)
    
    text = f"✅ ZET balli o'zgartirildi!\n\n{'+1' if change == 1 else '-1'} ball\n⭐ Yangi ball: {new_ball}"
    bot.edit_message_text(text, admin_id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call: CallbackQuery):
    user_id = call.from_user.id
    is_subscribed, not_subscribed = check_subscriptions(user_id)
    
    if is_subscribed:
        bot.delete_message(user_id, call.message.message_id)
        
        if not user_exists(user_id):
            msg = bot.send_message(
                user_id,
                "✅ Obuna tasdiqlandi!\n\n🌟 Xush kelibsiz!\n📝 <b>Ismingizni kiriting:</b>",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            bot.register_next_step_handler(msg, process_fullname, None, call.from_user.username)
        else:
            update_user_activity(user_id, 1)
            send_main_menu(user_id)
    else:
        text = "❌ Obuna bo'lmagansiz:\n"
        for name in not_subscribed:
            text += f"🔹 {name}\n"
        bot.edit_message_text(text, user_id, call.message.message_id, reply_markup=get_subscription_keyboard())
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_other(message: Message):
    user_id = message.from_user.id
    if user_exists(user_id):
        is_subscribed, _ = check_subscriptions(user_id)
        if is_subscribed:
            send_main_menu(user_id)
        else:
            bot.send_message(user_id, "❌ Kanallarga obuna bo'ling!", reply_markup=get_subscription_keyboard())
    else:
        bot.send_message(user_id, "❌ /start bosing!")

@bot.my_chat_member_handler()
def handle_leave(message):
    if message.new_chat_member.status in ["left", "kicked"]:
        user_id = message.from_user.id
        if user_exists(user_id):
            update_user_activity(user_id, 0)
            deduct_ball_for_unsubscribe(user_id)

# ==================== ISHGA TUSHIRISH ====================
if __name__ == "__main__":
    print("=" * 40)
    print("✅ IELTS Maxing bot ishga tushdi!")
    print(f"👑 Adminlar: {ADMIN_IDS}")
    print("=" * 40)
    bot.infinity_polling(skip_pending=True)