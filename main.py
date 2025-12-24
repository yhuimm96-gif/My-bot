import telebot
from telebot import types
import json
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- الإعدادات ---
CONFIG = {
    'TOKEN': '7941946883:AAERwK7lzjt1_xe-iarb5SkE8IXJs-abfrk', 
    'ADMIN_ID': 8499302703, 
    'WHATSAPP_NUMBER': '212774143365', 
    'CHANNEL_ID': '@AP_Fl', 
    'CHANNEL_LINK': 'https://t.me/AP_Fl',
    'DB_FILE': 'database.json',
    'WALLETS': {'TRC20': 'THqcaiM1CQtWYAqQm7iLJ2zFR5WVPFNCDx'}
}

bot = telebot.TeleBot(CONFIG['TOKEN'])

# --- وظائف قاعدة البيانات ---
def load_db():
    if not os.path.exists(CONFIG['DB_FILE']):
        with open(CONFIG['DB_FILE'], 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    try:
        with open(CONFIG['DB_FILE'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def save_db(data):
    with open(CONFIG['DB_FILE'], 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def calculate_profit(amount):
    if amount == 20: return 0.6
    elif amount == 100: return 3.3
    elif amount == 300: return 10.0
    return 0

# --- الأرباح التلقائية ---
def add_daily_profits():
    db = load_db()
    for uid, user in db.items():
        if user.get('deposit_amount', 0) > 0:
            profit = calculate_profit(user['deposit_amount'])
            user['balance'] += profit
            user['withdrawable_profit'] += profit
            try: bot.send_message(uid, f"💰 **أرباح يومية!**\nتم إضافة `+{profit}$` لرصيدك.")
            except: continue
    save_db(db)

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- الأوامر الأساسية ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    # التحقق من الاشتراك
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], message.from_user.id).status
        if status not in ['member', 'administrator', 'creator']:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
            return bot.send_message(message.chat.id, "⚠️ اشترك أولاً!", reply_markup=markup)
    except: pass

    if uid not in db:
        args = message.text.split()
        db[uid] = {'full_name': None, 'balance': 0.0, 'withdrawable_profit': 0.0, 'referred_by': args[1] if len(args)>1 else None, 'deposit_amount': 0, 'pending_amount': 0}
        save_db(db)

    if not db[uid]['full_name']:
        msg = bot.send_message(message.chat.id, "👋 أرسل اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else: show_menu(message)

def save_user_name(message):
    if message.text and len(message.text.split()) >= 3:
        db = load_db(); db[str(message.from_user.id)]['full_name'] = message.text; save_db(db)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ يرجى إرسال اسم ثلاثي صحيح:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id); db = load_db(); user = db[uid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='dep'), types.InlineKeyboardButton("📤 سحب", callback_data='wit'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='bal'), types.InlineKeyboardButton("👥 الإحالات", callback_data='ref'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم (WhatsApp)", url=f"https://wa.me/{CONFIG['WHATSAPP_NUMBER']}"))
    bot.send_message(message.chat.id, f"🏠 **لوحة التحكم**\n👤 {user['full_name']}\n💰 الرصيد: {user['balance']:.2f}$", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = str(call.from_user.id); db = load_db()
    if call.data == 'bal':
        bot.answer_callback_query(call.id, f"رصيدك: {db[uid]['balance']:.2f}$", show_alert=True)
    elif call.data == 'ref':
        bot.send_message(call.message.chat.id, f"👥 رابط إحالتك:\n`https://t.me/{(bot.get_me().username)}?start={uid}`", parse_mode='Markdown')
    elif call.data == 'wit':
        bot.send_message(call.message.chat.id, "📤 للسحب، تواصل مع الدعم عبر الواتساب.")
    elif call.data == 'dep':
        markup = types.InlineKeyboardMarkup()
        for v in [20, 100, 300]: markup.add(types.InlineKeyboardButton(f"باقة {v}$", callback_data=f"v_{v}"))
        bot.edit_message_text("اختر باقة:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith('v_'):
        amt = int(call.data.split('_')[1]); db[uid]['pending_amount'] = amt; save_db(db)
        bot.edit_message_text(f"أرسل {amt}$ لـ (TRC20):\n`{CONFIG['WALLETS']['TRC20']}`\nثم أرسل صورة الإثبات.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = str(message.from_user.id); db = load_db()
    if uid in db and db[uid].get('pending_amount', 0) > 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"ok_{uid}_{db[uid]['pending_amount']}"), types.InlineKeyboardButton("❌ رفض", callback_data=f"no_{uid}"))
        bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
        bot.send_message(CONFIG['ADMIN_ID'], f"إيداع من {db[uid]['full_name']} مبلغ {db[uid]['pending_amount']}$", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ جاري المراجعة...")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('ok_', 'no_')))
def admin_action(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    data = call.data.split('_'); action = data[0]; target_uid = data[1]; db = load_db()
    if action == 'ok':
        amt = float(data[2]); profit = calculate_profit(amt)
        db[target_uid]['balance'] += (amt + profit); db[target_uid]['deposit_amount'] = amt; db[target_uid]['pending_amount'] = 0
        if db[target_uid].get('referred_by') in db: db[db[target_uid]['referred_by']]['balance'] += 1.0
        bot.send_message(target_uid, "✅ تم التفعيل!")
    save_db(db); bot.delete_message(call.message.chat.id, call.message.message_id)

bot.infinity_polling()
