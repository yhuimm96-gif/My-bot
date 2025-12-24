import telebot
from telebot import types
import json
import os
import schedule
import time
import threading
from datetime import datetime

# --- الإعدادات ---
CONFIG = {
    'TOKEN': '8524828584:AAEt7svTqofhfYdxdlk-XAd5FH3OS886piY',
    'ADMIN_ID': 988759701, 
    'ADMIN_USERNAME': '@Mamskskjsjsj',
    'BOT_USERNAME': 'CoinsGlobalPop_Bot',
    'CHANNEL_ID': '@AP_Fl',
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
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
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_db(db):
    with open(DB_FILE, 'w') as f: json.dump(db, f, indent=4)

# --- نظام التسجيل والاسم الثلاثي ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db:
        db[uid] = {'balance': 0.0, 'full_name': None, 'base_deposit': 0}
        save_db(db)

    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال **اسمك الثلاثي** لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    name = message.text
    if len(name.split()) < 3:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم **ثلاثياً** للمتابعة:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        db = load_db()
        db[uid]['full_name'] = name
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تسجيلك باسم: {name}")
        show_menu(message)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db[uid]['balance']
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع واستثمار", callback_data='deposit_start'),
               types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'))
    bot.send_message(message.chat.id, f"💰 رصيدك: `{bal:.2f}$`", reply_markup=markup, parse_mode='Markdown')

# --- نظام الإيداع والموافقة ---
@bot.callback_query_handler(func=lambda call: call.data == 'deposit_start')
def deposit_start(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💵 20$", callback_data='v_20'),
               types.InlineKeyboardButton("💵 100$", callback_data='v_100'),
               types.InlineKeyboardButton("💵 300$", callback_data='v_300'))
    bot.edit_message_text("💰 اختر مبلغ الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def view_wallets(call):
    val = call.data.split('_')[1]
    text = f"✅ المبلغ: **{val}$**\n\nقم بالتحويل للعنوان التالي ثم ارسل صورة الإثبات:\n`{CONFIG['WALLETS']['TRC20']}`"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    name = db[uid].get('full_name', 'غير مسجل')
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ موافقة", callback_data=f"app_{uid}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 إثبات من: {name}\nآيدي: `{uid}`", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ جاري مراجعة طلبك...")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve(call):
    if call.from_user.id == CONFIG['ADMIN_ID']:
        t_uid = call.data.split('_')[1]
        bot.send_message(t_uid, "✅ تمت الموافقة على إيداعك!")
        bot.answer_callback_query(call.id, "تم التفعيل")

if __name__ == "__main__":
    bot.infinity_polling()
