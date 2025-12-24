import telebot
from telebot import types
import json
import os
from datetime import datetime

# --- الإعدادات النهائية ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'ADMIN_USERNAME': '@Mamskskjsjsj',
    'WALLETS': {
        'BEP20': '0x31d62d87fd666d3e4837c2de682adf1e21510295',
        'TRC20': 'THqcaiM1CQtWYAqQm7iLJ2zFR5WVPFNCDx'
    }
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_FILE = 'database.json'

def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()
    referrer = None
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
        if ref_id != uid: referrer = ref_id
    if uid not in db:
        db[uid] = {'balance': 0.0, 'full_name': None, 'referrer': referrer, 'has_deposited': False}
        save_db(db)
    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال **اسمك الثلاثي** لتفعيل حسابك.\n⚠️ لا يمكن تغيير الاسم لاحقاً.")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    db = load_db()
    if db.get(uid) and db[uid].get('full_name'):
        show_menu(message)
        return
    name = message.text
    if name and len(name.split()) >= 3:
        db[uid]['full_name'] = name
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم توثيق حسابك باسم: **{name}**")
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم **ثلاثياً**:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db[uid].get('balance', 0.0)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), types.InlineKeyboardButton("📤 سحب", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'), types.InlineKeyboardButton("👥 نظام الإحالة", callback_data='referral_info'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{CONFIG['ADMIN_USERNAME'].replace('@','')}"))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n\n👤 المستثمر: `{db[uid]['full_name']}`\n💰 رصيدك: `{bal:.2f}$`", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    db = load_db()
    if call.data == 'referral_info':
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\n\nاربح **1$** عن كل شخص يشحن حسابه!\n`{ref_link}`", parse_mode='Markdown')
    elif call.data == 'view_balance':
        bot.answer_callback_query(call.id, f"رصيدك: {db[uid]['balance']:.2f}$", show_alert=True)
    elif call.data == 'deposit_start':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💵 20$ (ربح 1$)", callback_data='v_20'), types.InlineKeyboardButton("💵 100$ (ربح 3.9$)", callback_data='v_100'), types.InlineKeyboardButton("💵 300$ (ربح 12$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر مبلغ الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == 'withdraw_start':
        if datetime.now().weekday() != 5:
            bot.answer_callback_query(call.id, "⚠️ السحب متاح يوم السبت فقط.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💰 أرسل المبلغ المراد سحبه:")
        bot.register_next_step_handler(msg, process_withdraw)
    elif call.data.startswith('v_'):
        val = call.data.split('_')[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("TRC20", callback_data=f"net_TRC20_{val}"), types.InlineKeyboardButton("BEP20", callback_data=f"net_BEP20_{val}"))
        bot.edit_message_text(f"💳 اختر الشبكة لمبلغ {val}$:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith('net_'):
        net, val = call.data.split('_')[1], call.data.split('_')[2]
        db[uid]['pending_amount'] = float(val)
        save_db(db)
        bot.edit_message_text(f"✅ حول **{val}$** لـ **{net}**:\n`{CONFIG['WALLETS'][net]}`\n\nأرسل صورة الإثبات هنا.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    elif call.from_user.id == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] += amt
            if not db[t_uid].get('has_deposited', False):
                rid = db[t_uid].get('referrer')
                if rid and rid in db: db[rid]['balance'] += 1.0
                db[t_uid]['has_deposited'] = True
            save_db(db)
            bot.send_message(t_uid, f"✅ تم تفعيل إيداعك بقيمة {amt}$!")
            bot.edit_message_text("✅ تمت الموافقة", call.message.chat.id, call.message.message_id)
        elif data[0] == 'wapp':
            t_uid, amt = data[1], float(data[2])
            if db[t_uid]['balance'] >= amt:
                db[t_uid]['balance'] -= amt
                save_db(db)
                bot.send_message(t_uid, f"✅ تم تأكيد سحب {amt}$!")
                bot.edit_message_text("✅ تم الخصم", call.message.chat.id, call.message.message_id)

def process_withdraw(message):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        db = load_db()
        if amt > db[uid]['balance']:
            bot.send_message(message.chat.id, "⚠️ رصيد غير كافٍ.")
            return
        msg = bot.send_message(message.chat.id, "💳 أرسل عنوان محفظتك:")
        bot.register_next_step_handler(msg, final_withdraw, amt)
    except: bot.send_message(message.chat.id, "⚠️ أدخل أرقاماً فقط.")

def final_withdraw(message, amt):
    uid = str(message.from_user.id)
    db = load_db()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة (خصم)", callback_data=f"wapp_{uid}_{amt}"), types.InlineKeyboardButton("❌ رفض", callback_data=f"wrej_{uid}"))
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 طلب سحب: {db[uid]['full_name']}\n💰 المبلغ: {amt}$\n💳 العنوان: `{message.text}`", reply_markup=markup, parse_mode='Markdown')
    bot.send_message(message.chat.id, "⏳ جاري مراجعة طلبك.")

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    if uid not in db or not db[uid].get('full_name'): return
    amount = db[uid].get('pending_amount', 0)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة", callback_data=f"app_{uid}_{amount}"), types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 إيداع من {db[uid]['full_name']} بمبلغ {amount}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ جاري المراجعة...")

if __name__ == "__main__":
    bot.infinity_polling()
