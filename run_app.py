import threading
import subprocess

# ฟังก์ชันเพื่อรัน metrics_collector.py
def run_metrics_collector():
    subprocess.run(["python", "d:/Project192/wifi-analyzer/metrics_collector.py"])

# ฟังก์ชันเพื่อรัน app.py
def run_dash_app():
    subprocess.run(["python", "d:/Project192/wifi-analyzer/app.py"])


 

# เริ่มทั้งสองฟังก์ชันใน thread แยก
if __name__ == "__main__":
    collector_thread = threading.Thread(target=run_metrics_collector)
    dash_thread = threading.Thread(target=run_dash_app)

    collector_thread.start()
    dash_thread.start()

    collector_thread.join()
    dash_thread.join()
