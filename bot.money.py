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
    
    spend_list = [f"• {l.reason}: {l.amount:,.0f}" for l in logs if l.type == 'spend']
    spend_text = "\n".join(spend_list) if spend_list else "ไม่มีรายการ"
    
    return s, p, spend_text

# --- 4. ระบบแจ้งเตือนอัตโนมัติ (Endpoints สำหรับ Cron-job) ---
@app.route("/push_weekly")
def push_weekly():
    # แก้ไข 'ใส่_USER_ID_ที่นี่' หลังจากพิมพ์ 'id' ถามบอทใน LINE
    user_id = "U4ada3d1215dd4cce94feb9208d1834c0" 
    s, p, detail = get_detailed_summary(days=7)
    msg = (f"🔔 【 สรุปรายอาทิตย์จ้า 】\n"
           f"━━━━━━━━━━━━━━\n"
           f"💸 จ่ายรวม 7 วัน: {p:,.0f} บาท\n"
           f"📝 รายการที่ใช้:\n{detail}\n\n"
           f"💰 สุทธิช่วงนี้: {s-p:,.0f} บาท")
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        return "Weekly summary sent!", 200
    except:
        return "Failed to send", 500

@app.route("/push_monthly")
def push_monthly():
    user_id = "U4ada3d1215dd4cce94feb9208d1834c0"
    s, p, detail = get_detailed_summary(days=30)
    msg = (f"📢 【 สรุปรายเดือนจ้า 】\n"
           f"━━━━━━━━━━━━━━\n"
           f"💸 จ่ายรวม 30 วัน: {p:,.0f} บาท\n"
           f"📝 รายการที่ใช้:\n{detail}\n\n"
           f"💰 สุทธิเดือนนี้: {s-p:,.0f} บาท")
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        return "Monthly summary sent!", 200
    except:
        return "Failed to send", 500

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
    
    # คำสั่งพิเศษสำหรับเช็ค ID
    if msg.lower() == "id":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=event.source.user_id))

    elif msg.startswith("เก็บเงิน"):
        num = re.findall(r'\d+', msg)
        if num:
            update_money('save', float(num[0]), "ฝากเงิน")
            reply = "บันทึกข้อมูลสำเร็จแล้ว"
        else: reply = "ลืมใส่จำนวนเงินหรือเปล่า? เช่น: เก็บเงิน 100"

    elif msg.startswith("ใช้เงิน"):
        parts = msg.split()
        if len(parts) >= 3:
            num = re.findall(r'\d+', parts[1])
            if num:
                amount = float(num[0])
                reason = " ".join(parts[2:])
                update_money('spend', amount, reason)
                reply = "บันทึกข้อมูลสำเร็จแล้ว"
            else: reply = "ระบุจำนวนเงินไม่ถูกนะ"
        else: reply = "บอกเหตุผลด้วยนะ เช่น: ใช้เงิน 100 ค่าข้าว"

    elif msg == "สรุป":
        s, p, _ = get_detailed_summary()
        reply = (f"📊 【 สรุปยอดทั้งหมด 】\n"
                 f"➕ เก็บ: {s:,.0f}\n"
                 f"➖ จ่าย: {p:,.0f}\n"
                 f"💰 คงเหลือ: {s-p:,.0f} บาท")

    elif msg == "สรุปอาทิตย์นี้":
        s, p, detail = get_detailed_summary(days=7)
        reply = (f"📅 【 สรุป 7 วันล่าสุด 】\n"
                 f"💸 จ่ายไปทั้งหมด: {p:,.0f}\n\n"
                 f"📝 รายการจ่าย:\n{detail}\n\n"
                 f"📉 สุทธิอาทิตย์นี้: {s-p:,.0f} บาท")

    elif msg == "สรุปเดือนนี้":
        s, p, detail = get_detailed_summary(days=30)
        reply = (f"🗓️ 【 สรุป 30 วันล่าสุด 】\n"
                 f"💸 จ่ายไปทั้งหมด: {p:,.0f}\n\n"
                 f"📝 รายการจ่าย:\n{detail}\n\n"
                 f"📉 สุทธิเดือนนี้: {s-p:,.0f} บาท")

    elif msg.lower() == "reset":
        db.session.query(FinanceLog).delete()
        db.session.commit()
        reply = "ล้างข้อมูลให้เกลี้ยงแล้วครับ! 🧹"
    
    else:
        reply = ("🤖 วิธีคุยกับบอทจ้า:\n"
                 "• เก็บเงิน 100\n"
                 "• ใช้เงิน 100 ค่าข้าว\n"
                 "• สรุปอาทิตย์นี้\n"
                 "• สรุปเดือนนี้\n"
                 "• พิมพ์ 'id' เพื่อดูไอดีตัวเอง")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
