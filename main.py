import telebot
from telebot import types
import sqlite3
import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. الإعدادات الأساسية (تأكد من وضع التوكن الخاص بك هنا) ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'SUPPORT_LINK': 'https://wa.me/qr/VPE2KU5DNYCSH1'
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_NAME = 'bot_database.db'

# --- 2. إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (uid TEXT PRIMARY KEY, full_name TEXT, balance REAL, withdrawable_profit REAL,
                  referred_by TEXT, referrals_count INTEGER, active_referrals INTEGER,
                  has_deposited INTEGER, deposit_amount REAL, pending_amount REAL)''')
    
    # جدول الإعدادات المتغيرة
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # القيم الافتراضية للإعدادات
    default_settings = [
        ('wallet', '0x31d62d87fd666d3e4837c2de682adf1e21510295'),
        ('profit_20', '0.6'),
        ('profit_100', '3.3'),
        ('profit_300', '10.0')
    ]
    c.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", default_settings)
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "0"

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

# --- 3. نظام الأرباح والنسخ الاحتياطي التلقائي ---
def calculate_profit(amount):
    if amount == 20: return float(get_setting('profit_20'))
    elif amount == 100: return float(get_setting('profit_100'))
    elif amount == 300: return float(get_setting('profit_300'))
    return 0

def add_daily_profits():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE deposit_amount > 0")
    users = c.fetchall()
    
    for index, user in enumerate(users):
        profit = calculate_profit(user['deposit_amount'])
        if profit > 0:
            new_balance = user['balance'] + profit
            new_withdraw = user['withdrawable_profit'] + profit
            c.execute("UPDATE users SET balance=?, withdrawable_profit=? WHERE uid=?", (new_balance, new_withdraw, user['uid']))
            try:
                bot.send_message(user['uid'], f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيد السحب.", parse_mode='Markdown')
                # نظام Anti-Flood لمنع حظر البوت
                if index % 20 == 0: time.sleep(1)
                else: time.sleep(0.1)
            except: continue
    conn.commit()
    conn.close()

def backup_database():
    try:
        if os.path.exists(DB_NAME):
            with open(DB_NAME, 'rb') as doc:
                bot.send_document(CONFIG['ADMIN_ID'], doc, caption=f"📂 نسخة احتياطية للقاعدة\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except: pass

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.add_job(backup_database, 'cron', hour=3, minute=0) # يومياً الساعة 3 فجراً
scheduler.start()

# --- 4. لوحة تحكم المدير ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != CONFIG['ADMIN_ID']: return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 تغيير عنوان المحفظة", callback_data='adm_edit_wallet'),
        types.InlineKeyboardButton("💵 تعديل أرباح الباقات", callback_data='adm_edit_profits'),
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data='adm_stats'),
        types.InlineKeyboardButton("📂 نسخ احتياطي الآن", callback_data='adm_backup')
    )
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم المدير**\nتحكم في إعدادات النظام من هنا:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callbacks(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    if call.data == 'adm_edit_wallet':
        msg = bot.send_message(call.message.chat.id, "✉️ أرسل عنوان محفظة **BEP20** الجديد:")
        bot.register_next_step_handler(msg, update_wallet_setting)
    elif call.data == 'adm_edit_profits':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("20$", callback_data='prof_20'),
                   types.InlineKeyboardButton("100$", callback_data='prof_100'),
                   types.InlineKeyboardButton("300$", callback_data='prof_300'))
        bot.edit_message_text("اختر الباقة لتعديل ربحها اليومي:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == 'adm_stats':
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total = c.execute("SELECT SUM(deposit_amount) FROM users").fetchone()[0] or 0
        bot.send_message(call.message.chat.id, f"📊 **الإحصائيات الحالية:**\n👤 المشتركون: {count}\n💰 إجمالي المبالغ المستثمرة: {total:.2f}$")
    elif call.data == 'adm_backup':
        backup_database()
        bot.answer_callback_query(call.id, "✅ تم إرسال النسخة الاحتياطية")

def update_wallet_setting(message):
    new_val = message.text.strip()
    if new_val.startswith("0x"):
        conn = sqlite3.connect(DB_NAME); conn.cursor().execute("UPDATE settings SET value=? WHERE key='wallet'", (new_val,)); conn.commit(); conn.close()
        bot.send_message(message.chat.id, "✅ تم تحديث المحفظة بنجاح!")
    else: bot.send_message(message.chat.id, "❌ العنوان غير صالح.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('prof_'))
def edit_profit_step(call):
    package = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, f"أدخل الربح اليومي الجديد لباقة {package}$ (مثال: 0.8):")
    bot.register_next_step_handler(msg, save_profit_setting, package)

def save_profit_setting(message, package):
    try:
        new_val = float(message.text)
        conn = sqlite3.connect(DB_NAME); conn.cursor().execute(f"UPDATE settings SET value=? WHERE key='profit_{package}'", (str(new_val),)); conn.commit(); conn.close()
        bot.send_message(message.chat.id, f"✅ تم تحديث ربح باقة {package}$ إلى {new_val}$ يومياً.")
    except: bot.send_message(message.chat.id, "❌ خطأ في الإدخال، استخدم أرقاماً فقط.")

# --- 5. أوامر المستخدم والتحقق من القناة ---
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
        bot.send_message(message.chat.id, "⚠️ للبدء، يجب عليك الانضمام للقناة ثم كتابة /start من جديد.", reply_markup=markup)
        return
    user = get_user(uid)
    if not user:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        add_user(uid, referrer)
        bot.send_message(CONFIG['ADMIN_ID'], f"👤 **عضو جديد انضم للبوت:** {message.from_user.first_name}")
        user = get_user(uid)
    if not user['full_name']:
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else: show_menu(message)

def save_user_name(message):
    if message.text and len(message.text.split()) >= 3:
        update_user(message.from_user.id, full_name=message.text)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى كتابة اسمك الثلاثي بشكل صحيح:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='u_dep'), types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='u_wit'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='u_bal'), types.InlineKeyboardButton("👥 الإحالات", callback_data='u_ref'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=CONFIG['SUPPORT_LINK']))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n\n👤 المستثمر: `{user['full_name']}`\n💰 الرصيد الكلي: `{user['balance']:.2f}$` \n💸 القابل للسحب: `{user['withdrawable_profit']:.2f}$`", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('u_'))
def user_actions(call):
    uid = str(call.from_user.id); user = get_user(uid)
    if call.data == 'u_bal': bot.answer_callback_query(call.id, f"الرصيد: {user['balance']:.2f}$\nللسحب: {user['withdrawable_profit']:.2f}$", show_alert=True)
    elif call.data == 'u_ref':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\n\n🔗 رابط إحالتك:\n`{ref_link}`", parse_mode='Markdown')
    elif call.data == 'u_dep':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(f"💵 20$ (ربح {get_setting('profit_20')}$)", callback_data='v_20'),
                   types.InlineKeyboardButton(f"💵 100$ (ربح {get_setting('profit_100')}$)", callback_data='v_100'),
                   types.InlineKeyboardButton(f"💵 300$ (ربح {get_setting('profit_300')}$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر باقة الإيداع المطلوبة:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == 'u_wit':
        if datetime.now().strftime("%A") != "Friday": 
            bot.answer_callback_query(call.id, "⚠️ السحب متاح فقط يوم الجمعة!", show_alert=True)
            return
        if user['withdrawable_profit'] <= 0: 
            bot.answer_callback_query(call.id, "⚠️ لا يوجد رصيد كافٍ للسحب حالياً.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"💵 أدخل المبلغ الذي تود سحبه (متاح {user['withdrawable_profit']:.2f}$):")
        bot.register_next_step_handler(msg, process_withdraw)

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def package_select(call):
    val = int(call.data.split('_')[1])
    update_user(call.from_user.id, pending_amount=val)
    bot.edit_message_text(f"✅ اخترت باقة {val}$\nيرجى تحويل المبلغ لعنوان BEP20:\n`{get_setting('wallet')}`\nثم أرسل صورة الإثبات هنا.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    user = get_user(message.from_user.id)
    if not user or user['has_deposited'] or user['pending_amount'] == 0: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"app_{user['uid']}_{user['pending_amount']}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{user['uid']}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **طلب إيداع جديد**\n👤: {user['full_name']}\n💰: {user['pending_amount']}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال الإثبات للإدارة، سيتم التفعيل قريباً.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_approval(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    data = call.data.split('_'); t_uid = data[1]
    if data[0] == 'app':
        amt = float(data[2]); profit = calculate_profit(amt); t_user = get_user(t_uid)
        update_user(t_uid, balance=amt+profit, deposit_amount=amt, withdrawable_profit=profit, has_deposited=1)
        if t_user['referred_by']:
            ref = get_user(t_user['referred_by'])
            if ref: update_user(ref['uid'], balance=ref['balance']+1.0, withdrawable_profit=ref['withdrawable_profit']+1.0, active_referrals=ref['active_referrals']+1)
        bot.send_message(t_uid, "✅ تم قبول إيداعك بنجاح! بدأت أرباحك بالاحتساب الآن.")
    else: bot.send_message(t_uid, "❌ تم رفض إثبات الدفع، يرجى التواصل مع الدعم الفني.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

def process_withdraw(message):
    try:
        amt = float(message.text); user = get_user(message.from_user.id)
        if amt > user['withdrawable_profit']: bot.send_message(message.chat.id, "⚠️ رصيدك أقل من المبلغ المطلوب."); return
        msg = bot.send_message(message.chat.id, "💳 أرسل عنوان محفظة BEP20 الخاصة بك:"); bot.register_next_step_handler(msg, final_wit, amt)
    except: bot.send_message(message.chat.id, "⚠️ يرجى إدخال مبلغ صحيح.")

def final_wit(message, amt):
    address = message.text.strip()
    if not address.startswith("0x") or len(address) != 42: 
        bot.send_message(message.chat.id, "❌ عنوان المحفظة غير صحيح.")
        return
    user = get_user(message.from_user.id)
    update_user(user['uid'], balance=user['balance']-amt, withdrawable_profit=user['withdrawable_profit']-amt)
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 **طلب سحب جديد**\n👤: {user['full_name']}\n💰: {amt}$\n💳: `{address}`", parse_mode='Markdown')
    bot.send_message(message.chat.id, "⏳ تم إرسال طلب السحب بنجاح للمراجعة.")

# --- تشغيل البوت مع نظام إعادة الاتصال التلقائي ---
if __name__ == "__main__":
    print("Bot is Active and Monitoring...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
