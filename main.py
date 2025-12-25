import telebot
from telebot import types
import sqlite3
import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. الإعدادات الأساسية ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://wa.me/qr/VPE2KU5DNYCSH1'
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_NAME = 'bot_database.db'

# --- 2. إدارة قاعدة البيانات ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (uid TEXT PRIMARY KEY, full_name TEXT, balance REAL, withdrawable_profit REAL,
                      referred_by TEXT, referrals_count INTEGER, active_referrals INTEGER,
                      has_deposited INTEGER, deposit_amount REAL, pending_amount REAL)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        
        # إضافة رابط الدعم الفني الافتراضي في الإعدادات
        default_settings = [
            ('wallet', '0x31d62d87fd666d3e4837c2de682adf1e21510295'),
            ('profit_20', '0.6'),
            ('profit_100', '3.3'),
            ('profit_300', '10.0'),
            ('support_link', 'https://t.me/ContactUsCOINSGLOPAL22_bot?start=98875970')
        ]
        c.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", default_settings)
        conn.commit()

def get_setting(key):
    with get_db_connection() as conn:
        res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else "0"

def update_setting(key, value):
    with get_db_connection() as conn:
        conn.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
        conn.commit()

def get_user(uid):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE uid=?", (str(uid),)).fetchone()

def add_user(uid, referrer=None):
    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users (uid, balance, withdrawable_profit, referrals_count, active_referrals, has_deposited, deposit_amount, pending_amount, referred_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (str(uid), 0.0, 0.0, 0, 0, 0, 0.0, 0.0, referrer))
        if referrer:
            conn.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE uid=?", (str(referrer),))
        conn.commit()

def update_user(uid, **kwargs):
    with get_db_connection() as conn:
        for key, value in kwargs.items():
            conn.execute(f"UPDATE users SET {key}=? WHERE uid=?", (value, str(uid)))
        conn.commit()

init_db()

# --- 3. نظام الأرباح التلقائي ---
def calculate_profit(amount):
    try:
        if amount == 20: return float(get_setting('profit_20'))
        elif amount == 100: return float(get_setting('profit_100'))
        elif amount == 300: return float(get_setting('profit_300'))
    except: return 0
    return 0

def add_daily_profits():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users WHERE deposit_amount > 0").fetchall()
        for index, user in enumerate(users):
            profit = calculate_profit(user['deposit_amount'])
            if profit > 0:
                new_balance = user['balance'] + profit
                new_withdraw = user['withdrawable_profit'] + profit
                conn.execute("UPDATE users SET balance=?, withdrawable_profit=? WHERE uid=?", (new_balance, new_withdraw, user['uid']))
                try:
                    bot.send_message(user['uid'], f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيد السحب.", parse_mode='Markdown')
                except: continue
        conn.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- 4. لوحة تحكم المدير ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != CONFIG['ADMIN_ID']: return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 تغيير عنوان المحفظة", callback_data='adm_edit_wallet'),
        types.InlineKeyboardButton("💵 تعديل أرباح الباقات", callback_data='adm_edit_profits'),
        types.InlineKeyboardButton("🔗 تعديل رابط الدعم الفني", callback_data='adm_edit_support'), # الزر الجديد
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data='adm_stats'),
        types.InlineKeyboardButton("📂 نسخ احتياطي الآن", callback_data='adm_backup')
    )
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم المدير**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callbacks(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    
    if call.data == 'adm_edit_wallet':
        msg = bot.send_message(call.message.chat.id, "✉️ أرسل عنوان محفظة **BEP20** الجديد:")
        bot.register_next_step_handler(msg, save_wallet)
        
    elif call.data == 'adm_edit_support':
        msg = bot.send_message(call.message.chat.id, "🔗 أرسل رابط الدعم الفني الجديد (مثلاً رابط واتساب أو بوت آخر):")
        bot.register_next_step_handler(msg, save_support_link)
        
    elif call.data == 'adm_edit_profits':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("20$", callback_data='prof_20'),
                   types.InlineKeyboardButton("100$", callback_data='prof_100'),
                   types.InlineKeyboardButton("300$", callback_data='prof_300'))
        bot.edit_message_text("اختر الباقة لتعديل ربحها اليومي:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif call.data == 'adm_stats':
        with get_db_connection() as conn:
            res = conn.execute("SELECT COUNT(*), SUM(deposit_amount) FROM users").fetchone()
            bot.send_message(call.message.chat.id, f"📊 **إحصائيات:**\n👤 المشتركين: {res[0]}\n💰 إجمالي الإيداعات: {res[1] or 0:.2f}$")

def save_wallet(message):
    update_setting('wallet', message.text.strip())
    bot.send_message(message.chat.id, "✅ تم تحديث المحفظة.")

def save_support_link(message):
    new_link = message.text.strip()
    if new_link.startswith("http"):
        update_setting('support_link', new_link)
        bot.send_message(message.chat.id, "✅ تم تحديث رابط الدعم الفني بنجاح.")
    else:
        bot.send_message(message.chat.id, "❌ خطأ! الرابط يجب أن يبدأ بـ http أو https.")

# --- 5. أوامر المستخدم ---
@bot.message_handler(commands=['
