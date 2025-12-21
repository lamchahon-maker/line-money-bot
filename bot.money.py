from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from flask_sqlalchemy import SQLAlchemy
import os, re
from datetime import datetime, timedelta

app = Flask(__name__)

# --- 1. ตั้งค่า LINE Token ---
LINE_ACCESS_TOKEN = "w6hXGsdzBxQN4H6G/HT9BclvbSIzvGpd6ZWNYeow0zzdqqF+iW404xEwYJqO5RO1WMHU1U4AWMBtDMR6gqjXMHvWIfoH5QD294FabeZRgo4t90OeEW+wgsNnYeromvNafeiLVC140C7lStpX3BiAAQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "d6a2078c9f627f8c52ec831aa91b5217from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from flask_sqlalchemy import SQLAlchemy
import os, re
from datetime import datetime, timedelta

app = Flask(__name__)

# --- 1. ตั้งค่า LINE Token ---
LINE_ACCESS_TOKEN = "w6hXGsdzBxQN4H6G/HT9BclvbSIzvGpd6ZWNYeow0zzdqqF+iW404xEwYJqO5RO1WMHU1U4AWMBtDMR6gqjXMHvWIfoH5QD294FabeZRgo4t90OeEW+wgsNnYeromvNafeiLVC140C7lStpX3BiAAQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "d6a2078c9f627f8c52ec831aa91b5217"

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 2. ระบบฐานข้อมูล PostgreSQL ---
DB_URL = "postgresql://money_db_lxmd_user:bPXBKJUY9Z7tvSiFVTgGwycwiQ8J96Ps@dpg-d541tdq4d50c738nt25g-a/money_db_lxmd"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", DB_URL)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class FinanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))
    amount = db.Column(db.Float)
    reason = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- 3. ฟังก์ชันจัดการข้อมูล ---
def update_money(t_type, amount, reason=""):
    new_log = FinanceLog(type=t_type, amount=amount, reason=reason)
    db.session.add(new_log)
    db.session.commit()

def get_detailed_summary(days=None):
    query = FinanceLog.query
    if days:
        start_date = datetime.now() - timedelta(days=days)
        query = query.filter(FinanceLog.timestamp >= start_date)
    
    logs = query.all()
    s = sum(l.amount for l in logs if l.type == 'save')
    p = sum(l.amount for l in logs if l.type == 'spend')
    
    # ดึงเฉพาะรายการจ่ายมาลิสต์
    spend_list = [f"- {l.reason}: {l.amount:,.0f}" for l in logs if l.type == 'spend']
    spend_text = "\n".join(spend_list) if spend_list else "ไม่มีรายการ"
    
    return s, p, spend_text

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    
    if msg.startswith("เก็บเงิน"):
        num = re.findall(r'\d+', msg)
        if num:
            update_money('save', float(num[0]), "ฝากเงิน")
            reply = "บันทึกข้อมูลสำเร็จแล้ว"
        else: reply = "บอกจำนวนเงินด้วย เช่น เก็บเงิน 100"

    elif msg.startswith("ใช้เงิน"):
        parts = msg.split()
        if len(parts) >= 3:
            num = re.findall(r'\d+', parts[1])
            if num:
                update_money('spend', float(num[0]), " ".join(parts[2:]))
                reply = "บันทึกข้อมูลสำเร็จ"
            else: reply = "ระบุจำนวนเงินไม่ถูก"
        else: reply = "ต้องบอกเหตุผลด้วย เช่น ใช้เงิน 100 ค่าข้าว"

    elif msg == "สรุป":
        s, p, _ = get_detailed_summary()
        reply = f"📊 ยอดรวมทั้งหมด\n➕ เก็บ: {s:,.0f}\n➖ จ่าย: {p:,.0f}\n💰 คงเหลือ: {s-p:,.0f}"

    elif msg == "สรุปอาทิตย์นี้":
        s, p, detail = get_detailed_summary(days=7)
        reply = f"📅 7 วันที่ผ่านมา\n💸 จ่ายไปทั้งหมด: {p:,.0f}\n\nรายการที่จ่าย:\n{detail}\n\n📉 สุทธิอาทิตย์นี้: {s-p:,.0f}"

    elif msg == "สรุปเดือนนี้":
        s, p, detail = get_detailed_summary(days=30)
        reply = f"🗓️ 30 วันที่ผ่านมา\n💸 จ่ายไปทั้งหมด: {p:,.0f}\n\nรายการที่จ่าย:\n{detail}\n\n📉 สุทธิเดือนนี้: {s-p:,.0f}"

    elif msg.lower() == "reset":
        db.session.query(FinanceLog).delete()
        db.session.commit()
        reply = "ล้างข้อมูลให้เกลี้ยงแล้วครับ!"
    
    else:
        reply = "พิมพ์ตามนี้นะ:\n• เก็บเงิน 100\n• ใช้เงิน 100 ค่าข้าว\n• สรุปอาทิตย์นี้ / สรุปเดือนนี้"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 2. ระบบฐานข้อมูล PostgreSQL ---
# ใช้ URL ของคุณที่คุณก๊อปปี้มาจาก Render
DB_URL = "postgresql://money_db_lxmd_user:bPXBKJUY9Z7tvSiFVTgGwycwiQ8J96Ps@dpg-d541tdq4d50c738nt25g-a/money_db_lxmd"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", DB_URL)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class FinanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))
    amount = db.Column(db.Float)
    reason = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- 3. ฟังก์ชันจัดการข้อมูล ---
def update_money(t_type, amount, reason=""):
    new_log = FinanceLog(type=t_type, amount=amount, reason=reason)
    db.session.add(new_log)
    db.session.commit()

def get_balance(days=None):
    query_s = db.session.query(db.func.sum(FinanceLog.amount)).filter(FinanceLog.type == 'save')
    query_p = db.session.query(db.func.sum(FinanceLog.amount)).filter(FinanceLog.type == 'spend')
    if days:
        start_date = datetime.now() - timedelta(days=days)
        query_s = query_s.filter(FinanceLog.timestamp >= start_date)
        query_p = query_p.filter(FinanceLog.timestamp >= start_date)
    s = query_s.scalar() or 0
    p = query_p.scalar() or 0
    return s, p

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    
    # 💰 บันทึกรายรับ
    if msg.startswith("เก็บเงิน"):
        num = re.findall(r'\d+', msg)
        if num:
            amount = float(num[0])
            update_money('save', amount, "เงินออม/รายรับ")
            s, p = get_balance()
            reply = (f"🟢 【 บันทึกรายรับ 】\n"
                     f"━━━━━━━━━━━━━━\n"
                     f"💰 ยอดเงิน: +{amount:,.2f} บาท\n"
                     f"✅ บันทึกสำเร็จ\n"
                     f"✨ ยอดรวมคงเหลือ: {s-p:,.2f} บาท")
        else: reply = "❌ รูปแบบผิด! ลองพิมพ์: เก็บเงิน 500"

    # 💸 บันทึกรายจ่าย
    elif msg.startswith("ใช้เงิน"):
        parts = msg.split()
        if len(parts) >= 3:
            num = re.findall(r'\d+', parts[1])
            if num:
                amount = float(num[0])
                reason = " ".join(parts[2:])
                update_money('spend', amount, reason)
                s, p = get_balance()
                reply = (f"🔴 【 บันทึกรายจ่าย 】\n"
                         f"━━━━━━━━━━━━━━\n"
                         f"💸 ยอดเงิน: -{amount:,.2f} บาท\n"
                         f"📝 เหตุผล: {reason}\n"
                         f"📉 คงเหลือสุทธิ: {s-p:,.2f} บาท")
            else: reply = "❌ ระบุจำนวนเงินไม่ถูกต้อง"
        else: reply = "⚠️ ใส่เหตุผลด้วยนะ! เช่น: ใช้เงิน 100 ค่าข้าว"

    # 📊 สรุปทั้งหมด
    elif msg == "สรุป":
        s, p = get_balance()
        reply = (f"🏆 【 สรุปภาพรวมทั้งหมด 】\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"📥 รายรับสะสม: {s:,.2f}\n"
                 f"📤 รายจ่ายสะสม: {p:,.2f}\n"
                 f"--------------------------\n"
                 f"💰 ยอดเงินคงเหลือ: {s-p:,.2f} บาท")

    # 📅 สรุปรายอาทิตย์
    elif msg == "สรุปอาทิตย์นี้":
        s, p = get_balance(days=7)
        reply = (f"🗓️ 【 สรุป 7 วันล่าสุด 】\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"🟢 รับมา: {s:,.2f}\n"
                 f"🔴 จ่ายไป: {p:,.2f}\n"
                 f"📊 ยอดรวมช่วงนี้: {s-p:,.2f} บาท")

    # 🗓️ สรุปรายเดือน
    elif msg == "สรุปเดือนนี้":
        s, p = get_balance(days=30)
        reply = (f"📅 【 สรุป 30 วันล่าสุด 】\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"🟢 รับมา: {s:,.2f}\n"
                 f"🔴 จ่ายไป: {p:,.2f}\n"
                 f"📊 ยอดรวมช่วงนี้: {s-p:,.2f} บาท")

    # ⚠️ รีเซ็ต
    elif msg.lower() == "reset":
        db.session.query(FinanceLog).delete()
        db.session.commit()
        reply = "⚠️ ข้อมูลทั้งหมดถูกล้างเรียบร้อยแล้ว!"
    
    # 🏠 เมนู
    else:
        reply = ("ยินดีต้อนรับสู่บอทบัญชี! 🤖✨\n"
                 "━━━━━━━━━━━━━━\n"
                 "👉 【 วิธีใช้งาน 】\n"
                 "• เก็บเงิน 500\n"
                 "• ใช้เงิน 100 ค่าข้าว\n\n"
                 "📊 【 ดูสรุปยอด 】\n"
                 "• สรุป (ยอดทั้งหมด)\n"
                 "• สรุปอาทิตย์นี้\n"
                 "• สรุปเดือนนี้\n\n"
                 "🗑️ พิมพ์ 'reset' เพื่อล้างข้อมูล")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

