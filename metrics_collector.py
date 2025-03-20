import sqlite3
import datetime
import pytz
import subprocess
import psutil
import ping3
import speedtest
from scapy.all import sniff, ARP
import schedule
import time
from prometheus_client import start_http_server, Gauge, Info

# ชื่อไฟล์ฐานข้อมูล
DB_NAME = 'network_metrics.db'

# Prometheus metrics    
signal_strength_gauge = Gauge('wifi_signal_strength', 'WiFi Signal Strength', ['frequency'])
download_speed_gauge = Gauge('download_speed', 'Download Speed')
upload_speed_gauge = Gauge('upload_speed', 'Upload Speed')
latency_gauge = Gauge('latency', 'Latency')
packet_loss_gauge = Gauge('packet_loss', 'Packet Loss')
bytes_sent_gauge = Gauge('bytes_sent', 'Bytes Sent')
bytes_recv_gauge = Gauge('bytes_recv', 'Bytes Received')
device_count_gauge = Gauge('device_count', 'Device Count')

# Info metrics for Wi-Fi channels
channel_info_metric = Info('wifi_channel_info', 'WiFi Info by Channel', ['channel', 'bssid', 'ssid'])

# ระบุหน่วงเวลาในวินาที (เช่น 60 วินาที)
DELAY = 60

# ฟังก์ชันที่จะให้เวลาตามท้องถิ่น (เช่น เวลาในประเทศไทย)
def get_local_time():
    local_timezone = pytz.timezone("Asia/Bangkok")  # หรือเขียนตามเวลาในภูมิภาคที่คุณต้องการ
    return datetime.datetime.now(local_timezone).strftime('%Y-%m-%d %H:%M:%S')

# ฟังก์ชันสร้างฐานข้อมูล
def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # สร้างตารางในฐานข้อมูลหากยังไม่มี
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS metrics (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ssid TEXT,
            bssid TEXT,
            signal_strength INTEGER,
            frequency TEXT,
            channel TEXT
        )
    ''')

    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS network_metrics (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            download_speed REAL,
            upload_speed REAL,
            latency REAL,
            packet_loss REAL,
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            device_count INTEGER,
            ssid TEXT
        )
    ''')

    conn.commit()
    conn.close()

# ฟังก์ชันบันทึกข้อมูลลงฐานข้อมูล
def save_metrics_to_db(ssid, bssid, signal_strength, frequency, channel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = get_local_time()  # ใช้เวลาท้องถิ่น

    # แทรกข้อมูลลงในตาราง
    cursor.execute(''' 
        INSERT INTO metrics (timestamp, ssid, bssid, signal_strength, frequency, channel) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, ssid, bssid, signal_strength, frequency, channel))

    conn.commit()
    conn.close()

# ฟังก์ชันบันทึกข้อมูล network metrics
def save_network_metrics_to_db(download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count, ssid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = get_local_time()  # ใช้เวลาท้องถิ่น

    cursor.execute(''' 
        INSERT INTO network_metrics (timestamp, download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count, ssid) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, download_speed, upload_speed, latency, packet_loss, bytes_sent, bytes_recv, device_count, ssid))

    conn.commit()
    conn.close()

# ฟังก์ชันลบข้อมูลที่เก่ากว่า 1 ชั่วโมง
def delete_old_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ลบข้อมูลที่มี timestamp เก่ากว่า 1 ชั่วโมง
    cursor.execute(''' 
        DELETE FROM metrics WHERE timestamp < datetime('now', '-24 hour')  
    ''')

    cursor.execute(''' 
        DELETE FROM network_metrics WHERE timestamp < datetime('now', '-24 hour')  
    ''')

    conn.commit()
    conn.close()

# ฟังก์ชันดึงข้อมูล Wi-Fi ทุกเครือข่าย
def get_wifi_networks_by_channel():
    result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], capture_output=True, text=True)
    networks = {}
    current_network = {}

    for line in result.stdout.split('\n'):
        if 'SSID' in line and 'BSSID' not in line:
            if current_network:  # Save the previous network
                channel = current_network.get('Channel', 'unknown')
                if channel not in networks:
                    networks[channel] = []
                networks[channel].append(current_network)
                current_network = {}
            current_network['SSID'] = line.split(':')[1].strip()
        elif 'BSSID' in line:
            current_network['BSSID'] = line.split(':')[1].strip()
        elif 'Signal' in line:
            current_network['Signal'] = int(line.split(':')[1].strip().replace('%', ''))
        elif 'Radio type' in line:
            current_network['Frequency'] = line.split(':')[1].strip()
        elif 'Channel' in line:
            current_network['Channel'] = line.split(':')[1].strip()

    if current_network:  # Add the last network  
        channel = current_network.get('Channel', 'unknown')
        if channel not in networks:
            networks[channel] = []
        networks[channel].append(current_network)

    return networks

# ฟังก์ชันเก็บข้อมูลจาก Wi-Fi เครือข่ายลงในฐานข้อมูล
def collect_and_save_wifi_networks():
    # ลบข้อมูลเก่ากว่า 1 ชั่วโมงก่อนที่จะบันทึกข้อมูลใหม่
    delete_old_data()

    wifi_by_channel = get_wifi_networks_by_channel()

    # บันทึกข้อมูลทุกช่องสัญญาณ
    for channel, networks in wifi_by_channel.items():
        for network in networks:
            ssid = network.get('SSID', 'unknown')
            bssid = network.get('BSSID', 'unknown')
            signal_strength = network.get('Signal', 0)
            frequency = network.get('Frequency', 'unknown')

            # บันทึกข้อมูลลงในฐานข้อมูล
            save_metrics_to_db(ssid, bssid, signal_strength, frequency, channel)
            print(f"SSID: {ssid} | BSSID: {bssid} | Signal: {signal_strength}% | Frequency: {frequency} | Channel: {channel}")

# Function to get current Wi-Fi information
def get_current_wifi_info():
    result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True)
    wifi_info = {}
    for line in result.stdout.split('\n'):
        if 'SSID' in line and 'BSSID' not in line:
            wifi_info['SSID'] = line.split(':')[1].strip()
        elif 'BSSID' in line:
            wifi_info['BSSID'] = line.split(':')[1].strip()
        elif 'Signal' in line:
            wifi_info['Signal'] = int(line.split(':')[1].strip().replace('%', ''))
        elif 'Radio type' in line:
            wifi_info['Frequency'] = line.split(':')[1].strip()
        elif 'Channel' in line:
            wifi_info['Channel'] = line.split(':')[1].strip()
    return wifi_info

# Function to measure throughput
def get_throughput():
    try:
        st = speedtest.Speedtest(secure=True)
        download_speed = st.download()
        upload_speed = st.upload()
        return download_speed, upload_speed
    except Exception as e:
        print(f"Error in throughput measurement: {e}")
        return 0, 0

# Function to measure latency
def get_latency(host='8.8.8.8'):
    try:
        return ping3.ping(host)
    except Exception as e:
        print(f"Error in latency measurement: {e}")
        return None

# Function to measure packet loss
def get_packet_loss(host='8.8.8.8', count=10):
    try:
        lost = 0
        for _ in range(count):
            if ping3.ping(host) is None:
                lost += 1
        return lost / count
    except Exception as e:
        print(f"Error in packet loss measurement: {e}")
        return 1

# Function to measure bandwidth utilization
def get_bandwidth_utilization():
    net_io = psutil.net_io_counters()
    return net_io.bytes_sent, net_io.bytes_recv

# Function to count devices on the network
def get_device_count():
    devices = set()

    def arp_display(pkt):
        if pkt[ARP].op == 1:  # who-has (request)
            devices.add(pkt[ARP].psrc)

    sniff(prn=arp_display, filter="arp", store=0, count=10, timeout=10)
    return len(devices)

# ฟังก์ชันตรวจจับ DDoS
def detect_ddos(download_speed, upload_speed, packet_loss, bytes_sent, bytes_recv, device_count):
    alerts = []

    # ตรวจสอบว่าค่ามีการเกิน threshold หรือไม่
    if download_speed > 50 * 1e6:
        alerts.append("ตรวจพบการโจมตี DDoS: ความเร็วการดาวน์โหลดสูงเกินไป")
    
    if upload_speed > 50 * 1e6:
        alerts.append("ตรวจพบการโจมตี DDoS: ความเร็วการอัปโหลดสูงเกินไป")
    
    if packet_loss > 0.5:
        alerts.append(f"ตรวจพบการโจมตี DDoS: การสูญเสียแพ็กเกจสูง ({packet_loss:.2%})")
    
    if bytes_sent > 100 * 1e6:
        alerts.append("ตรวจพบการโจมตี DDoS: ข้อมูลที่ส่งสูงเกินไป")
    
    if bytes_recv > 100 * 1e6:
        alerts.append("ตรวจพบการโจมตี DDoS: ข้อมูลที่รับสูงเกินไป")
    
    if device_count > 50:
        alerts.append("ตรวจพบการโจมตี DDoS: อุปกรณ์ในเครือข่ายมากเกินไป")

    return alerts

# Collect metrics and print information
def collect_metrics():
    wifi_info = get_current_wifi_info()
    ssid = wifi_info.get('SSID', 'unknown')  # ดึง SSID

    # Update current Wi-Fi signal strength
    if 'Signal' in wifi_info and 'Frequency' in wifi_info:
        signal_strength_gauge.labels(frequency=wifi_info['Frequency']).set(wifi_info['Signal'])
        print(f"SSID: {wifi_info.get('SSID', 'unknown')} | BSSID: {wifi_info.get('BSSID', 'unknown')} | Signal: {wifi_info.get('Signal')}% | Frequency: {wifi_info.get('Frequency')} | Channel: {wifi_info.get('Channel', 'unknown')}")

    # Update throughput
    download_speed, upload_speed = get_throughput()
    download_speed_gauge.set(download_speed)
    upload_speed_gauge.set(upload_speed)
    print(f"Download Speed: {download_speed / 1e6:.2f} Mbps")
    print(f"Upload Speed: {upload_speed / 1e6:.2f} Mbps")

    # Update latency
    latency = get_latency()
    if latency is not None:
        latency_gauge.set
