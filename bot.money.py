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
# สำคัญ: นำ Internal Database URL ที่ก๊อปปี้มาวางแทนที่ตรงนี้ หรือตั้งเป็น Environment Variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "postgresql://money_db_lxmd_user:bPXBKJUY9Z7tvSiFVTgGwycwiQ8J96Ps@dpg-d541tdq4d50c738nt25g-a/money_db_lxmd")
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

def get_balance():
    s = db.session.query(db.func.sum(FinanceLog.amount)).filter(FinanceLog.type == 'save').scalar() or 0
    p = db.session.query(db.func.sum(FinanceLog.amount)).filter(FinanceLog.type == 'spend').scalar() or 0
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
    
    if msg.startswith("เก็บเงิน"):
        num = re.findall(r'\d+', msg)
        if num:
            amount = float(num[0])
            update_money('save', amount, "ฝากเงินสะสม")
            s, p = get_balance()
            reply = f"📥 【 บันทึกรายรับ 】\n💰 +{amount:,.2f} บาท\n✨ ยอดรวม: {s-p:,.2f} บาท"
        else: reply = "❌ รูปแบบ: เก็บเงิน 200"

    elif msg.startswith("ใช้เงิน"):
        parts = msg.split()
        if len(parts) >= 3:
            num = re.findall(r'\d+', parts[1])
            if num:
                amount = float(num[0])
                reason = " ".join(parts[2:])
                update_money('spend', amount, reason)
                s, p = get_balance()
                reply = f"💸 【 บันทึกรายจ่าย 】\n🔻 -{amount:,.2f} บาท\n📝 เหตุผล: {reason}\n📉 คงเหลือ: {s-p:,.2f} บาท"
            else: reply = "❌ ระบุจำนวนเงินไม่ถูกต้อง"
        else: reply = "⚠️ ต้องระบุเหตุผลด้วย! เช่น: ใช้เงิน 100 ค่าข้าว"

    elif msg == "สรุป":
        s, p = get_balance()
        reply = f"📊 【 สรุปยอด 】\n📥 สะสม: {s:,.2f}\n📤 จ่ายรวม: -{p:,.2f}\n━━━━━━━━━━\n✨ คงเหลือ: {s-p:,.2f} บาท"

    elif msg.lower() == "reset":
        db.session.query(FinanceLog).delete()
        db.session.commit()
        reply = "⚠️ ข้อมูลทั้งหมดถูกล้างแล้ว!"
    
    else:
        reply = "🏠 【 คำสั่ง 】\n• เก็บเงิน 100\n• ใช้เงิน 50 ค่าขนม\n• สรุป\n• reset"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

