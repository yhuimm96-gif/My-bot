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

# --- دوال قاعدة البيانات ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if data else {}
    except:
        return {}

def save_db(db):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving DB: {e}")

# --- نظام الأرباح التلقائي ---
def add_daily_profits():
    db = load_db()
    for uid in db:
        deposited_val = db[uid].get('deposit_amount', 0)
        profit = 0
        if deposited_val == 20: profit = 0.6
        elif deposited_val == 100: profit = 3.3
        elif deposited_val == 300: profit = 10.0
            
        if profit > 0:
            db[uid]['balance'] = db[uid].get('balance', 0.0) + profit
            db[uid]['withdrawable_profit'] = db[uid].get('withdrawable_profit', 0.0) + profit
            try:
                bot.send_message(uid, f"💰 **أرباح يومية جديدة!**\n📈 تم إضافة: `+{profit}$` لرصيد السحب.", parse_mode='Markdown')
            except:
                continue
    save_db(db)

scheduler = BackgroundScheduler()
scheduler.add_job(add_daily_profits, 'interval', hours=24)
scheduler.start()

# --- التحقق من الاشتراك ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def send_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 انضم للقناة الآن", url=CONFIG['CHANNEL_LINK']))
    bot.send_message(chat_id, "⚠️ للبدء في استخدام البوت، يجب عليك الاشتراك في القناة أولاً!", reply_markup=markup)

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
            'balance': 0.0, 
            'withdrawable_profit': 0.0, 
            'full_name': None, 
            'referred_by': referrer, 
            'referrals_count': 0, 
            'active_referrals': 0, 
            'has_deposited': False, 
            'deposit_amount': 0,
            'pending_amount': 0
        }
        if referrer and referrer in db:
            db[referrer]['referrals_count'] = db[referrer].get('referrals_count', 0) + 1
        save_db(db)
        bot.send_message(CONFIG['ADMIN_ID'], f"👤 **مستخدم جديد:**\nالاسم: {message.from_user.first_name}\nالأيدي: `{uid}`")

    if not db[uid].get('full_name'):
        msg = bot.send_message(message.chat.id, "👋 يرجى إرسال اسمك الثلاثي لتفعيل حسابك:")
        bot.register_next_step_handler(msg, save_user_name)
    else:
        show_menu(message)

def save_user_name(message):
    uid = str(message.from_user.id)
    db = load_db()
    if message.text and len(message.text.split()) >= 3:
        db[uid]['full_name'] = message.text
        save_db(db)
        show_menu(message)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ الاسم غير مكتمل. يرجى إرسال اسمك الثلاثي (3 كلمات على الأقل):")
        bot.register_next_step_handler(msg, save_user_name)

def show_menu(message):
    uid = str(message.from_user.id)
    db = load_db()
    user = db.get(uid, {})
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📥 إيداع", callback_data='deposit_start'), 
               types.InlineKeyboardButton("📤 سحب الأرباح", callback_data='withdraw_start'))
    markup.add(types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'), 
               types.InlineKeyboardButton("👥 الإحالات", callback_data='referral_info'))
    markup.add(types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{CONFIG['ADMIN_USERNAME'].replace('@','')}"))
    
    msg_text = (f"🏠 **لوحة التحكم**\n\n👤 المستثمر: `{user.get('full_name')}`\n"
                f"💰 الرصيد الكلي: `{user.get('balance', 0):.2f}$` \n"
                f"💸 القابل للسحب: `{user.get('withdrawable_profit', 0):.2f}$` \n"
                f"👥 الإحالات: {user.get('referrals_count', 0)} (الفعالة: {user.get('active_referrals', 0)})")
    bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='Markdown')

# --- معالجة الإيداع وصور الإثبات ---
@bot.message_handler(content_types=['photo'])
def handle_payment_proof(message):
    uid = str(message.from_user.id)
    db = load_db()
    if uid not in db or db[uid].get('has_deposited'): return

    pending_amt = db[uid].get('pending_amount', 0)
    if pending_amt == 0:
        bot.send_message(message.chat.id, "⚠️ يرجى اختيار مبلغ الإيداع من القائمة أولاً قبل إرسال الصورة.")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول الإيداع", callback_data=f"app_{uid}_{pending_amt}"), 
               types.InlineKeyboardButton("❌ رفض الإيداع", callback_data=f"rej_{uid}"))
    
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 **إثبات إيداع جديد**\n👤 الاسم: {db[uid]['full_name']}\n💵 المبلغ المطلوب: {pending_amt}$", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال الإثبات للإدارة. سيتم تفعيل حسابك فور التأكد.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    db = load_db()
    if uid not in db and not call.data.startswith(('app_', 'rej_', 'wapp_', 'wrej_')): return

    if call.data == 'view_balance':
        user = db.get(uid, {})
        bot.answer_callback_query(call.id, f"الرصيد الكلي: {user.get('balance',0):.2f}$\nرصيد السحب: {user.get('withdrawable_profit',0):.2f}$", show_alert=True)

    elif call.data == 'referral_info':
        ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
        user = db.get(uid, {})
        bot.send_message(call.message.chat.id, f"👥 **نظام الإحالة**\n\n- اربح 1$ عن كل شخص يشحن!\n- رابطك الشخصي:\n`{ref_link}`\n\n- الإحالات الفعالة: {user.get('active_referrals', 0)}", parse_mode='Markdown')

    elif call.data == 'deposit_start':
        if db[uid].get('has_deposited'):
            bot.answer_callback_query(call.id, "⚠️ مسموح بالإيداع مرة واحدة فقط!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💵 20$ (ربح يومي 0.6$)", callback_data='v_20'), 
                   types.InlineKeyboardButton("💵 100$ (ربح يومي 3.3$)", callback_data='v_100'), 
                   types.InlineKeyboardButton("💵 300$ (ربح يومي 10$)", callback_data='v_300'))
        bot.edit_message_text("💰 اختر باقة الإيداع المناسبة لك:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('v_'):
        val = int(call.data.split('_')[1])
        db[uid]['pending_amount'] = val
        save_db(db)
        bot.edit_message_text(f"✅ لقد اخترت باقة {val}$\nيرجى تحويل المبلغ لعنوان TRC20 التالي:\n\n`{CONFIG['WALLETS']['TRC20']}`\n\nبعد التحويل، أرسل صورة إثبات الدفع هنا.", call.message.chat.id, call.message.message_id)

    elif call.data == 'withdraw_start':
        withdrawable = db[uid].get('withdrawable_profit', 0.0)
        if withdrawable <= 0:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد أرباح متاحة للسحب حالياً!", show_alert=True)
            return
        
        withdraw_msg = (
            "📤 **طلب سحب جديد**\n\n"
            "⚠️ **تنبيهات هامة:**\n"
            "- لا يمكنك سحب رأس المال.\n"
            "- السحب متاح فقط لـ الأرباح اليومية وأرباح الإحالات.\n\n"
            f"💰 الرصيد المتاح للسحب: `{withdrawable:.2f}$`\n"
            "💬 أدخل المبلغ المراد سحبه:"
        )
        msg = bot.send_message(call.message.chat.id, withdraw_msg, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_withdraw_amount)

    # --- معالجة طلبات الآدمن ---
    if int(uid) == CONFIG['ADMIN_ID']:
        data = call.data.split('_')
        # قبول/رفض الإيداع
        if data[0] == 'app':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['balance'] = amt
            db[t_uid]['deposit_amount'] = amt
            db[t_uid]['has_deposited'] = True
            # عمولة الإحالة
            ref_id = db[t_uid].get('referred_by')
            if ref_id and ref_id in db:
                db[ref_id]['balance'] = db[ref_id].get('balance', 0) + 1.0
                db[ref_id]['withdrawable_profit'] = db[ref_id].get('withdrawable_profit', 0) + 1.0
                db[ref_id]['active_referrals'] = db[ref_id].get('active_referrals', 0) + 1
                try: bot.send_message(ref_id, "🎁 مبروك! حصلت على 1$ مكافأة إحالة.")
                except: pass
            save_db(db)
            bot.send_message(t_uid, "✅ تم قبول إيداعك بنجاح! ستبدأ أرباحك بالنزول يومياً.")
            bot.edit_message_text(f"✅ تم تفعيل حساب {db[t_uid]['full_name']}", call.message.chat.id, call.message.message_id)
        
        elif data[0] == 'rej':
            bot.send_message(data[1], "❌ نعتذر، تم رفض إثبات الإيداع الخاص بك.")
            bot.edit_message_text("❌ تم الرفض.", call.message.chat.id, call.message.message_id)

        # قبول/رفض السحب
        elif data[0] == 'wapp':
            t_uid, amt = data[1], float(data[2])
            bot.send_message(t_uid, f"✅ **تمت الموافقة على سحب مبلغ {amt}$**\nالأموال في طريقها لمحفظتك.")
            bot.edit_message_text(f"✅ تم تأكيد تحويل {amt}$ لـ {db[t_uid].get('full_name')}", call.message.chat.id, call.message.message_id)
        
        elif data[0] == 'wrej':
            t_uid, amt = data[1], float(data[2])
            db[t_uid]['withdrawable_profit'] += amt
            db[t_uid]['balance'] += amt
            save_db(db)
            bot.send_message(t_uid, f"❌ **تم رفض طلب السحب بمبلغ {amt}$**\nتم إعادة الرصيد لحسابك.")
            bot.edit_message_text(f"❌ تم رفض السحب وإعادة الرصيد.", call.message.chat.id, call.message.message_id)

def process_withdraw_amount(message):
    try:
        amt = float(message.text)
        uid = str(message.from_user.id)
        db = load_db()
        if amt > db[uid].get('withdrawable_profit', 0):
            bot.send_message(message.chat.id, "⚠️ الرصيد غير كافٍ.")
            return
        if amt <= 0: return
            
        msg = bot.send_message(message.chat.id, "💳 أدخل عنوان محفظتك TRC20:")
        bot.register_next_step_handler(msg, final_withdraw_request, amt)
    except:
        bot.send_message(message.chat.id, "⚠️ يرجى إدخال رقم صحيح.")

def final_withdraw_request(message, amt):
    uid = str(message.from_user.id)
    db = load_db()
    db[uid]['withdrawable_profit'] -= amt
    db[uid]['balance'] -= amt
    save_db(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تم التحويل", callback_data=f"wapp_{uid}_{amt}"), 
               types.InlineKeyboardButton("❌ رفض السحب", callback_data=f"wrej_{uid}_{amt}"))
    
    bot.send_message(CONFIG['ADMIN_ID'], f"📤 **طلب سحب جديد**\n👤 الاسم: {db[uid]['full_name']}\n💰 المبلغ: {amt}$\n💳 العنوان: `{message.text}`", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ تم إرسال طلب السحب. سيصلك إشعار فور المراجعة.")

if __name__ == "__main__":
    print("البوت يعمل بنجاح...")
    bot.infinity_polling()
