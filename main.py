import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- الإعدادات النهائية المعتمدة ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'SUPPORT_LINK': 'https://wa.me/qr/VPE2KU5DNYCSH1',
    'WALLETS': {
        'BEP20': '0x31d62d87fd666d3e4837c2de682adf1e21510295'
    }
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_NAME = 'bot_database.db'

# --- إدارة قاعدة البيانات SQLite ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (uid TEXT PRIMARY KEY, full_name TEXT, balance REAL, withdrawable_profit REAL,
                  referred_by TEXT, referrals_count INTEGER, active_referrals INTEGER,
                  has_deposited INTEGER, deposit_amount REAL, pending_amount REAL)''')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (str(uid),))
    user = c.fetchone()
    conn.close()
    return user

def add_user(uid, referrer=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (uid, balance, withdrawable_profit, referrals_count, active_referrals, has_deposited, deposit_amount, pending_amount, referred_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (str(uid), 0.0, 0.0, 0, 0, 0, 0.0, 0.0, referrer))
    if referrer:
        c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE uid=?", (str(referrer),))
    conn.commit()
    conn.close()

def update_user(uid, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE users SET {key}=? WHERE uid=?", (value, str(uid)))
    conn.commit()
    conn.close()

init_db()

# --- نظام الأرباح التلقائي ---
def calculate_profit(amount):
    if amount == 20: return 0.6
    elif amount == 100: return 3.3
    elif amount == 300: return 10.0
    return 0

def add_daily_profits():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE deposit_amount > 0")
    users = c.fetchall()
    
    for user in users:
        profit = calculate_profit(user['deposit_amount'])
        if profit > 0:
            new_balance = user['balance'] + profit
            new_withdraw = user['withdrawable_profit'] + profit
            c.execute("UPDATE users SET balance=?, withdrawable_profit=? WHERE uid=?", 
                      (new_balance, new_withdraw, user['uid']))
            try:
                bot.send_message(user['uid'], f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيد السحب.", parse_mode='Markdown')
            except: continue
    conn.commit()
    conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- التحقق من الاشتراك ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# --- أوامر البوت ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 انضم للقناة الآن", url=CONFIG['CHANNEL_LINK']))
        bot.send_message(message.chat.id, "⚠️ للبدء، يجب عليك الاشتراك في القناة أولاً!", reply_markup=markup)
        return
    
    user = get_user(uid)
    if not user:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        add_user(uid, referrer)
        bot.send_message(CONFIG['ADMIN_ID'], f"👤 **مستخدم جديد:** {message.from_user.first_name}")
        user = get_user(uid)

    if not user['full_name']:
        msg = bot.send_message(message.chat.id, "👋 يرجى إرسال اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else: 
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    if message.text and len(message.text.split()) >= 3:
        update_user(uid, full_name=message.text)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم الثلاثي (3 كلمات على الأقل):")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    user = get_user(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), 
               types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'), 
               types.InlineKeyboardButton("👥 الإحالات", callback_data='referral_info'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=CONFIG['SUPPORT_LINK']))
    
    msg_text = (f"🏠 **لوحة التحكم**\n\n👤 المستثمر: `{user['full_name']}`\n"
                f"💰 الرصيد الكلي: `{user['balance']:.2f}$` \n"
                f"💸 القابل للسحب: `{user['withdrawable_profit']:.2f}$` \n"
                f"👥 الإحالات الكلية: {user['referrals_count']}\n"
                f"✅ الإحالات الفعالة: {user['active_referrals']}")
    bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='Markdown')

# --- معالجة التفاعلات ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    user = get_user(uid)
