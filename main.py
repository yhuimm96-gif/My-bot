import telebot
from telebot import types
import json
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- الإعدادات النهائية ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'ADMIN_USERNAME': '@Mamskskjsjsj',
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'WALLETS': {
        'TRC20': 'THqcaiM1CQtWYAqQm7iLJ2zFR5WVPFNCDx'
    }
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_FILE = 'database.json'

# --- نظام الأرباح التلقائي المخصص ---
def add_daily_profits():
    db = load_db()
    for uid in db:
        deposited_val = db[uid].get('deposit_amount', 0)
        profit = 0
        if deposited_val == 20: profit = 0.6
        elif deposited_val == 100: profit = 3.3
        elif deposited_val == 300: profit = 10.0
            
        if profit > 0:
            db[uid]['balance'] += profit
            db[uid]['withdrawable_profit'] = db[uid].get('withdrawable_profit', 0.0) + profit
            try:
                bot.send_message(uid, f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيد السحب.", parse_mode='Markdown')
            except: continue
    save_db(db)

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- دوال قاعدة البيانات ---
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

# --- أوامر البوت ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if not is_subscribed(message.from_user.id):
        send_join_msg(message.chat.id)
        return
    
    db = load_db()
    if uid not in db:
        args = message.text.split()
        referrer = args[1] if len(args) > 1 else None
        db[uid] = {
            'balance': 0.0, 'withdrawable_profit': 0.0, 'full_name': None, 
            'referred_by': referrer, 'referrals_count': 0, 'has_deposited': False, 'deposit_amount': 0 
        }
        if referrer and referrer in db:
            db[referrer]['referrals_count'] = db[referrer].get('referrals_count', 0) + 1
        save_db(db)
    
    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 يرجى إرسال اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    user = db.get(uid, {})
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), 
               types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'), 
               types.InlineKeyboardButton("👥 الإحالات", callback_data='referral_info'))
    
    msg_text = (f"🏠 **لوحة التحكم**\n\n👤 المستثمر: `{user.get('full_name')}`\n"
                f"💰 الرصيد الكلي: `{user.get('balance'):.2f}$` \n"
                f"💸 القابل للسحب: `{user.get('withdrawable_profit', 0):.2f}$` \n"
                f"👥 عدد الإحالات: `{user.get('referrals_count', 0)}`")
    bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='Markdown')

# --- استقبال صورة الإيداع ---
@bot.message_handler(content_types=['photo'])
def handle_payment_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    if uid not in db or db[uid].get('has_deposited'): return

    pending_amt = db[uid].get('pending_amount')
    if not pending_amt:
        bot.send_message(message.chat.id, "⚠️ يرجى اختيار مبلغ الإيداع من القائمة أولاً.")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"app_{uid}_{pending_amt}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **طلب إيداع جديد**\n👤 الاسم: {db[uid]['full_name']}\n💵 المبلغ: {pending_amt}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال إثبات الدفع للآدمن. سيتم تفعيل حسابك فور التأكد.")

# --- معالجة الأزرار ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    db = load_db()

    if call.data == 'view_balance':
        bot.answer_callback_query(call.id, f"رصيدك الكلي: {db[uid]['balance']:.2f}$", show_alert=True)

    elif call.data == 'referral_info':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\n\nاربح 1$ عن كل شخص يشحن!\n🔗 رابطك: `{ref_link}`", parse_mode='Markdown')

    elif call.data == 'deposit_start':
        if db[uid].get('has_deposited'):
            bot.answer_callback_query(call.id, "⚠️ مسموح بالإيداع مرة واحدة فقط!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💵 20$ (ربح 0.6$)", callback_data='v_20'), 
                   types.InlineKeyboardButton("💵 100$ (ربح 3.3$)", callback_data='v_100'), 
                   types.InlineKeyboardButton("💵 300$ (ربح 10$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر باقة الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('v_'):
        val = int(call.data.split('_')[1])
        db[uid]['pending_amount'] = val
        save_db(db)
        bot.edit_message_text(f"✅ حول مبلغ {val}$ لعنوان TRC20:\n`{CONFIG['WALLETS']['TRC20']}`\n\nأرسل صورة الإثبات هنا.", call.message.chat.id, call.message.message_id)

    elif call.data == 'withdraw_start':
        withdrawable = db[uid].get('withdrawable_profit', 0.0)
        if withdrawable <= 0:
            bot.answer_callback_query(call.id, "⚠️ ليس لديك أرباح للسحب!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"💰 رصيد السحب: `{withdrawable:.2f}$`\nأدخل المبلغ:")
        bot.register_next_step_handler(msg, process_withdraw_amount)

    # --- أزرار الآدمن ---
    if call.from_user.id == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] = amt
            db[t_uid]['deposit_amount'] = amt
            db[t_uid]['has_deposited'] = True
            
            # مكافأة الإحالة
            ref_id = db[t_uid].get('referred_by')
            if ref_id and ref_id in db:
                db[ref_id]['balance'] += 1.0
                db[ref_id]['withdrawable_profit'] += 1.0
                try: bot.send_message(ref_id, "🎁 حصلت على 1$ مكافأة إحالة في رصيد السحب!")
                except: pass
            
            save_db(db)
            bot.send_message(t_uid, "✅ تم تفعيل إيداعك بنجاح!")
            bot.edit_message_text(f"✅ تم تفعيل حساب {db[t_uid]['full_name']}", call.message.chat.id, call.message.message_id)
        
        elif data[0] == 'rej':
            bot.send_message(data[1], "❌ تم رفض إثبات الدفع من قبل الإدارة.")
            bot.edit_message_text("❌ تم الرفض.", call.message.chat.id, call.message.message_id)

def process_withdraw_amount(message):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        db = load_db()
        if amt > db[uid].get('withdrawable_profit', 0):
            bot.send_message(message.chat.id, "⚠️ المبلغ أكبر من أرباحك!")
            return
        msg = bot.send_message(message.chat.id, "💳 أدخل عنوان TRC20:")
        bot.register_next_step_handler(msg, final_withdraw_request, amt)
    except: bot.send_message(message.chat.id, "⚠️ أرقام فقط!")

def final_withdraw_request(message, amt):
    uid = str(message.from_user.id)
    db = load_db()
    db[uid]['withdrawable_profit'] -= amt
    db[uid]['balance'] -= amt
    save_db(db)
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 **طلب سحب**\n👤: {db[uid]['full_name']}\n💰: {amt}$\n💳: `{message.text}`")
    bot.send_message(message.chat.id, "⏳ تم إرسال طلب السحب.")

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def send_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
    bot.send_message(chat_id, "⚠️ يجب الاشتراك أولاً!", reply_markup=markup)

def save_user_name(message):
    uid = str(message.from_user.id)
    db = load_db()
    if len(message.text.split()) >= 3:
        db[uid]['full_name'] = message.text
        save_db(db)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم ثلاثياً:")
        bot.register_next_step_handler(msg, save_user_name)

if __name__ == "__main__":
    bot.infinity_polling()
