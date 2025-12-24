import telebot
from telebot import types
import json
import os
import schedule
import time
import threading
from datetime import datetime

# --- 1. إعدادات البوت الكاملة ---
CONFIG = {
    'TOKEN': '8524828584:AAEt7svTqofhfYdxdlk-XAd5FH3OS886piY',
    'ADMIN_ID': 988759701, # معرفك كأدمن
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

# --- 3. نظام الأرباح التلقائي ---
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
            try: bot.send_message(uid, f"💰 **ربح يومي جديد:** تم إضافة {profit}$ لرصيدك.")
            except: pass
    save_db(db)

def run_scheduler():
    schedule.every().day.at("00:00").do(daily_profit_distribution)
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- 4. التحقق من الاشتراك ---
def is_subbed(user_id):
    try:
        status = bot.get_chat_member(CONFIG['CHANNEL_ID'], user_id).status
        return status not in ['left', 'kicked']
    except: return True

# --- 5. لوحة التحكم الرئيسية ---
def get_main_menu(uid):
    db = load_db()
    bal = db.get(str(uid), {}).get('balance', 0.0)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 إيداع واستثمار", callback_data='dep_info'),
        types.InlineKeyboardButton("📤 سحب (السبت)", callback_data='with_start')
    )
    markup.add(
        types.InlineKeyboardButton("💰 رصيدي", callback_data='view_balance'),
        types.InlineKeyboardButton("👥 الإحالة ($1)", callback_data='ref_system')
    )
    return f"🌟 أهلاً بك في **CoinsGlobalPop**\n\n💰 رصيدك الحالي: `{bal:.2f}$`", markup

# --- 6. معالجة الأوامر ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    db = load_db()

    if uid not in db:
        referrer = None
        if len(message.text.split()) > 1:
            ref_id = message.text.split()[1]
            if ref_id.isdigit() and ref_id != uid:
                referrer = ref_id
        db[uid] = {'balance': 0.0, 'name': message.from_user.first_name, 'base_deposit': 0, 'referrer': referrer}
        save_db(db)

    if not is_subbed(message.from_user.id):
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("📢 انضم للقناة", url=CONFIG['CHANNEL_LINK']))
        m.add(types.InlineKeyboardButton("🔄 تأكيد الاشتراك", callback_data='check_sub'))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك في القناة أولاً لتفعيل البوت.", reply_markup=m)
        return

    text, markup = get_main_menu(uid)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

# --- 7. استقبال صور الإيداع وإرسالها للأدمن ---
@bot.message_handler(content_types=['photo'])
def handle_payment_screenshot(message):
    uid = message.from_user.id
    # إرسال الصورة للأدمن مع أزرار الموافقة السريعة
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ موافقة (20$)", callback_data=f"ok_dep_{uid}_20"),
        types.InlineKeyboardButton("✅ موافقة (100$)", callback_data=f"ok_dep_{uid}_100"),
        types.InlineKeyboardButton("✅ موافقة (300$)", callback_data=f"ok_dep_{uid}_300")
    )
    # تحويل الصورة للأدمن
    bot.forward_message(CONFIG['ADMIN_ID'], message.chat.id, message.message_id)
    bot.send_message(CONFIG['ADMIN_ID'], f"📩 وصل إثبات إيداع جديد من: `{uid}`\nالاسم: {message.from_user.first_name}", reply_markup=markup, parse_mode='Markdown')
    # تأكيد للمستخدم
    bot.send_message(message.chat.id, "✅ تم استلام صورة الإثبات بنجاح. سيتم مراجعتها من قبل الإدارة وإضافة الرصيد لحسابك قريباً.")

# --- 8. معالجة التفاعلات وأزرار الموافقة ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = str(call.from_user.id)
    db = load_db()

    # نظام الموافقة على الإيداع (للأدمن فقط)
    if call.data.startswith('ok_dep_'):
        if call.from_user.id != CONFIG['ADMIN_ID']: return
        
        _, _, target_uid, amount = call.data.split('_')
        amount = float(amount)
        db = load_db()
        
        if target_uid in db:
            db[target_uid]['balance'] += amount
            db[target_uid]['base_deposit'] = amount
            
            # مكافأة الداعي 1$
            ref_id = db[target_uid].get('referrer')
            if ref_id and str(ref_id) in db:
                db[str(ref_id)]['balance'] += 1.0
                try: bot.send_message(ref_id, "🎊 مبروك! أحد الأشخاص الذين دعوتهم قام بالإيداع، وحصلت على 1$ مكافأة.")
                except: pass
                
            save_db(db)
            bot.send_message(target_uid, f"✅ تم تأكيد إيداعك بقيمة {amount}$ وبدأت خطة الاستثمار!")
            bot.edit_message_text(f"✅ تمت الموافقة على إيداع المستخدم {target_uid} بقيمة {amount}$", call.message.chat.id, call.message.message_id)
        return

    if call.data == 'check_sub':
        if is_subbed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ تم تأكيد الاشتراك!")
            text, markup = get_main_menu(uid)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في القناة بعد.", show_alert=True)

    elif call.data == 'dep_info':
        text = f"📥 **قسم الإيداع والاستثمار**\n\nيرجى إرسال المبلغ إلى أحد العناوين التالية:\n\n📌 **BEP20 (USDT):**\n`{CONFIG['WALLETS']['BEP20']}`\n\n📌 **TRC20 (USDT):**\n`{CONFIG['WALLETS']['TRC20']}`\n\n⚠️ **بعد التحويل:** ارسل صورة الإثبات (Screenshot) هنا في الشات وسنقوم بتفعيل حسابك."
        back = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_home'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back, parse_mode='Markdown')

    elif call.data == 'main_home':
        text, markup = get_main_menu(uid)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == 'view_balance':
        bal = db.get(uid, {}).get('balance', 0.0)
        bot.answer_callback_query(call.id, f"رصيدك: {bal:.2f}$", show_alert=True)

    elif call.data == 'ref_system':
        ref_link = f"https://t.me/{CONFIG['BOT_USERNAME']}?start={uid}"
        text = f"👥 **نظام الإحالة**\n\nاحصل على **1$** عن كل شخص يقوم بالإيداع عبر رابطك.\n\n🔗 رابطك: `{ref_link}`"
        back = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_home'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back, parse_mode='Markdown')

    elif call.data == 'with_start':
        if datetime.now().strftime('%A') != "Saturday":
            bot.answer_callback_query(call.id, "⚠️ السحب متاح يوم السبت فقط!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "ارسل عنوان محفظتك والمبلغ للأدمن لسحب رصيدك.", show_alert=True)

# --- 9. تشغيل البوت ---
if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("Bot is fully updated and running with Photo Confirmation...")
    bot.infinity_polling()
