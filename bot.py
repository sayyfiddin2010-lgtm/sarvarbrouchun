# bot.py
# IELTS Maxing Bot - To'liq tuzatilgan versiya

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

# Adminlar ro'yxati
ADMIN_IDS = [ADMIN_1, ADMIN_2, ZET_ID]
ADMIN_IDS = [aid for aid in ADMIN_IDS if aid != 0]

# 3 TA KANAL
CHANNELS = {
    "HayotMax": "@hayotmax",
    "Uyg'onish Books": "@uygonishbooks",
    "HayotMax IELTS": "@hayotmax_ielts"
}

# ==================== BOT ====================
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

# ==================== DATABASE FUNKSIYALARI ====================
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
    
    # Referal ball qo'shish (FAQAT referrer_id bo'lsa)
    if referrer_id and referrer_id != user_id:
        # Referrer mavjudligini tekshirish
        c.execute("SELECT 1 FROM users WHERE user_id = ?", (referrer_id,))
        if c.fetchone():
            c.execute("UPDATE users SET refer_ball = refer_ball + 1 WHERE user_id = ?", (referrer_id,))
            c.execute('''
                INSERT INTO referrals (referrer_id, referred_id, date)
                VALUES (?, ?, ?)
            ''', (referrer_id, user_id, now))
            conn.commit()
            
            # Referal qilgan odamga habar yuborish
            try:
                ball = get_user_ball(referrer_id)
                bot.send_message(
                    referrer_id, 
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"Sizning referal linkingiz orqali <b>{full_name}</b> ismli foydalanuvchi botga qo'shildi!\n"
                    f"⭐ Sizning ballaringiz <b>+1</b> ga oshdi. (Jami: {ball})"
                )
            except Exception as e:
                print(f"Xabar yuborishda xatolik: {e}")
    
    conn.close()

def deduct_ball_from_referrer(user_id: int):
    """Foydalanuvchi botni tark etsa, refererdan ball ayirish"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
    result = c.fetchone()
    if result and result[0]:
        referrer_id = result[0]
        c.execute("UPDATE users SET refer_ball = refer_ball - 1 WHERE user_id = ? AND refer_ball > 0", (referrer_id,))
        conn.commit()
        
        # Ball ayirilgani haqida habar
        try:
            bot.send_message(
                referrer_id,
                f"⚠️ <b>Diqqat!</b>\n\n"
                f"Siz taklif qilgan foydalanuvchi botni tark etdi.\n"
                f"Sizning ballaringizdan <b>-1</b> ayirildi."
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
        SELECT user_id, full_name, phone, refer_ball, username, joined_date, is_active 
        FROM users ORDER BY refer_ball DESC
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_referral_tree() -> List[Tuple]:
    """Kim kimni taklif qilgan - to'liq ma'lumot"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT 
            r.referrer_id, 
            u1.full_name as referrer_name, 
            u1.username as referrer_username,
            u1.phone as referrer_phone,
            r.referred_id, 
            u2.full_name as referred_name, 
            u2.username as referred_username,
            u2.phone as referred_phone,
            r.date
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

def get_referrer_info(user_id: int):
    """Foydalanuvchini kim taklif qilganini olish"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_referred_users(user_id: int) -> List[Tuple]:
    """Foydalanuvchi kimlarni taklif qilgan"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT u.user_id, u.full_name, u.username, u.phone, u.joined_date 
        FROM users u
        WHERE u.referrer_id = ? AND u.is_active = 1
    ''', (user_id,))
    result = c.fetchall()
    conn.close()
    return result

# ==================== OBUNA TEKSHIRISH (HAR DOIM) ====================
def check_subscriptions(user_id: int) -> Tuple[bool, List[str]]:
    """Foydalanuvchi barcha kanallarga obuna bo'lganmi? HAR DOIM TEKSHIRADI"""
    not_subscribed = []
    for name, channel_username in CHANNELS.items():
        try:
            member = bot.get_chat_member(channel_username, user_id)
            if member.status in ["left", "kicked"]:
                not_subscribed.append(name)
        except Exception as e:
            print(f"Kanal tekshirish xatosi {name}: {e}")
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
        InlineKeyboardButton("❌ Yopish", callback_data="admin_close")
    )
    return keyboard

# ==================== OBUNA FILTRI ====================
def subscription_required(func):
    """Dekorator - har bir xabardan oldin obunani tekshiradi"""
    def wrapper(message):
        user_id = message.from_user.id
        
        # Ro'yxatdan o'tmagan bo'lsa, start ga yuborish
        if not user_exists(user_id):
            bot.send_message(user_id, "❌ Iltimos, avval /start buyrug'ini bosing!")
            return
        
        # Obunani tekshirish
        is_subscribed, not_subscribed = check_subscriptions(user_id)
        
        if not is_subscribed:
            text = "❌ <b>IELTS Maxing</b> botidan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
            for name in not_subscribed:
                text += f"🔹 {name}\n"
            text += "\n✅ Obuna bo'lgach <b>Obunani tekshirish</b> tugmasini bosing!"
            bot.send_message(user_id, text, reply_markup=get_subscription_keyboard())
            return
        
        return func(message)
    return wrapper

# ==================== HANDLERLAR ====================
@bot.message_handler(commands=['start'])
def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text
    
    # Referal ID ni olish
    referrer_id = None
    parts = text.split()
    if len(parts) > 1:
        try:
            referrer_id = int(parts[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass
    
    print(f"📝 Yangi foydalanuvchi: {user_id}, Referrer: {referrer_id}")
    
    # Obunani tekshirish
    is_subscribed, not_subscribed = check_subscriptions(user_id)
    
    if not is_subscribed:
        text_msg = "❌ <b>IELTS Maxing</b> botidan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for name in not_subscribed:
            text_msg += f"🔹 {name}\n"
        text_msg += "\n✅ Obuna bo'lgach <b>Obunani tekshirish</b> tugmasini bosing!"
        bot.send_message(user_id, text_msg, reply_markup=get_subscription_keyboard())
        return
    
    # Agar foydalanuvchi ro'yxatdan o'tmagan bo'lsa
    if not user_exists(user_id):
        msg = bot.send_message(
            user_id,
            "🌟 <b>IELTS Maxing</b> botiga xush kelibsiz! 🌟\n\n"
            "IELTS imtihoniga tayyorgarlik ko'rayotganlar uchun eng yaxshi bot!\n\n"
            "📝 <b>Iltimos, o'z ismingizni kiriting:</b>",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, process_fullname, referrer_id, username)
    else:
        send_main_menu(user_id)

def process_fullname(message: Message, referrer_id: int, username: str):
    user_id = message.from_user.id
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        msg = bot.send_message(user_id, "❌ Iltimos, haqiqiy ismingizni kiriting (kamida 2 harf):")
        bot.register_next_step_handler(msg, process_fullname, referrer_id, username)
        return
    
    phone_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    phone_keyboard.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    
    msg = bot.send_message(
        user_id,
        "📞 <b>Endi telefon raqamingizni yuboring.</b>\n\n👇 Pastdagi tugmani bosing:",
        reply_markup=phone_keyboard
    )
    bot.register_next_step_handler(msg, process_phone, full_name, referrer_id, username)

def process_phone(message: Message, full_name: str, referrer_id: int, username: str):
    user_id = message.from_user.id
    
    if not message.contact:
        msg = bot.send_message(
            user_id, 
            "❌ Iltimos, pastdagi tugma orqali telefon raqamingizni yuboring!",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        )
        bot.register_next_step_handler(msg, process_phone, full_name, referrer_id, username)
        return
    
    phone = message.contact.phone_number
    
    # Foydalanuvchini ro'yxatga olish
    register_user(user_id, full_name, phone, username, referrer_id)
    
    if referrer_id and referrer_id != user_id:
        ball_text = "\n\n🎉 Sizga <b>+1 ball</b> qo'shildi (referal orqali keldingiz)!"
    else:
        ball_text = ""
    
    bot.send_message(
        user_id,
        f"✅ <b>{full_name}</b>, ro'yxatdan o'tish muvaffaqiyatli yakunlandi!{ball_text}\n\n"
        f"🎉 Endi siz IELTS Maxing botidan to'liq foydalanishingiz mumkin.\n"
        f"👥 Do'stlaringizni taklif qiling va ballar yig'ing!",
        reply_markup=get_main_keyboard(user_id)
    )

def send_main_menu(user_id: int):
    text = "🏠 <b>Asosiy menyu</b>\n\nQuyidagi tugmalar orqali botdan foydalanishingiz mumkin:"
    bot.send_message(user_id, text, reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda message: message.text == "👥 Referal")
@subscription_required
def handle_referal(message: Message):
    user_id = message.from_user.id
    ball = get_user_ball(user_id)
    bot_username = bot.get_me().username
    referal_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Taklif qilganlar soni
    referred_count = len(get_referred_users(user_id))
    
    text = (
        "🌟 <b>Referal tizimi</b> 🌟\n\n"
        f"📊 Sizning ballaringiz: <b>{ball}</b>\n"
        f"👥 Taklif qilgan do'stlar: <b>{referred_count}</b> ta\n\n"
        "👥 Do'stlaringizni taklif qiling va ball yig'ing!\n"
        "Har bir taklif qilgan do'stingiz uchun <b>1 ball</b> olasiz.\n\n"
        "🔗 <b>Sizning referal linkingiz:</b>\n"
        f"<code>{referal_link}</code>\n\n"
        "💡 Do'stlaringizga yuboring, ular botga kirganda siz avtomatik ball olasiz!"
    )
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "📊 Dashboard")
@subscription_required
def handle_dashboard(message: Message):
    user_id = message.from_user.id
    total_users = get_total_users_count()
    top10 = get_top10_users()
    
    text = f"📈 <b>Dashboard</b> 📈\n\n"
    text += f"👥 <b>Umumiy foydalanuvchilar:</b> {total_users}\n\n"
    text += "🏆 <b>Top 10 (Referal ball bo'yicha):</b>\n"
    
    if top10:
        for i, (name, ball) in enumerate(top10, 1):
            text += f"{i}. {name[:20]} - {ball} ball\n"
    else:
        text += "📭 Hozircha ma'lumot yo'q\n"
    
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "👤 Mening ma'lumotlarim")
@subscription_required
def handle_my_info(message: Message):
    user_id = message.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT full_name, phone, refer_ball, joined_date, username, referrer_id FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        username_text = f"@{user[4]}" if user[4] else "Yo'q"
        
        # Kim taklif qilganini topish
        referrer_text = "Yo'q"
        if user[5]:
            c2 = conn = get_db_connection()
            c2.execute("SELECT full_name FROM users WHERE user_id = ?", (user[5],))
            referrer = c2.fetchone()
            if referrer:
                referrer_text = referrer[0]
            conn.close()
        
        text = (
            "👤 <b>Mening ma'lumotlarim</b>\n\n"
            f"📛 <b>Ism:</b> {user[0]}\n"
            f"📞 <b>Telefon:</b> {user[1]}\n"
            f"⭐ <b>Referal ball:</b> {user[2]}\n"
            f"👤 <b>Username:</b> {username_text}\n"
            f"📅 <b>Qo'shilgan sana:</b> {user[3]}\n"
            f"👥 <b>Kim taklif qilgan:</b> {referrer_text}\n"
        )
        bot.send_message(user_id, text)

@bot.message_handler(func=lambda message: message.text == "⚙️ Admin panel")
def handle_admin_panel(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "❌ Siz admin emassiz!")
        send_main_menu(user_id)
        return
    
    bot.send_message(
        user_id,
        "⚙️ <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call: CallbackQuery):
    user_id = call.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    if call.data == "admin_users":
        users = get_all_users_for_admin()
        text = "👥 <b>Barcha foydalanuvchilar:</b>\n\n"
        
        for user in users[:30]:
            username_text = f"@{user[4]}" if user[4] else "Yo'q"
            status = "✅ Faol" if user[6] else "❌ Faol emas"
            text += (
                f"🆔 ID: <code>{user[0]}</code>\n"
                f"📛 Ism: {user[1]}\n"
                f"📞 Tel: {user[2]}\n"
                f"👤 Username: {username_text}\n"
                f"⭐ Ball: {user[3]}\n"
                f"📅 Qo'shilgan: {user[5]}\n"
                f"{status}\n"
                f"{'─' * 30}\n"
            )
        
        if len(users) > 30:
            text += f"\n... va yana {len(users)-30} ta foydalanuvchi"
        
        bot.edit_message_text(text[:4000], user_id, call.message.message_id)
        
    elif call.data == "admin_referrals":
        refs = get_referral_tree()
        if refs:
            text = "🔗 <b>Kim kimni taklif qilgan:</b>\n\n"
            for ref in refs[:30]:
                referrer_info = f"{ref[1]} (@{ref[2]})" if ref[2] else f"{ref[1]} (tel: {ref[3]})"
                referred_info = f"{ref[5]} (@{ref[6]})" if ref[6] else f"{ref[5]} (tel: {ref[7]})"
                text += f"👤 {referrer_info}\n   ↓\n👤 {referred_info}\n📅 {ref[8]}\n\n{'─' * 20}\n\n"
            bot.edit_message_text(text[:4000], user_id, call.message.message_id)
        else:
            bot.edit_message_text("📭 Hozircha hech qanday referal mavjud emas.", user_id, call.message.message_id)
    
    elif call.data == "admin_stats":
        total = get_total_users_count()
        conn = get_db_connection()
        c = conn.cursor()
        active = c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
        total_balls = c.execute("SELECT SUM(refer_ball) FROM users").fetchone()[0] or 0
        total_referrals = c.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        conn.close()
        
        text = (
            "📊 <b>Bot statistikasi</b>\n\n"
            f"👥 Jami foydalanuvchilar: {total}\n"
            f"✅ Faol foydalanuvchilar: {active}\n"
            f"⭐ Jami berilgan ballar: {total_balls}\n"
            f"🔗 Jami referallar: {total_referrals}\n"
            f"👑 Adminlar soni: {len(ADMIN_IDS)}\n"
        )
        bot.edit_message_text(text, user_id, call.message.message_id)
    
    elif call.data == "admin_close":
        bot.delete_message(user_id, call.message.message_id)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call: CallbackQuery):
    user_id = call.from_user.id
    is_subscribed, not_subscribed = check_subscriptions(user_id)
    
    if is_subscribed:
        bot.delete_message(user_id, call.message.message_id)
        if not user_exists(user_id):
            # Obuna bo'ldi, endi ro'yxatdan o'tish
            msg = bot.send_message(
                user_id,
                "✅ Obuna tasdiqlandi!\n\n🌟 <b>IELTS Maxing</b> botiga xush kelibsiz!\n\n📝 <b>Iltimos, o'z ismingizni kiriting:</b>",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            bot.register_next_step_handler(msg, process_fullname, None, call.from_user.username)
        else:
            send_main_menu(user_id)
    else:
        text = "❌ Siz hali quyidagi kanallarga obuna bo'lmagansiz:\n"
        for name in not_subscribed:
            text += f"🔹 {name}\n"
        text += "\n✅ Obuna bo'lgach qaytadan tekshiring!"
        bot.edit_message_text(text, user_id, call.message.message_id, reply_markup=get_subscription_keyboard())
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
@subscription_required
def handle_other_messages(message: Message):
    send_main_menu(message.from_user.id)

@bot.my_chat_member_handler()
def handle_my_chat_member(message):
    """Foydalanuvchi botni blocklaganda yoki to'xtatganda"""
    if message.new_chat_member.status in ["left", "kicked"]:
        user_id = message.from_user.id
        if user_exists(user_id):
            update_user_activity(user_id, 0)
            deduct_ball_from_referrer(user_id)
            print(f"⚠️ User {user_id} botni tark etdi. Ball ayirildi.")

# ==================== ISHGA TUSHIRISH ====================
if __name__ == "__main__":
    print("=" * 40)
    print("✅ IELTS Maxing bot ishga tushdi!")
    print("=" * 40)
    print("📢 Kanallar:")
    for name, link in CHANNELS.items():
        print(f"   - {name}: {link}")
    print(f"👑 Adminlar: {ADMIN_IDS}")
    print("=" * 40)
    print("🚀 Bot polling rejimida ishlayapti...")
    print("=" * 40)
    bot.infinity_polling(skip_pending=True)