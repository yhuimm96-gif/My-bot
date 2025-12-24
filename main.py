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
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'WALLETS': {
        'BEP20': '0x31d62d87fd666d3e4837c2de682adf1e21510295',
        'TRC20': 'THqcaiM1CQtWYAqQm7iLJ2zFR5WVPFNCDx'
    }
}

bot = telebot.TeleBot(CONFIG['TOKEN'])
DB_FILE = 'database.json'

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def send_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 انضم للقناة من هنا", url=CONFIG['CHANNEL_LINK']))
    bot.send_message(chat_id, "⚠️ يجب الاشتراك في قناة البوت أولاً لتتمكن من استخدامه.", reply_markup=markup)

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
    if not is_subscribed(message.from_user.id):
        send_join_msg(message.chat.id)
        return
    db = load_db()
    if uid not in db:
        db[uid] = {'balance': 0.0, 'full_name': None, 'has_deposited': False}
        save_db(db)
    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else: show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    db = load_db()
    name = message.text
    if name and len(name.split()) >= 3:
        db[uid]['full_name'] = name
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم توثيق حسابك باسم: {name}")
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ خطأ! يرجى إرسال الاسم ثلاثياً:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db[uid].get('balance', 0.0)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), types.InlineKeyboardButton("📤 سحب", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'))
    bot.send_message(message.chat.id, f"🏠 لوحة التحكم\n👤: {db[uid]['full_name']}\n💰 رصيدك: {bal:.2f}$", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if not is_subscribed(call.from_user.id):
        send_join_msg(call.message.chat.id)
        return
    uid = str(call.from_user.id)
    db = load_db()
    if call.data == 'deposit_start':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💵 20$", callback_data='v_20'), types.InlineKeyboardButton("💵 100$", callback_data='v_100'))
        bot.edit_message_text("💰 اختر مبلغ الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith('v_'):
        val = call.data.split('_')[1]
        db[uid]['pending_amount'] = float(val)
        save_db(db)
        bot.send_message(call.message.chat.id, f"✅ حول {val}$ لشبكة TRC20:\n`{CONFIG['WALLETS']['TRC20']}`\nثم أرسل صورة الإثبات.")
    elif call.from_user.id == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] += amt
            save_db(db)
            bot.send_message(t_uid, f"✅ تم تأكيد إيداعك بقيمة {amt}$!")
            bot.edit_message_text("✅ تمت الموافقة", call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    amt = db[uid].get('pending_amount', 0)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة", callback_data=f"app_{uid}_{amt}"), types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 إيداع جديد من {db[uid].get('full_name')}: {amt}$", reply_markup=markup)

if __name__ == "__main__":
    bot.infinity_polling()
