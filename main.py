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

# --- إضافة زر Start للقائمة الجانبية ---
def set_bot_commands():
    try:
        commands = [types.BotCommand("start", "الرجوع للقائمة الرئيسية 🏠")]
        bot.set_my_commands(commands)
    except: pass

# --- التحقق من الاشتراك الإجباري ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def send_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 انضم للقناة الآن", url=CONFIG['CHANNEL_LINK']))
    bot.send_message(chat_id, "⚠️ **عذراً، يجب عليك الاشتراك في القناة أولاً!**\n\nبعد الانضمام، أرسل /start مجدداً لتفعيل الحساب.", reply_markup=markup)

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
        db[uid] = {'balance': 0.0, 'full_name': None, 'has_deposited': False}
        save_db(db)
    
    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال اسمك الثلاثي لتفعيل حسابك وحفظ بياناتك:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    db = load_db()
    name = message.text
    if name and len(name.split()) >= 3:
        db[uid]['full_name'] = name
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم التوثيق باسم: **{name}**\n\n📌 **تنبيه:** يرجى عدم مسح السجل لضمان حقوقك.")
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال الاسم ثلاثياً ليتم قبوله:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db[uid].get('balance', 0.0)
    name = db[uid].get('full_name', 'مستثمر')
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), 
               types.InlineKeyboardButton("📤 سحب", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'), 
               types.InlineKeyboardButton("👥 نظام الإحالة", callback_data='referral_info'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم", url=f"https://t.me/{CONFIG['ADMIN_USERNAME'].replace('@','')}"))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n👤 المستثمر: `{name}`\n💰 الرصيد: `{bal:.2f}$`", reply_markup=markup, parse_mode='Markdown')

# --- معالجة الأزرار ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    db = load_db()
    
    if not is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ اشترك في القناة أولاً!", show_alert=True)
        return

    if call.data == 'view_balance':
        bot.answer_callback_query(call.id, f"رصيدك: {db[uid]['balance']:.2f}$", show_alert=True)

    elif call.data == 'deposit_start':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💵 20$ (ربح 1$)", callback_data='v_20'), 
                   types.InlineKeyboardButton("💵 100$ (ربح 3.9$)", callback_data='v_100'), 
                   types.InlineKeyboardButton("💵 300$ (ربح 12$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر مبلغ الإيداع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == 'withdraw_start':
        if datetime.now().weekday() != 5: # السبت = 5
            bot.answer_callback_query(call.id, "⚠️ السحب متاح يوم السبت فقط!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💰 أرسل المبلغ المراد سحبه:")
        bot.register_next_step_handler(msg, process_withdraw)

    elif call.data == 'referral_info':
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\nاربح 1$ عن كل شخص يشحن!\n`{ref_link}`", parse_mode='Markdown')

    elif call.data.startswith('v_'):
        val = call.data.split('_')[1]
        db[uid]['pending_amount'] = float(val)
        save_db(db)
        bot.edit_message_text(f"✅ حول {val}$ لـ TRC20:\n`{CONFIG['WALLETS']['TRC20']}`\n\n⚠️ أرسل صورة الإثبات هنا.", call.message.chat.id, call.message.message_id)

    # --- إدارة الآدمن ---
    elif call.from_user.id == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] += amt
            save_db(db)
            bot.send_message(t_uid, f"✅ تم تفعيل إيداعك بمبلغ {amt}$!")
            bot.edit_message_text(f"✅ تم الشحن لـ {db[t_uid]['full_name']}", call.message.chat.id, call.message.message_id)
        elif data[0] == 'rej':
            bot.send_message(data[1], "❌ نعتذر، تم رفض طلبك من قبل الإدارة.")
            bot.edit_message_text(f"❌ تم الرفض للمستخدم {data[1]}", call.message.chat.id, call.message.message_id)

# --- وظائف السحب ---
def process_withdraw(message):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        db = load_db()
        if amt > db[uid]['balance']:
            bot.send_message(message.chat.id, "⚠️ رصيدك غير كافٍ!")
            return
        msg = bot.send_message(message.chat.id, "💳 أرسل عنوان محفظتك (TRC20):")
        bot.register_next_step_handler(msg, final_withdraw, amt)
    except: bot.send_message(message.chat.id, "⚠️ أرقام فقط!")

def final_withdraw(message, amt):
    uid = str(message.from_user.id)
    db = load_db()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة", callback_data=f"wapp_{uid}_{amt}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 **طلب سحب**\n👤: {db[uid]['full_name']}\n💰: {amt}$\n💳: `{message.text}`", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال طلبك للمراجعة.")

# --- استقبال الصور ---
@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    if uid not in db: return
    amt = db[uid].get('pending_amount', 0)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ موافقة", callback_data=f"app_{uid}_{amt}"), 
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}"))
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 إيداع جديد: {db[uid]['full_name']} ({amt}$)", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ جاري مراجعة إثباتك...")

if __name__ == "__main__":
    set_bot_commands()
    bot.infinity_polling()
