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
    'ADMIN_ID': 988759701,  # الآيدي الجديد الخاص بك
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
    with open(DB_FILE, 'r') as f: return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f: json.dump(db, f, indent=4)

# --- 3. نظام الأرباح اليومية التلقائي ---
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

# --- 4. التحقق من الاشتراك الإجباري ---
def check_sub(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status not in ['left', 'kicked']
    except: return False

# --- 5. الأوامر الرئيسية ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()

    if uid not in db:
        ref = message.text.split()[1] if len(message.text.split()) > 1 else None
        db[uid] = {'balance': 0.0, 'name': message.from_user.first_name, 'base_deposit': 0, 'referrer': ref}
        save_db(db)

    if not check_sub(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
        markup.add(types.InlineKeyboardButton("🔄 تأكيد الاشتراك", callback_data='check_sub'))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت.", reply_markup=markup)
        return

    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(types.InlineKeyboardButton("📥 إيداع", callback_data='dep_info'),
          types.InlineKeyboardButton("📤 سحب", callback_data='with_start'))
    m.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'),
          types.InlineKeyboardButton("👥 الإحالة (1$)", callback_data='ref_system'))
    
    bot.send_message(message.chat.id, f"🌟 أهلاً بك في CoinsGlobalPop\n💰 رصيدك الحالي: {db[uid]['balance']:.2f}$", reply_markup=m)

# --- 6. نظام الإيداع والموافقة (يصل للأدمن الجديد) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('ok_dep_'))
def approve_dep(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return
    
    _, _, target_uid, amount = call.data.split('_')
    amount = float(amount)
    db = load_db()
    
    if target_uid in db:
        db[target_uid]['balance'] += amount
        db[target_uid]['base_deposit'] = amount
        
        # منح مكافأة إحالة 1$ للداعي عند أول إيداع
        ref_id = db[target_uid].get('referrer')
        bonus_msg = ""
        if ref_id and str(ref_id) in db:
            db[str(ref_id)]['balance'] += 1.0
            bonus_msg = f"\n✅ تم منح 1$ للداعي {ref_id}"
            try: bot.send_message(ref_id, "🎊 مبروك! أحد الأشخاص الذين دعوتهم قام بالإيداع وحصلت على 1$.")
            except: pass
            
        save_db(db)
        bot.send_message(target_uid, f"✅ تم تفعيل إيداعك بنجاح بقيمة {amount}$!")
        bot.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_uid}{bonus_msg}", call.message.chat.id, call.message.message_id)

# --- 7. تشغيل البوت ---
if __name__ == "__main__":
    # تشغيل مجدول الأرباح في خلفية الكود
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("Bot is Running with New Admin ID: 988759701")
    bot.infinity_polling()
