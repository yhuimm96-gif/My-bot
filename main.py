import telebot
from telebot import types
import json
import os
import re
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- الإعدادات ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'ADMIN_USERNAME': '@Mamskskjsjsj', 
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'WALLETS': {'TRC20': 'THqcaiM1CQtWYAqQm7iLJ2zFR5WVPFNCDx'}
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_FILE = 'database.json'

def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def calculate_profit(amount):
    profits = {20: 0.6, 100: 3.3, 300: 10.0}
    return profits.get(amount, 0)

# --- نظام الأرباح اليومي ---
def add_daily_profits():
    db = load_db()
    for uid, user in db.items():
        profit = calculate_profit(user.get('deposit_amount', 0))
        if profit > 0:
            user['balance'] += profit
            user['withdrawable_profit'] += profit
            try: bot.send_message(uid, f"📈 أرباح يومية: `+{profit}$`", parse_mode='Markdown')
            except: continue
    save_db(db)

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- التحقق من القناة ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# --- الأوامر الرئيسية ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك بالقناة أولاً!", reply_markup=markup)
        return
    
    db = load_db()
    if uid not in db:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        db[uid] = {
            'balance': 0.0, 'withdrawable_profit': 0.0, 'full_name': None, 
            'referred_by': referrer, 'referrals_count': 0, 'active_referrals': 0, 
            'has_deposited': False, 'deposit_amount': 0, 'pending_amount': 0
        }
        if referrer and referrer in db:
            db[referrer]['referrals_count'] = db[referrer].get('referrals_count', 0) + 1
        save_db(db)

    user = db[uid]
    if not user.get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أرسل اسمك الثلاثي لتفعيل الحساب:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    if message.text and len(message.text.split()) >= 3:
        db = load_db()
        db[uid]['full_name'] = message.text
        save_db(db)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال اسم ثلاثي صحيح:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    user = db[uid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), 
               types.InlineKeyboardButton("📤 سحب", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 الرصيد", callback_data='view_balance'), 
               types.InlineKeyboardButton("👥 الإحالات", callback_data='referral_info'))
    
    text = (f"🏠 **لوحة التحكم**\n\n👤: `{user['full_name']}`\n"
            f"💵 الرصيد: `{user['balance']:.2f}$`\n"
            f"✅ الإحالات الفعالة: `{user['active_referrals']}`")
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

# --- معالجة الأزرار (الموحدة) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    uid = str(call.from_user.id)
    db = load_db()

    if call.data == 'referral_info':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        text = (f"👥 **نظام الإحالة**\n\n🔗 رابطك: `{ref_link}`\n"
                f"🎁 مكافأة الإيداع: **1$**\n"
                f"📊 الإحالات الفعالة: {db[uid].get('active_referrals', 0)}")
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    elif call.data == 'withdraw_start':
        if datetime.now().strftime("%A") != "Saturday":
            bot.answer_callback_query(call.id, "⚠️ السحب متاح يوم السبت فقط!", show_alert=True)
            return
        # كود اختيار الشبكة كما في السابق...
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("TRC20", callback_data='net_TRC20'),
                   types.InlineKeyboardButton("BEP20", callback_data='net_BEP20'))
        bot.edit_message_text("🌐 اختر الشبكة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('net_'):
        network = call.data.split('_')[1]
        msg = bot.send_message(call.message.chat.id, f"💰 أدخل مبلغ السحب ({network}):")
        bot.register_next_step_handler(msg, process_withdraw, network)

    elif call.data == 'deposit_start':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("20$", callback_data='v_20'),
                   types.InlineKeyboardButton("100$", callback_data='v_100'))
        bot.edit_message_text("💵 اختر باقة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('v_'):
        val = int(call.data.split('_')[1])
        db[uid]['pending_amount'] = val
        save_db(db)
        bot.edit_message_text(f"✅ باقة {val}$\nحول للعنوان:\n`{CONFIG['WALLETS']['TRC20']}`\nثم أرسل الصورة.", call.message.chat.id, call.message.message_id)

    # --- إدارة الآدمن ---
    if int(uid) == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] = amt + calculate_profit(amt)
            db[t_uid]['deposit_amount'] = amt
            db[t_uid]['withdrawable_profit'] += calculate_profit(amt)
            db[t_uid]['has_deposited'] = True
            
            # مكافأة الداعي
            ref_id = db[t_uid].get('referred_by')
            if ref_id and ref_id in db:
                db[ref_id]['balance'] += 1.0
                db[ref_id]['withdrawable_profit'] += 1.0
                db[ref_id]['active_referrals'] += 1
                try: bot.send_message(ref_id, "🎁 حصلت على 1$ مكافأة إحالة فعالة!")
                except: pass
            
            save_db(db)
            bot.send_message(t_uid, "✅ تم تفعيل إيداعك!")
            bot.edit_message_text(f"✅ تم تفعيل {t_uid}", call.message.chat.id, call.message.message_id)

# --- دوال السحب ---
def process_withdraw(message, network):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        db = load_db()
        if amt > db[uid]['withdrawable_profit']:
            bot.send_message(message.chat.id, "⚠️ رصيدك غير كافٍ.")
            return
        msg = bot.send_message(message.chat.id, f"💳 أرسل عنوان محفظة {network}:")
        bot.register_next_step_handler(msg, final_withdraw, amt, network)
    except: bot.send_message(message.chat.id, "⚠️ أدخل رقماً صحيحاً.")

def final_withdraw(message, amt, network):
    addr = message.text.strip()
    # التحقق من المحفظة
    if (network == "TRC20" and not addr.startswith("T")) or (network == "BEP20" and not addr.startswith("0x")):
        bot.send_message(message.chat.id, "❌ عنوان غير صحيح للشبكة المختارة!")
        return
    
    uid = str(message.from_user.id)
    db = load_db()
    db[uid]['withdrawable_profit'] -= amt
    db[uid]['balance'] -= amt
    save_db(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تم", callback_data=f"wapp_{uid}"),
               types.InlineKeyboardButton("❌ رفض", callback_data=f"wrej_{uid}_{amt}"))
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 طلب سحب: {amt}$\n👤: {db[uid]['full_name']}\n💳: `{addr}`\n🌐: {network}", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال الطلب للآدمن.")

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    if uid in db and db[uid]['pending_amount'] > 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"app_{uid}_{db[uid]['pending_amount']}"),
                   types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
        bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
        bot.send_message(CONFIG['ADMIN_ID'], f"📩 إيداع جديد من {db[uid]['full_name']}", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ جاري مراجعة الإيداع...")

if __name__ == "__main__":
    bot.infinity_polling()
