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
                      has_deposited INTEGER DEFAULT 0, deposit_amount REAL, pending_amount REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        
        # الإعدادات الافتراضية
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

# --- 3. نظام الأرباح والجدولة ---
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
                new_balance = (user['balance'] or 0.0) + profit
                new_withdraw = (user['withdrawable_profit'] or 0.0) + profit
                conn.execute("UPDATE users SET balance=?, withdrawable_profit=? WHERE uid=?", (new_balance, new_withdraw, user['uid']))
                try:
                    bot.send_message(user['uid'], f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيدك المتاح للسحب.", parse_mode='Markdown')
                except: continue
        conn.commit()

def backup_database():
    try:
        if os.path.exists(DB_NAME):
            with open(DB_NAME, 'rb') as doc:
                bot.send_document(CONFIG['ADMIN_ID'], doc, caption=f"📂 نسخة احتياطية لقاعدة البيانات\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except: pass

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.add_job(backup_database, 'cron', hour=3, minute=0)
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
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم المدير**", reply_markup=markup)

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
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total = conn.execute("SELECT SUM(deposit_amount) FROM users").fetchone()[0] or 0
            bot.send_message(call.message.chat.id, f"📊 **إحصائيات المنصة:**\n👤 إجمالي المستخدمين: {count}\n💰 إجمالي الاستثمارات: {total:.2f}$")
    elif call.data == 'adm_backup':
        backup_database()
        bot.answer_callback_query(call.id, "✅ تم إرسال النسخة الاحتياطية")

def update_wallet_setting(message):
    new_val = message.text.strip()
    if new_val.startswith("0x") and len(new_val) == 42:
        with get_db_connection() as conn:
            conn.execute("UPDATE settings SET value=? WHERE key='wallet'", (new_val,))
            conn.commit()
        bot.send_message(message.chat.id, "✅ تم تحديث عنوان المحفظة بنجاح.")
    else: bot.send_message(message.chat.id, "❌ العنوان غير صالح، يجب أن يبدأ بـ 0x.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('prof_'))
def edit_profit_step(call):
    package = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, f"أدخل الربح اليومي الجديد لباقة {package}$ (مثال: 1.5):")
    bot.register_next_step_handler(msg, save_profit_setting, package)

def save_profit_setting(message, package):
    try:
        new_val = float(message.text)
        with get_db_connection() as conn:
            conn.execute(f"UPDATE settings SET value=? WHERE key='profit_{package}'", (str(new_val),))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ تم تحديث أرباح باقة {package}$.")
    except: bot.send_message(message.chat.id, "❌ خطأ: يرجى إدخال أرقام فقط.")

# --- 5. أوامر المستخدم والتحقق ---
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
        markup.add(types.InlineKeyboardButton("📢 انضم للقناة لتفعيل البوت", url=CONFIG['CHANNEL_LINK']))
        bot.send_message(message.chat.id, "⚠️ عذراً، يجب عليك الانضمام للقناة أولاً لاستخدام البوت.", reply_markup=markup)
        return
    
    user = get_user(uid)
    if not user:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        add_user(uid, referrer)
        bot.send_message(CONFIG['ADMIN_ID'], f"👤 **عضو جديد انضم:** {message.from_user.first_name}")
        user = get_user(uid)
        
    if not user['full_name']:
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال اسمك الثلاثي لفتح حسابك الاستثماري:")
        bot.register_next_step_handler(msg, save_user_name)
    else: show_menu(message)

def save_user_name(message):
    if message.text and len(message.text.split()) >= 2:
        update_user(message.from_user.id, full_name=message.text)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى كتابة اسمك بشكل واضح (الاسم الثنائي على الأقل):")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع جديد", callback_data='u_dep'), 
               types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='u_wit'))
    markup.add(types.InlineKeyboardButton("💰 محفظتي", callback_data='u_bal'), 
               types.InlineKeyboardButton("👥 نظام الإحالة", callback_data='u_ref'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=CONFIG['SUPPORT_LINK']))
    
    status_text = "✅ مستثمر نشط" if user['has_deposited'] else "💤 بانتظار الإيداع"
    bot.send_message(message.chat.id, 
                     f"🏠 **لوحة التحكم الشخصية**\n\n"
                     f"👤 المستثمر: `{user['full_name']}`\n"
                     f"📊 الحالة: `{status_text}`\n"
                     f"💰 متاح للسحب: `{user['withdrawable_profit']:.2f}$`", 
                     reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('u_'))
def user_actions(call):
    uid = str(call.from_user.id); user = get_user(uid)
    if call.data == 'u_bal': 
        bot.answer_callback_query(call.id, f"الرصيد الكلي: {user['balance']:.2f}$\nالأرباح المتاحة للسحب: {user['withdrawable_profit']:.2f}$", show_alert=True)
    elif call.data == 'u_ref':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        text = (
            f"👥 **نظام الإحالة المكافئ**\n\n"
            f"🔗 رابط دعوة الأصدقاء:\n`{ref_link}`\n\n"
            f"📊 إحصائياتك:\n"
            f"👤 عدد الإحالات: `{user['referrals_count']}`\n"
            f"✅ إحالات مفعلة: `{user['active_referrals']}`\n\n"
            f"💰 تحصل على 1$ فوري عند قيام إحالتك بأول إيداع."
        )
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    elif call.data == 'u_dep':
        if user['has_deposited'] == 1:
            bot.answer_callback_query(call.id, "⚠️ مسموح بإيداع استثماري واحد فقط حالياً.", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(f"💵 باقة 20$ (ربح {get_setting('profit_20')}$/يوم)", callback_data='v_20'),
                   types.InlineKeyboardButton(f"💵 باقة 100$ (ربح {get_setting('profit_100')}$/يوم)", callback_data='v_100'),
                   types.InlineKeyboardButton(f"💵 باقة 300$ (ربح {get_setting('profit_300')}$/يوم)", callback_data='v_300'))
        bot.edit_message_text("💰 **اختر الباقة الاستثمارية المناسبة:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
    elif call.data == 'u_wit':
        if datetime.now().strftime("%A") != "Friday": 
            bot.answer_callback_query(call.id, "⚠️ السحب متاح فقط في يوم الجمعة من كل أسبوع.", show_alert=True)
            return
        if user['withdrawable_profit'] <= 0: 
            bot.answer_callback_query(call.id, "⚠️ رصيدك الحالي هو 0$. لا يمكن السحب.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"💵 أدخل المبلغ الذي تود سحبه (متاح لك {user['withdrawable_profit']:.2f}$):")
        bot.register_next_step_handler(msg, process_withdraw)

# --- 6. معالجة الإيداع والموافقة ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def package_select(call):
    val = int(call.data.split('_')[1])
    update_user(call.from_user.id, pending_amount=val)
    bot.edit_message_text(f"✅ تم اختيار باقة {val}$\n\n"
                          f"يرجى تحويل المبلغ لعنوان BEP20 التالي:\n`{get_setting('wallet')}`\n\n"
                          f"📸 بعد التحويل، أرسل صورة إثبات التحويل (Screenshot) هنا.", 
                          call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    user = get_user(message.from_user.id)
    if not user or user['pending_amount'] == 0 or user['has_deposited'] == 1: return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول الإيداع", callback_data=f"app_{user['uid']}_{user['pending_amount']}"), 
               types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"rej_{user['uid']}"))
    
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **طلب إيداع جديد**\n👤 المستثمر: {user['full_name']}\n💰 المبلغ: {user['pending_amount']}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال إثباتك للإدارة. سيتم تفعيل باقتك فور التأكد.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_approval(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    data = call.data.split('_'); t_uid = data[1]
    if data[0] == 'app':
        amt = float(data[2]); profit = calculate_profit(amt); t_user = get_user(t_uid)
        update_user(t_uid, balance=amt+profit, deposit_amount=amt, withdrawable_profit=profit, has_deposited=1, pending_amount=0)
        
        # مكافأة الإحالة
        if t_user['referred_by']:
            ref = get_user(t_user['referred_by'])
            if ref:
                new_act = (ref['active_referrals'] or 0) + 1
                new_ref_bal = (ref['balance'] or 0.0) + 1.0
                new_ref_wit = (ref['withdrawable_profit'] or 0.0) + 1.0
                update_user(ref['uid'], balance=new_ref_bal, withdrawable_profit=new_ref_wit, active_referrals=new_act)
                try: 
                    bot.send_message(ref['uid'], f"🎉 **مكافأة إحالة!**\n✅ قام صديقك بالإيداع، تمت إضافة `1$` لرصيدك.")
                except: pass
        
        bot.send_message(t_uid, "✅ **تم تفعيل باقتك الاستثمارية!**\nستبدأ أرباحك بالنزول يومياً في نفس هذا التوقيت.")
    else: 
        update_user(t_uid, pending_amount=0)
        bot.send_message(t_uid, "❌ تم رفض إثبات الإيداع. يرجى التأكد من البيانات أو التواصل مع الدعم.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- 7. نظام السحب بموافقة المدير ---
def process_withdraw(message):
    try:
        amt = float(message.text)
        user = get_user(message.from_user.id)
        if amt > user['withdrawable_profit']: 
            bot.send_message(message.chat.id, "⚠️ عذراً، رصيدك غير كافٍ لسحب هذا المبلغ.")
            return
        if amt < 1.0:
            bot.send_message(message.chat.id, "⚠️ الحد الأدنى للسحب هو 1$.")
            return
        msg = bot.send_message(message.chat.id, "💳 أرسل عنوان محفظة BEP20 لاستلام الأرباح:")
        bot.register_next_step_handler(msg, final_wit_request, amt)
    except: 
        bot.send_message(message.chat.id, "⚠️ يرجى إدخال مبلغ صحيح (أرقام فقط).")

def final_wit_request(message, amt):
    address = message.text.strip()
    if not address.startswith("0x") or len(address) != 42:
        bot.send_message(message.chat.id, "❌ عنوان المحفظة غير صحيح. يرجى المحاولة مجدداً عبر زر السحب.")
        return
    
    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة على السحب", callback_data=f"wapp_{user['uid']}_{amt}"),
               types.InlineKeyboardButton("❌ رفض السحب", callback_data=f"wrej_{user['uid']}_{amt}"))
    
    bot.send_message(CONFIG['ADMIN_ID'], 
                     f"📤 **طلب سحب قيد الانتظار**\n"
                     f"👤 المستثمر: {user['full_name']}\n"
                     f"💰 المبلغ: {amt}$\n"
                     f"💳 العنوان: `{address}`", reply_markup=markup, parse_mode='Markdown')
    
    bot.send_message(message.chat.id, "⏳ تم إرسال طلب السحب للإدارة. سيصلك إشعار فور تأكيد عملية الدفع.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('wapp_', 'wrej_')))
def admin_withdraw_decision(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    data = call.data.split('_'); action = data[0]; t_uid = data[1]; amt = float(data[2])
    
    user = get_user(t_uid)
    if action == 'wapp':
        if user and user['withdrawable_profit'] >= amt:
            new_bal = user['balance'] - amt
            new_wit = user['withdrawable_profit'] - amt
            update_user(t_uid, balance=new_bal, withdrawable_profit=new_wit)
            bot.send_message(t_uid, f"✅ **تمت الموافقة على سحبك!**\n💰 بقيمة: {amt}$\nتم تحويل المبلغ إلى محفظتك.")
            bot.answer_callback_query(call.id, "✅ تم التأكيد وخصم الرصيد")
        else:
            bot.answer_callback_query(call.id, "❌ خطأ: رصيد المستخدم غير كافٍ!", show_alert=True)
    else:
        bot.send_message(t_uid, f"❌ نعتذر، تم رفض طلب سحب مبلغ {amt}$. لمزيد من التفاصيل تواصل مع الدعم.")
        bot.answer_callback_query(call.id, "❌ تم الرفض")
    
    bot.delete_message(call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    print("Bot is successfully running and connected to database...")
    bot.infinity_polling()
