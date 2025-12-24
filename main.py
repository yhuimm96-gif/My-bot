import telebot
from telebot import types
import json
import os
import schedule
import time
import threading

# --- 1. الإعدادات الأساسية ---
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

# --- 2. إدارة قاعدة البيانات ---
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_db(db):
    with open(DB_FILE, 'w') as f: json.dump(db, f, indent=4)

# --- 3. نظام الأرباح اليومية ---
def daily_profit_distribution():
    db = load_db()
    for uid, data in db.items():
        base = data.get('base_deposit', 0)
        profit = 0
        if base == 20: profit = 1.0
        elif base == 100: profit = 3.9
        elif base == 300: profit = 12.0
        
        if profit > 0:
            data['balance'] += profit
            try: bot.send_message(uid, f"💰 **إشعار ربح:** تمت إضافة {profit}$ لرصيدك اليومي.")
            except: pass
    save_db(db)

def run_scheduler():
    schedule.every().day.at("00:00").do(daily_profit_distribution)
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- 4. التحقق من الاشتراك ---
def check_sub(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status not in ['left', 'kicked']
    except: return True # في حال وجود خطأ بالاتصال نسمح بالدخول مؤقتاً

# --- 5. لوحة التحكم الرئيسية ---
def main_menu(uid):
    db = load_db()
    balance = db.get(str(uid), {}).get('balance', 0.0)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 إيداع", callback_data='dep_info'),
        types.InlineKeyboardButton("📤 سحب", callback_data='with_start')
    )
    markup.add(
        types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'),
        types.InlineKeyboardButton("👥 الإحالة ($1)", callback_data='ref_system')
    )
    return f"🌟 أهلاً بك في **CoinsGlobalPop**\n\n💰 رصيدك الحالي: `{balance:.2f}$`", markup

# --- 6. معالجة الأوامر ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()

    if uid not in db:
        ref = message.text.split()[1] if len(message.text.split()) > 1 else None
        db[uid] = {'balance': 0.0, 'name': message.from_user.first_name, 'base_deposit': 0, 'referrer': ref}
        save_db(db)

    if not check_sub(message.from_user.id):
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
        m.add(types.InlineKeyboardButton("🔄 تأكيد الاشتراك", callback_data='check_sub'))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت.", reply_markup=m)
        return

    text, markup = main_menu(uid)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

# --- 7. معالجة الأزرار التفاعلية ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    db = load_db()

    if call.data == 'check_sub':
        if check_sub(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ تم تأكيد الاشتراك!")
            text, markup = main_menu(uid)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في القناة بعد.", show_alert=True)

    elif call.data == 'dep_info':
        text = f"""
📥 **قسم الإيداع**

يرجى إرسال المبلغ إلى أحد العناوين التالية:

📌 **شبكة BEP20 (USDT/BNB):**
`{CONFIG['WALLETS']['BEP20']}`

📌 **شبكة TRC20 (USDT):**
`{CONFIG['WALLETS']['TRC20']}`

⚠️ **بعد التحويل:** ارسل صورة الإثبات (Screenshot) وقيمة المبلغ هنا.
        """
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_menu'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back, parse_mode='Markdown')

    elif call.data == 'main_menu':
        text, markup = main_menu(uid)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == 'view_balance':
        bal = db.get(uid, {}).get('balance', 0.0)
        bot.answer_callback_query(call.id, f"رصيدك الحالي هو: {bal}$", show_alert=True)

    elif call.data == 'ref_system':
        ref_link = f"https://t.me/{CONFIG['BOT_USERNAME']}?start={uid}"
        text = f"👥 **نظام الإحالة**\n\nاحصل على **1$** عن كل شخص يدخل عبر رابطك ويقوم بالإيداع.\n\n🔗 رابطك: `{ref_link}`"
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_menu'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back, parse_mode='Markdown')

# --- 8. تشغيل البوت ---
if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("Bot updated and running...")
    bot.infinity_polling()
