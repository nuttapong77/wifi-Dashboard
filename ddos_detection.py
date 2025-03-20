import sqlite3
import time

# ฟังก์ชันในการเชื่อมต่อกับฐานข้อมูลและดึงข้อมูล
def fetch_network_metrics():
    conn = sqlite3.connect('network_metrics.db')
    cursor = conn.cursor()

    # ดึงข้อมูลจากตาราง network_metrics
    cursor.execute('''
        SELECT * FROM network_metrics ORDER BY timestamp DESC LIMIT 1
    ''')
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        # ถ้ามีข้อมูลจะส่งค่าที่ดึงมาให้
        timestamp, download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count, ssid = result
        return download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count
    else:
        # ถ้าไม่พบข้อมูล
        return None

# ฟังก์ชันในการตรวจจับ DDoS โดยใช้ข้อมูลจากฐานข้อมูล
def detect_ddos():
    metrics = fetch_network_metrics()
    
    if not metrics:
        return ["No metrics available"]
    
    download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count = metrics
    alerts = []

    # การตรวจจับพฤติกรรมผิดปกติ:
    # 1. ตรวจจับแบนด์วิดธ์สูง (Bandwidth Utilization)
    if download_speed > 1e9:  # ถ้าแบนด์วิดธ์ดาวน์โหลดเกิน 1 Gbps
        alerts.append("Detected potential DDoS: High download speed")
    if upload_speed > 1e9:  # ถ้าแบนด์วิดธ์อัพโหลดเกิน 1 Gbps
        alerts.append("Detected potential DDoS: High upload speed")

    # 2. ตรวจจับการสูญเสียแพ็กเก็ต (Packet Loss)
    if packet_loss > 0.5:  # ถ้าการสูญเสียแพ็กเก็ตเกิน 50%
        alerts.append(f"Detected potential DDoS: High packet loss ({packet_loss:.2%})")
    
    # 3. ตรวจจับจำนวนอุปกรณ์ที่เชื่อมต่อ (Device Count)
    if device_count > 50:  # ถ้าจำนวนอุปกรณ์เชื่อมต่อเกิน 50 เครื่อง
        alerts.append("Detected potential DDoS: High number of devices on the network")
    
    # 4. ตรวจจับ Latency สูง (Latency)
    if latency > 200:  # ถ้า Latency เกิน 200 ms
        alerts.append(f"Detected potential DDoS: High latency ({latency} ms)")
    
    # 5. การตรวจจับการเปลี่ยนแปลงในเวลาที่รวดเร็ว (Rate of Change Detection)
    # บันทึกค่าเก่าจากการตรวจจับครั้งก่อนหน้า
    if hasattr(detect_ddos, "previous_metrics"):
        prev_metrics = detect_ddos.previous_metrics
        download_speed_change = abs(download_speed - prev_metrics["download_speed"])
        upload_speed_change = abs(upload_speed - prev_metrics["upload_speed"])
        device_count_change = abs(device_count - prev_metrics["device_count"])

        if download_speed_change > 1e8:  # ถ้าแบนด์วิดธ์ดาวน์โหลดเปลี่ยนแปลงเกิน 100 Mbps
            alerts.append("Detected rapid change in download speed")
        
        if upload_speed_change > 1e8:  # ถ้าแบนด์วิดธ์อัพโหลดเปลี่ยนแปลงเกิน 100 Mbps
            alerts.append("Detected rapid change in upload speed")
        
        if device_count_change > 10:  # ถ้าจำนวนอุปกรณ์เปลี่ยนแปลงเกิน 10 เครื่องในช่วงเวลาสั้นๆ
            alerts.append("Detected rapid change in device count")
    
    # บันทึกข้อมูลการตรวจจับครั้งล่าสุด
    detect_ddos.previous_metrics = {
        "download_speed": download_speed,
        "upload_speed": upload_speed,
        "device_count": device_count
    }

    return alerts

# ทดสอบการตรวจจับ DDoS
alerts = detect_ddos()
for alert in alerts:
    print(alert)
