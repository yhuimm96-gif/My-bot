import telebot
from telebot import types
import json
import os

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

# --- وظائف قاعدة البيانات ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: 
            return json.load(f)
    except: 
        return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: 
        json.dump(db, f, indent=4, ensure_ascii=False)

# --- نظام التسجيل ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db:
        db[uid] = {'balance': 0.0, 'full_name': None, 'pending_amount': 0}
        save_db(db)

    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 أهلاً بك! يرجى إرسال **اسمك الثلاثي** لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    name = message.text
    if name and len(name.split()) >= 3:
        db = load_db()
        db[uid]['full_name'] = name
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تسجيلك بنجاح باسم: {name}")
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ خطأ! يرجى إرسال الاسم **ثلاثياً على الأقل**:")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    bal = db.get(uid, {}).get('balance', 0.0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 إيداع واستثمار", callback_data='deposit_start'),
        types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'),
        types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{CONFIG['ADMIN_USERNAME'].replace('@','')}")
    )
    
    text = f"🏠 **القائمة الرئيسية**\n\n👤 الاسم: {db[uid]['full_name']}\n💰 رصيدك الحالي: `{bal:.2f}$`"
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

# --- نظام الإيداع ---
@bot.callback_query_handler(func=lambda call: call.data == 'deposit_start')
def deposit_start(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💵 20$", callback_data='v_20'),
        types.InlineKeyboardButton("💵 100$", callback_data='v_100'),
        types.InlineKeyboardButton("💵 300$", callback_data='v_300')
    )
    bot.edit_message_text("💰 اختر مبلغ الإيداع المناسب لك:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def choose_network(call):
    val = call.data.split('_')[1]
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Network TRC20", callback_data=f"net_TRC20_{val}"),
        types.InlineKeyboardButton("Network BEP20", callback_data=f"net_BEP20_{val}")
    )
    bot.edit_message_text(f"💳 اختر شبكة التحويل لمبلغ **{val}$**:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('net_'))
def show_wallet(call):
    data = call.data.split('_')
    net, val = data[1], data[2]
    wallet = CONFIG['WALLETS'][net]
    
    # حفظ المبلغ المعلق مؤقتاً في قاعدة البيانات
    db = load_db()
    db[str(call.from_user.id)]['pending_amount'] = float(val)
    save_db(db)
    
    text = f"✅ مبلغ الإيداع: **{val}$**\n🌐 الشبكة: **{net}**\n\nقم بالتحويل للعنوان أدناه:\n`{wallet}`\n\n⚠️ بعد التحويل، ارسل **صورة (Screenshot)** للإيصال هنا."
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db or not db[uid].get('full_name'):
        bot.send_message(message.chat.id, "❌ يرجى التسجيل أولاً باستخدام /start")
        return

    amount = db[uid].get('pending_amount', 0)
    name = db[uid].get('full_name', 'غير معروف')
    
    # إرسال للمسؤول
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ موافقة", callback_data=f"app_{uid}_{amount}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{uid}")
    )
    
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **إيداع جديد!**\n👤 المستخدم: {name}\n🆔 الآيدي: `{uid}`\n💰 المبلغ: **{amount}$**", reply_markup=markup, parse_mode='Markdown')
    
    bot.send_message(message.chat.id, "⏳ تم استلام إثباتك، سيتم مراجعته من قبل الإدارة وإضافته لرصيدك فوراً.")

# --- لوحة تحكم المسؤول ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_action(call):
    if call.from_user.id != CONFIG['ADMIN_ID']: return

    data = call.data.split('_')
    action = data[0]
    t_uid = data[1]
    
    db = load_db()
    
    if action == 'app':
        amount = float(data[2])
        db[t_uid]['balance'] += amount
        db[t_uid]['pending_amount'] = 0
        save_db(db)
        bot.send_message(t_uid, f"✅ تمت الموافقة على إيداعك! رصيدك الحالي: **{db[t_uid]['balance']}$**")
        bot.answer_callback_query(call.id, "تم التفعيل بنجاح")
    else:
        bot.send_message(t_uid, "❌ نعتذر، تم رفض إثبات الإيداع. تأكد من البيانات أو تواصل مع الدعم.")
        bot.answer_callback_query(call.id, "تم الرفض")

    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# --- عرض الرصيد ---
@bot.callback_query_handler(func=lambda call: call.data == 'view_balance')
def view_balance(call):
    uid = str(call.from_user.id)
    db = load_db()
    bal = db.get(uid, {}).get('balance', 0.0)
    bot.answer_callback_query(call.id, f"رصيدك الحالي هو: {bal}$", show_alert=True)

if __name__ == "__main__":
    print("🤖 البوت يعمل الآن...")
    bot.infinity_polling()
