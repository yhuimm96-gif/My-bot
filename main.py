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
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'SUPPORT_LINK': 'https://wa.me/qr/VPE2KU5DNYCSH1'
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_NAME = 'bot_database.db'

# --- 2. إدارة قاعدة البيانات (كما في الصورة) ---
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
                      has_deposited INTEGER DEFAULT 0, deposit_amount REAL, pending_amount REAL)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        
        default_settings = [
            ('wallet', '0x31d62d87fd666d3e4837c2de682adf1e21510295'),
            ('profit_20', '0.6'),
            ('profit_100', '3.3'),
            ('profit_300', '10.0')
        ]
        c.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", default_settings)
        conn.commit()

def get_setting(key):
    with get_db_connection() as conn:
        res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else "0"

def get_user(uid):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE uid=?", (str(uid),)).fetchone()

def add_user(uid, referrer=None):
    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users (uid, balance, withdrawable_profit, referrals_count, active_referrals, has_deposited, deposit_amount, pending_amount, referred_by) VALUES (?, 0.0, 0.0, 0, 0, 0, 0.0, 0.0, ?)",
                  (str(uid), referrer))
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
        users = conn.execute("SELECT * FROM users WHERE has_deposited = 1").fetchall()
        for user in users:
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

# --- 4. أوامر المستخدم ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 انضم للقناة أولاً", url=CONFIG['CHANNEL_LINK']))
        bot.send_message(message.chat.id, "⚠️ يجب عليك الانضمام للقناة أولاً لاستخدام البوت.", reply_markup=markup)
        return
    
    user = get_user(uid)
    if not user:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        add_user(uid, referrer)
        user = get_user(uid)
        
    if not user['full_name']:
        msg = bot.send_message(message.chat.id, "👋 يرجى إرسال اسمك الثلاثي للتفعيل:")
        bot.register_next_step_handler(msg, save_user_name)
    else: show_menu(message)

def save_user_name(message):
    if message.text and len(message.text.split()) >= 3:
        update_user(message.from_user.id, full_name=message.text)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ الاسم غير صحيح، أرسل الاسم الثلاثي:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='u_dep'), 
               types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='u_wit'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='u_bal'), 
               types.InlineKeyboardButton("👥 الإحالات", callback_data='u_ref'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=CONFIG['SUPPORT_LINK']))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n👤 المستثمر: `{user['full_name']}`\n💸 متاح للسحب: `{user['withdrawable_profit']:.2f}$`", reply_markup=markup, parse_mode='Markdown')

# --- 5. نظام الإيداع (مرة واحدة فقط) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('u_'))
def user_actions(call):
    uid = str(call.from_user.id); user = get_user(uid)
    
    if call.data == 'u_dep':
        if user['has_deposited'] == 1:
            bot.answer_callback_query(call.id, "⚠️ يسمح بالإيداع لمرة واحدة فقط!", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(f"💵 20$ (ربح {get_setting('profit_20')}$)", callback_data='v_20'),
                   types.InlineKeyboardButton(f"💵 100$ (ربح {get_setting('profit_100')}$)", callback_data='v_100'),
                   types.InlineKeyboardButton(f"💵 300$ (ربح {get_setting('profit_300')}$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر باقة الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == 'u_wit':
        if datetime.now().strftime("%A") != "Friday": 
            bot.answer_callback_query(call.id, "⚠️ السحب متاح يوم الجمعة فقط!", show_alert=True)
            return
        if user['withdrawable_profit'] <= 0: 
            bot.answer_callback_query(call.id, "⚠️ رصيدك 0$ حالياً.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"💵 أدخل مبلغ السحب (متاح {user['withdrawable_profit']:.2f}$):")
        bot.register_next_step_handler(msg, process_withdraw)
    
    elif call.data == 'u_bal':
        bot.answer_callback_query(call.id, f"المتاح للسحب: {user['withdrawable_profit']:.2f}$", show_alert=True)
    
    elif call.data == 'u_ref':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\nرابطك: `{ref_link}`\n💰 مكافأة 1$ عند إيداع الصديق.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def package_select(call):
    user = get_user(call.from_user.id)
    if user['has_deposited'] == 1: return
    val = int(call.data.split('_')[1])
    update_user(call.from_user.id, pending_amount=val)
    bot.edit_message_text(f"✅ باقة {val}$\nارسل المبلغ لعنوان BEP20:\n`{get_setting('wallet')}`\nثم أرسل صورة الإثبات:", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    user = get_user(message.from_user.id)
    if not user or user['pending_amount'] == 0 or user['has_deposited'] == 1: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"app_{user['uid']}_{user['pending_amount']}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{user['uid']}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **إيداع جديد**\n👤: {user['full_name']}\n💰: {user['pending_amount']}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال الإثبات للمراجعة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_approval(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    data = call.data.split('_'); t_uid = data[1]
    if data[0] == 'app':
        amt = float(data[2]); profit = calculate_profit(amt); t_user = get_user(t_uid)
        update_user(t_uid, balance=amt+profit, deposit_amount=amt, withdrawable_profit=profit, has_deposited=1, pending_amount=0)
        if t_user['referred_by']:
            ref = get_user(t_user['referred_by'])
            if ref:
                update_user(ref['uid'], balance=ref['balance']+1.0, withdrawable_profit=ref['withdrawable_profit']+1.0, active_referrals=ref['active_referrals']+1)
        bot.send_message(t_uid, "✅ تم تفعيل إيداعك بنجاح!")
    else: 
        update_user(t_uid, pending_amount=0)
        bot.send_message(t_uid, "❌ تم رفض الإثبات.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- 6. نظام السحب ---
def process_withdraw(message):
    try:
        amt = float(message.text); user = get_user(message.from_user.id)
        if amt > user['withdrawable_profit']: bot.send_message(message.chat.id, "⚠️ رصيد غير كافٍ."); return
        msg = bot.send_message(message.chat.id, "💳 ارسل عنوان محفظة BEP20:"); bot.register_next_step_handler(msg, final_wit, amt)
    except: bot.send_message(message.chat.id, "⚠️ ارسل أرقاماً فقط.")

def final_wit(message, amt):
    address = message.text.strip()
    user = get_user(message.from_user.id)
    update_user(user['uid'], balance=user['balance']-amt, withdrawable_profit=user['withdrawable_profit']-amt)
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 **طلب سحب**\n👤: {user['full_name']}\n💰: {amt}$\n💳: `{address}`")
    bot.send_message(message.chat.id, "⏳ طلبك قيد المراجعة.")

if __name__ == "__main__":
    bot.infinity_polling()
