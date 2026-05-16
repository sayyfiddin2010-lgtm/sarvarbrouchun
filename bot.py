# bot.py
# IELTS Maxing Bot - Referal ball hech qachon kamaymaydi

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

def get_db():
    return sqlite3.connect('database.db')

def user_exists(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_user_ball(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT refer_ball FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def register_user(user_id, full_name, phone, username, referrer_id):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute('''
        INSERT INTO users (user_id, full_name, phone, referrer_id, refer_ball, joined_date, username, is_active)
        VALUES (?, ?, ?, ?, 0, ?, ?, 1)
    ''', (user_id, full_name, phone, referrer_id, now, username))
    conn.commit()
    
    print(f"📝 Yangi foydalanuvchi: {full_name} (ID: {user_id}), Referrer: {referrer_id}")
    
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
            
            print(f"🎉 Ball qo'shildi: Referrer {referrer_id} ga +1 ball")
            
            try:
                new_ball = get_user_ball(referrer_id)
                bot.send_message(
                    referrer_id,
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"Sizning referal linkingiz orqali <b>{full_name}</b> ismli foydalanuvchi botga qo'shildi!\n"
                    f"⭐ Sizning ballaringiz <b>+1</b> ga oshdi. (Jami: {new_ball})"
                )
            except Exception as e:
                print(f"Xabar yuborishda xatolik: {e}")
    
    conn.close()
    return True

def get_total_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    result = c.fetchone()[0]
    conn.close()
    return result

def get_top10():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT full_name, refer_ball FROM users 
        ORDER BY refer_ball DESC LIMIT 10
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, full_name, phone, refer_ball, username, joined_date, referrer_id 
        FROM users ORDER BY refer_ball DESC
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_referrals():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT r.referrer_id, u1.full_name, u1.username, 
               r.referred_id, u2.full_name, u2.username, r.date
        FROM referrals r
        JOIN users u1 ON r.referrer_id = u1.user_id
        JOIN users u2 ON r.referred_id = u2.user_id
        ORDER BY r.date DESC
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_my_referrals(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, full_name, username, phone, joined_date
        FROM users WHERE referrer_id = ?
    ''', (user_id,))
    result = c.fetchall()
    conn.close()
    return result

def change_ball_admin(user_id, change):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET refer_ball = refer_ball + ? WHERE user_id = ?", (change, user_id))
    conn.commit()
    c.execute("SELECT refer_ball FROM users WHERE user_id = ?", (user_id,))
    new_ball = c.fetchone()[0]
    conn.close()
    return new_ball

# ==================== OBUNA ====================
def check_sub(user_id):
    not_sub = []
    for name, ch in CHANNELS.items():
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                not_sub.append(name)
        except:
            not_sub.append(name)
    return len(not_sub) == 0, not_sub

def sub_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for name, link in CHANNELS.items():
        kb.add(InlineKeyboardButton(f"📢 {name}", url=f"https://t.me/{link[1:]}"))
    kb.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
    return kb

def main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btns = [KeyboardButton("👥 Referal"), KeyboardButton("📊 Dashboard"), KeyboardButton("👤 Mening ma'lumotlarim")]
    kb.add(*btns)
    if user_id in ADMIN_IDS:
        kb.add(KeyboardButton("⚙️ Admin panel"))
    return kb

def admin_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 Barcha foydalanuvchilar", callback_data="admin_users"),
        InlineKeyboardButton("🔗 Referallar", callback_data="admin_refs"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton("⚡ ZET ball", callback_data="admin_zet"),
        InlineKeyboardButton("❌ Yopish", callback_data="admin_close")
    )
    return kb

# ==================== HANDLERLAR ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text
    
    # Referal ID ni olish
    referrer_id = None
    if ' ' in text:
        parts = text.split(' ')
        if len(parts) > 1:
            try:
                referrer_id = int(parts[1])
                if referrer_id == user_id:
                    referrer_id = None
                print(f"🔗 Referal ID: {referrer_id} (User: {user_id})")
            except:
                pass
    
    # Obuna tekshirish
    ok, not_sub = check_sub(user_id)
    
    if not ok:
        msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for n in not_sub:
            msg += f"🔹 {n}\n"
        msg += "\n✅ Obuna bo'lgach <b>Obunani tekshirish</b> tugmasini bosing!"
        bot.send_message(user_id, msg, reply_markup=sub_keyboard())
        return
    
    # Ro'yxatdan o'tmagan bo'lsa
    if not user_exists(user_id):
        msg = bot.send_message(
            user_id,
            "🌟 <b>IELTS Maxing</b> botiga xush kelibsiz! 🌟\n\n"
            "IELTS imtihoniga tayyorgarlik ko'rayotganlar uchun eng yaxshi bot!\n\n"
            "📝 <b>Iltimos, o'z ismingizni kiriting:</b>",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, get_name, referrer_id, username)
    else:
        bot.send_message(user_id, "🏠 <b>Asosiy menyu</b>", reply_markup=main_keyboard(user_id))

def get_name(message, referrer_id, username):
    user_id = message.from_user.id
    name = message.text.strip()
    
    if len(name) < 2:
        msg = bot.send_message(user_id, "❌ Iltimos, haqiqiy ismingizni kiriting (kamida 2 harf):")
        bot.register_next_step_handler(msg, get_name, referrer_id, username)
        return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    
    msg = bot.send_message(user_id, "📞 <b>Telefon raqamingizni yuboring:</b>\n\n👇 Pastdagi tugmani bosing:", reply_markup=kb)
    bot.register_next_step_handler(msg, get_phone, name, referrer_id, username)

def get_phone(message, name, referrer_id, username):
    user_id = message.from_user.id
    
    if not message.contact:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        msg = bot.send_message(user_id, "❌ Iltimos, pastdagi tugma orqali telefon raqamingizni yuboring!", reply_markup=kb)
        bot.register_next_step_handler(msg, get_phone, name, referrer_id, username)
        return
    
    phone = message.contact.phone_number
    
    register_user(user_id, name, phone, username, referrer_id)
    
    if referrer_id and referrer_id != user_id:
        txt = f"✅ <b>{name}</b>, ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n🎉 Siz referal link orqali keldingiz! Taklif qilgan insonga <b>+1 ball</b> qo'shildi.\n\n👥 Do'stlaringizni taklif qiling va ballar yig'ing!"
    else:
        txt = f"✅ <b>{name}</b>, ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n👥 Do'stlaringizni taklif qiling va ballar yig'ing!"
    
    bot.send_message(user_id, txt, reply_markup=main_keyboard(user_id))

@bot.message_handler(func=lambda m: m.text == "👥 Referal")
def ref_handler(m):
    uid = m.from_user.id
    
    if not user_exists(uid):
        bot.send_message(uid, "❌ Iltimos, avval /start buyrug'ini bosing va ro'yxatdan o'ting!")
        return
    
    ok, not_sub = check_sub(uid)
    if not ok:
        msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for n in not_sub:
            msg += f"🔹 {n}\n"
        bot.send_message(uid, msg, reply_markup=sub_keyboard())
        return
    
    ball = get_user_ball(uid)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={uid}"
    refs = get_my_referrals(uid)
    
    txt = (
        f"🌟 <b>Referal tizimi</b> 🌟\n\n"
        f"📊 Sizning ballaringiz: <b>{ball}</b>\n"
        f"👥 Taklif qilgan do'stlar: <b>{len(refs)}</b> ta\n\n"
        f"👥 Do'stlaringizni taklif qiling va ball yig'ing!\n"
        f"Har bir taklif qilgan do'stingiz uchun <b>1 ball</b> olasiz.\n\n"
        f"🔗 <b>Sizning referal linkingiz:</b>\n"
        f"<code>{link}</code>\n\n"
        f"💡 Do'stlaringizga yuboring, ular botga kirganda siz avtomatik ball olasiz!\n\n"
        f"📌 <b>Eslatma:</b> Ball hech qachon kamaymaydi!"
    )
    bot.send_message(uid, txt)

@bot.message_handler(func=lambda m: m.text == "📊 Dashboard")
def dash_handler(m):
    uid = m.from_user.id
    
    if not user_exists(uid):
        bot.send_message(uid, "❌ Iltimos, avval /start buyrug'ini bosing va ro'yxatdan o'ting!")
        return
    
    ok, not_sub = check_sub(uid)
    if not ok:
        msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for n in not_sub:
            msg += f"🔹 {n}\n"
        bot.send_message(uid, msg, reply_markup=sub_keyboard())
        return
    
    total = get_total_users()
    top10 = get_top10()
    
    txt = f"📈 <b>Dashboard</b> 📈\n\n"
    txt += f"👥 <b>Umumiy foydalanuvchilar:</b> {total}\n\n"
    txt += "🏆 <b>Top 10 (Referal ball bo'yicha):</b>\n"
    
    if top10:
        for i, (name, b) in enumerate(top10, 1):
            txt += f"{i}. {name[:20]} - {b} ball\n"
    else:
        txt += "📭 Hozircha ma'lumot yo'q\n"
    
    bot.send_message(uid, txt)

@bot.message_handler(func=lambda m: m.text == "👤 Mening ma'lumotlarim")
def info_handler(m):
    uid = m.from_user.id
    
    if not user_exists(uid):
        bot.send_message(uid, "❌ Iltimos, avval /start buyrug'ini bosing va ro'yxatdan o'ting!")
        return
    
    ok, not_sub = check_sub(uid)
    if not ok:
        msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        for n in not_sub:
            msg += f"🔹 {n}\n"
        bot.send_message(uid, msg, reply_markup=sub_keyboard())
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name, phone, refer_ball, joined_date, username, referrer_id FROM users WHERE user_id = ?", (uid,))
    user = c.fetchone()
    conn.close()
    
    if user:
        uname = f"@{user[4]}" if user[4] else "Yo'q"
        ref_by = "Yo'q"
        if user[5]:
            conn2 = get_db()
            c2 = conn2.cursor()
            c2.execute("SELECT full_name FROM users WHERE user_id = ?", (user[5],))
            r = c2.fetchone()
            if r:
                ref_by = r[0]
            conn2.close()
        
        txt = (
            f"👤 <b>Mening ma'lumotlarim</b>\n\n"
            f"📛 <b>Ism:</b> {user[0]}\n"
            f"📞 <b>Telefon:</b> {user[1]}\n"
            f"⭐ <b>Referal ball:</b> {user[2]}\n"
            f"👤 <b>Username:</b> {uname}\n"
            f"📅 <b>Qo'shilgan sana:</b> {user[3]}\n"
            f"👥 <b>Kim taklif qilgan:</b> {ref_by}\n"
        )
        bot.send_message(uid, txt)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin panel")
def admin_panel(m):
    uid = m.from_user.id
    if uid not in ADMIN_IDS:
        bot.send_message(uid, "❌ Siz admin emassiz!")
        return
    bot.send_message(uid, "⚙️ <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:", reply_markup=admin_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def admin_cb(c):
    uid = c.from_user.id
    if uid not in ADMIN_IDS:
        bot.answer_callback_query(c.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    if c.data == "admin_users":
        users = get_all_users()
        txt = "👥 <b>Barcha foydalanuvchilar:</b>\n\n"
        for u in users[:30]:
            uname = f"@{u[4]}" if u[4] else "Yo'q"
            ref_by = "Yo'q"
            if u[6]:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT full_name FROM users WHERE user_id = ?", (u[6],))
                rr = cur.fetchone()
                if rr:
                    ref_by = rr[0]
                conn.close()
            txt += f"🆔 ID: <code>{u[0]}</code>\n📛 Ism: {u[1]}\n📞 Tel: {u[2]}\n👤 Username: {uname}\n⭐ Ball: {u[3]}\n👥 Kim taklif qilgan: {ref_by}\n📅 Qo'shilgan: {u[5]}\n{'-'*30}\n"
        bot.edit_message_text(txt[:4000], uid, c.message.message_id)
    
    elif c.data == "admin_refs":
        refs = get_referrals()
        if refs:
            txt = "🔗 <b>Kim kimni taklif qilgan:</b>\n\n"
            for r in refs[:30]:
                txt += f"👤 {r[1]} (@{r[2]}) → 👤 {r[4]} (@{r[5]})\n📅 {r[6]}\n{'-'*25}\n"
            bot.edit_message_text(txt[:4000], uid, c.message.message_id)
        else:
            bot.edit_message_text("📭 Hozircha hech qanday referal mavjud emas.", uid, c.message.message_id)
    
    elif c.data == "admin_stats":
        total = get_total_users()
        conn = get_db()
        cur = conn.cursor()
        balls = cur.execute("SELECT SUM(refer_ball) FROM users").fetchone()[0] or 0
        refs = cur.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        conn.close()
        txt = f"📊 <b>Bot statistikasi</b>\n\n👥 Jami foydalanuvchilar: {total}\n⭐ Jami berilgan ballar: {balls}\n🔗 Jami referallar: {refs}\n👑 Adminlar soni: {len(ADMIN_IDS)}"
        bot.edit_message_text(txt, uid, c.message.message_id)
    
    elif c.data == "admin_zet":
        ball = get_user_ball(ZET_ID)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ +1 ball", callback_data="zet_add"),
            InlineKeyboardButton("➖ -1 ball", callback_data="zet_remove")
        )
        kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back"))
        bot.edit_message_text(f"⚡ <b>ZET ballini o'zgartirish</b>\n\nZET ID: <code>{ZET_ID}</code>\nJoriy ball: <b>{ball}</b>\n\nQuyidagi tugmalar orqali ballni o'zgartiring:", uid, c.message.message_id, reply_markup=kb)
    
    elif c.data == "admin_back":
        bot.edit_message_text("⚙️ <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:", uid, c.message.message_id, reply_markup=admin_keyboard())
    
    elif c.data == "admin_close":
        bot.delete_message(uid, c.message.message_id)
    
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data in ["zet_add", "zet_remove"])
def zet_cb(c):
    uid = c.from_user.id
    if uid not in ADMIN_IDS:
        bot.answer_callback_query(c.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    change = 1 if c.data == "zet_add" else -1
    new_ball = change_ball_admin(ZET_ID, change)
    bot.edit_message_text(f"✅ <b>Ball o'zgartirildi!</b>\n\n⭐ ZET yangi ball: <b>{new_ball}</b>", uid, c.message.message_id)
    bot.answer_callback_query(c.id, f"Ball {'qo\'shildi' if change == 1 else 'ayirildi'}!")

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def sub_cb(c):
    uid = c.from_user.id
    ok, not_sub = check_sub(uid)
    
    if ok:
        bot.delete_message(uid, c.message.message_id)
        if not user_exists(uid):
            msg = bot.send_message(
                uid,
                "✅ Obuna tasdiqlandi!\n\n🌟 <b>IELTS Maxing</b> botiga xush kelibsiz!\n\n📝 <b>Iltimos, o'z ismingizni kiriting:</b>",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            bot.register_next_step_handler(msg, get_name, None, c.from_user.username)
        else:
            bot.send_message(uid, "✅ Obuna tasdiqlandi!\n\n🏠 <b>Asosiy menyu</b>", reply_markup=main_keyboard(uid))
    else:
        txt = "❌ Siz hali quyidagi kanallarga obuna bo'lmagansiz:\n"
        for n in not_sub:
            txt += f"🔹 {n}\n"
        txt += "\n✅ Obuna bo'lgach qaytadan tekshiring!"
        bot.edit_message_text(txt, uid, c.message.message_id, reply_markup=sub_keyboard())
    
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: True)
def other(m):
    uid = m.from_user.id
    if user_exists(uid):
        ok, not_sub = check_sub(uid)
        if ok:
            bot.send_message(uid, "🏠 <b>Asosiy menyu</b>\n\nQuyidagi tugmalar orqali botdan foydalanishingiz mumkin:", reply_markup=main_keyboard(uid))
        else:
            msg = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
            for n in not_sub:
                msg += f"🔹 {n}\n"
            bot.send_message(uid, msg, reply_markup=sub_keyboard())
    else:
        bot.send_message(uid, "❌ Iltimos, avval /start buyrug'ini bosing va ro'yxatdan o'ting!")

# ==================== ISHGA TUSHIRISH ====================
if __name__ == "__main__":
    print("=" * 50)
    print("✅ IELTS Maxing bot ishga tushdi!")
    print("=" * 50)
    print("📢 Kanallar:")
    for name, link in CHANNELS.items():
        print(f"   - {name}: {link}")
    print(f"👑 Adminlar: {ADMIN_IDS}")
    print(f"⭐ ZET ID: {ZET_ID}")
    print("=" * 50)
    print("🎯 Referal ball hech qachon kamaymaydi!")
    print("🚀 Bot polling rejimida ishlayapti...")
    print("=" * 50)
    bot.infinity_polling(skip_pending=True)