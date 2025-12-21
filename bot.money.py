from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import sqlite3
import re
from datetime import datetime, timedelta

app = Flask(__name__)

# --- 1. ตั้งค่า Token (ใช้ค่าที่คุณระบุมา) ---
LINE_ACCESS_TOKEN = "w6hXGsdzBxQN4H6G/HT9BclvbSIzvGpd6ZWNYeow0zzdqqF+iW404xEwYJqO5RO1WMHU1U4AWMBtDMR6gqjXMHvWIfoH5QD294FabeZRgo4t90OeEW+wgsNnYeromvNafeiLVC140C7lStpX3BiAAQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "d6a2078c9f627f8c52ec831aa91b5217"

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 2. ระบบจัดการฐานข้อมูล ---
def init_db():
    conn = sqlite3.connect('finance_ultimate.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  type TEXT, amount REAL, reason TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

def update_money(t_type, amount, reason=""):
    conn = sqlite3.connect('finance_ultimate.db')
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs (type, amount, reason, timestamp) VALUES (?, ?, ?, ?)", 
               (t_type, amount, reason, now))
    conn.commit()
    conn.close()

def get_balance_info():
    conn = sqlite3.connect('finance_ultimate.db')
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM logs WHERE type='save'")
    s = c.fetchone()[0] or 0
    c.execute("SELECT SUM(amount) FROM logs WHERE type='spend'")
    p = c.fetchone()[0] or 0
    conn.close()
    return s, p

# --- 3. ส่วนการทำงานของ Webhook ---
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
    now = datetime.now()
    
    # ➕ บันทึกรายรับ
    if msg.startswith("เก็บเงิน"):
        num = re.findall(r'\d+', msg)
        if num:
            amount = float(num[0])
            update_money('save', amount, "ฝากเงินสะสม")
            s, p = get_balance_info()
            reply = (f"📥 【 บันทึกรายรับ 】\n━━━━━━━━━━━━━━\n"
                     f"💰 จำนวน:  +{amount:,.2f} บาท\n"
                     f"✨ ยอดสะสมรวม: {s-p:,.2f} บาท")
        else:
            reply = "❌ รูปแบบผิด! พิมพ์: เก็บเงิน 200"

    # ➖ บันทึกรายจ่าย (บังคับบอกเหตุผลเข้มงวด)
    elif msg.startswith("ใช้เงิน"):
        parts = msg.split()
        if len(parts) >= 3: # ต้องมี: 1.ใช้เงิน 2.ตัวเลข 3.เหตุผล
            num_check = re.findall(r'\d+', parts[1])
            if num_check:
                amount = float(num_check[0])
                reason = " ".join(parts[2:])
                update_money('spend', amount, reason)
                s, p = get_balance_info()
                reply = (f"💸 【 บันทึกรายจ่าย 】\n━━━━━━━━━━━━━━\n"
                         f"🔻 จำนวน:  -{amount:,.2f} บาท\n"
                         f"📝 เหตุผล:  {reason}\n"
                         f"📉 คงเหลือ: {s-p:,.2f} บาท")
            else:
                reply = "❌ ระบุจำนวนเงินไม่ถูกต้อง (ตัวอย่าง: ใช้เงิน 100 ค่าข้าว)"
        else:
            reply = ("⚠️ กรุณาระบุเหตุผลด้วยครับ!\n"
                     "━━━━━━━━━━━━━━\n"
                     "💡 รูปแบบ: ใช้เงิน [จำนวน] [เหตุผล]\n"
                     "📝 ตัวอย่าง: ใช้เงิน 100 ค่ากาแฟ")

    # 📅 สรุปรายสัปดาห์ (แสดงทุกรายการจ่ายตั้งแต่วันจันทร์)
    elif msg == "สรุป":
        s, p = get_balance_info()
        start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
        start_str = start_of_week.strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect('finance_ultimate.db')
        c = conn.cursor()
        c.execute("SELECT amount, reason, timestamp FROM logs WHERE type='spend' AND timestamp >= ? ORDER BY timestamp ASC", (start_str,))
        logs = c.fetchall()
        conn.close()
        
        history, weekly_p = "", 0
        for amt, reas, ts in logs:
            day_month = ts[8:10] + "/" + ts[5:7]
            history += f"• {day_month} | {reas}: -{amt:,.0f}\n"
            weekly_p += amt

        reply = (f"📊 【 สรุปรายสัปดาห์ 】\n"
                 f"📅 ตั้งแต่: {start_of_week.strftime('%d/%m/%Y')}\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"📥 สะสมรวม: {s:,.2f}\n"
                 f"📤 จ่ายอาทิตย์นี้: -{weekly_p:,.2f}\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"📑 รายการจ่ายทั้งหมด:\n{history if history else 'ยังไม่มีรายการ'}\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"✨ คงเหลือสุทธิ: {s-p:,.2f} บาท")

    # 🏆 สรุปใหญ่รายเดือน
    elif msg == "สรุปเดือน":
        s, p = get_balance_info()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        start_str = start_of_month.strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect('finance_ultimate.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM logs WHERE type='spend' AND timestamp >= ?", (start_str,))
        m_p = c.fetchone()[0] or 0
        c.execute("SELECT SUM(amount) FROM logs WHERE type='save' AND timestamp >= ?", (start_str,))
        m_s = c.fetchone()[0] or 0
        conn.close()

        reply = (f"🏆 【 สรุปใหญ่รายเดือน 】\n📅 เดือน: {now.strftime('%m/%Y')}\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"💰 รายรับเดือนนี้:  {m_s:,.2f} บาท\n"
                 f"💸 รายจ่ายเดือนนี้: -{m_p:,.2f} บาท\n"
                 f"━━━━━━━━━━━━━━\n"
                 f"✨ ยอดคงเหลือรวม: {s-p:,.2f} บาท")

    # ⚠️ รีเซ็ตข้อมูล
    elif msg.lower() == "reset":
        conn = sqlite3.connect('finance_ultimate.db')
        c = conn.cursor()
        c.execute("DELETE FROM logs")
        conn.commit()
        conn.close()
        reply = "⚠️ 【 RESET 】\nล้างข้อมูลทั้งหมดเรียบร้อยแล้วครับ!"

    else:
        reply = ("🏠 【 เมนูบอทกระเป๋าตังค์ 】\n"
                 "• เก็บเงิน [บาท]\n"
                 "• ใช้เงิน [บาท] [เหตุผล]\n"
                 "• สรุป (รายสัปดาห์)\n"
                 "• สรุปเดือน\n"
                 "• reset")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    init_db()
    
    # --- ส่วนที่ต้องแก้ให้เป็นแบบนี้ ---
    import os
    # Render จะเป็นคนกำหนด PORT ให้เองผ่าน Environment Variable
    port = int(os.environ.get("PORT", 5000))
    # ต้องตั้ง host เป็น "0.0.0.0" เพื่อให้ภายนอกเชื่อมต่อเข้ามาได้
    app.run(host="0.0.0.0", port=port)
