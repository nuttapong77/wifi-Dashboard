import os
import datetime

def log_system_restart():
    log_file = "system_log.txt"
    if os.path.exists(log_file):
        with open(log_file, "r") as file:
            last_entry = file.readlines()[-1].strip()
        
        if "Shutdown Detected" in last_entry:
            print("⚠️ Detected unexpected shutdown! Sending alert...")
            send_email_alert("System restarted after unexpected shutdown")
    
    with open(log_file, "a") as file:
        file.write(f"{datetime.datetime.now()} - System Started\n")

def send_email_alert(message):
    # เพิ่มฟังก์ชันส่งอีเมลแจ้งเตือน
    print(f"📩 Sending email alert: {message}")

# เรียกใช้งานเมื่อระบบเริ่มต้น
log_system_restart()
