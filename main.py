import telebot
from telebot import types
import json
import os
import schedule
import time
import threading
from datetime import datetime

# --- 1. الإعدادات ---
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

# --- 2. التحقق والبدء ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db:
        db[uid] = {'balance': 0.0, 'full_name': None, 'base_deposit': 0, 'referrer': None}
        save_db(db)

    # طلب الاسم الثلاثي إذا لم يكن مسجلاً
    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال **اسمك الثلاثي** أولاً لتسجيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
        return

    show_main_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    name = message.text
    if len(name.split()) < 3:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم **ثلاثياً** (الاسم، الأب، الكنية):")
        bot.register_next_step_handler(msg, save_user_name)
        return
    
    db = load_db()
    db[uid]['full_name'] = name
    save_db(db)
    bot.send_message(message.chat.id, f"✅ تم تسجيلك باسم: {name}")
    show_main_menu(message)

def show_main_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db[uid]['balance']
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع واستثمار", callback_data='choose_amount'),
               types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'))
    bot.send_message(message.chat.id, f"🌟 رصيدك الحالي: `{bal:.2f}$`", reply_markup=markup, parse_mode='Markdown')

# --- 3. نظام الإيداع (اختيار القيمة أولاً) ---
@bot.callback_query_handler(func=lambda call: call.data == 'choose_amount')
def choose_amount(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💵 20$", callback_data='amt_20'),
               types.InlineKeyboardButton("💵 100$", callback_data='amt_100'),
               types.InlineKeyboardButton("💵 300$", callback_data='amt_300'))
    bot.edit_message_text("💰 اختر مبلغ الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('amt_'))
def show_wallets(call):
    amount = call.data.split('_')[1]
    uid = str(call.from_user.id)
    db = load_db()
    user_name = db[uid].get('full_name', 'غير معروف')
    
    # إشعار للأدمن
    bot.send_message(CONFIG['ADMIN_ID'], f"🔔 **تنبيه:** المستخدم `{user_name}` ({uid}) اختار إيداع `{amount}$`.")
    
    text = f"✅ مبلغ الاستثمار: **{amount}$**\n\nيرجى التحويل للعنوان أدناه ثم إرسال صورة الإثبات:\n\n📌 **TRC20:**\n`{CONFIG['WALLETS']['TRC20']}`"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

# --- 4. استقبال الصور والموافقة ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = str(message.from_user.id)
    db = load_db()
    user_name = db[uid].get('full_name', 'غير معروف')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة (20$)", callback_data=f"ok_{uid}_20"),
               types.InlineKeyboardButton("✅ موافقة (100$)", callback_data=f"ok_{uid}_100"))
    
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 إثبات من: **{user_name}**\nآيدي: `{uid}`", reply_markup=markup, parse_mode='Markdown')
    bot.send_message(message.chat.id, "⏳ جاري مراجعة الإثبات من قبل الإدارة...")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ok_'))
def admin_approve(call):
    if str(call.from_user.id) != str(CONFIG['ADMIN_ID']): return
    _, target_uid, amount = call.data.split('_')
    db = load_db()
    if target_uid in db:
        db[target_uid]['balance'] += float(amount)
        db[target_uid]['base_deposit'] = float(amount)
        save_db(db)
        bot.send_message(target_uid, f"🎊 تمت الموافقة! تم تفعيل رصيدك بمبلغ {amount}$.")
        bot.edit_message_text(f"✅ تم تفعيل حساب {target_uid}", call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
