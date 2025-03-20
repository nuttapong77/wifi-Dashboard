import sqlite3
import dash
from dash import dcc, html
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import requests
from ddos_detection import *  # ฟังก์ชันตรวจจับ DDoS

# สร้างแอป Dash
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

# ฟังก์ชันดึงข้อมูล ISP
def get_isp_info():
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        return {
            "ip": data.get("ip", "N/A"),
            "isp": data.get("org", "N/A"),
            "city": data.get("city", "N/A"),
            "country": data.get("country", "N/A")
        }
    except Exception as e:
        return {"ip": "N/A", "isp": "N/A", "city": "N/A", "country": "N/A"}

# ฟังก์ชันดึงข้อมูลจาก SQLite
def get_data_from_db(ssid_filter=None):
    conn = sqlite3.connect('network_metrics.db')
    query = """
    SELECT timestamp, ssid, download_speed, upload_speed, latency, 
           packet_loss, bytes_sent, bytes_recv, device_count, bandwidth
    FROM network_metrics
    """
    if ssid_filter and ssid_filter != 'All':
        query += f" WHERE ssid = '{ssid_filter}'"
    query += " ORDER BY timestamp DESC LIMIT 10000"
    
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# ฟังก์ชันสร้างกราฟ
def create_graph(y_column, title, y_label, ssid_filter=None):
    df = get_data_from_db(ssid_filter)
    traces = []
    
    for ssid in df['ssid'].unique():
        ssid_data = df[df['ssid'] == ssid]
        trace = go.Scatter(
            x=ssid_data['timestamp'],
            y=ssid_data[y_column],
            mode='lines+markers',
            name=f'{title} - {ssid}'
        )
        traces.append(trace)
        
    layout = go.Layout(
        title=title,
        xaxis=dict(title='Timestamp'),
        yaxis=dict(title=y_label),
        template='plotly_dark'
    )
    return {'data': traces, 'layout': layout}

# ดึงข้อมูล ISP
isp_info = get_isp_info()

# Header แสดงข้อมูล ISP
header = dbc.Card(
    dbc.CardBody([ 
        html.H4("🌐 Network Information", className="card-title"),
        html.P(f"🆔 IP Address: {isp_info['ip']}"),
        html.P(f"🏢 ISP: {isp_info['isp']}"),
        html.P(f"📍 Location: {isp_info['city']}, {isp_info['country']}"),
    ]), 
    className="mb-3 text-light bg-dark"
)

# Sidebar Menu
sidebar = dbc.Card(
    [
        dbc.Button("☰ Toggle Menu", id="menu-button", color="primary", n_clicks=0, className="mb-3"),
        html.Div(
            id="sidebar-content",
            children=[
                html.H5("📡 Select SSID", className="text-light"),
                dcc.Dropdown(id='wifi-ssid-dropdown', multi=True, placeholder="เลือก SSID...", style={'color': 'black'}),
                html.Hr(),
                html.H5("📊 Select Data Type", className="text-light"),
                dcc.RadioItems(
                    id='data-type-radio',
                    options=[
                        {'label': 'Download Speed', 'value': 'download_speed'},
                        {'label': 'Upload Speed', 'value': 'upload_speed'},
                        {'label': 'Latency', 'value': 'latency'},
                        {'label': 'Packet Loss', 'value': 'packet_loss'},
                        {'label': 'Bandwidth Utilization', 'value': 'bandwidth'},
                        {'label': 'Device Count', 'value': 'device_count'}
                    ],
                    value='download_speed',
                    labelStyle={'display': 'block', 'color': 'white'}
                ),
                html.Hr(),
                html.H5("⚠️ Alert Thresholds", className="text-light"),
                dbc.Input(id="threshold-download", type="number", placeholder="Download Speed (Mbps)", className="mb-2"),
                dbc.Input(id="threshold-latency", type="number", placeholder="Latency (ms)", className="mb-2"),
                dbc.Input(id="threshold-packet-loss", type="number", placeholder="Packet Loss (%)"),
                dbc.Input(id="threshold-upload", type="number", placeholder="Upload Speed (Mbps)", className="mb-2"),
                dbc.Input(id="threshold-bandwidth", type="number", placeholder="Bandwidth Utilization (Mbps)", className="mb-2"),
                dbc.Input(id="threshold-device-count", type="number", placeholder="Device Count", className="mb-2"),
            ],
            style={"display": "none"}
        )
    ],
    body=True,
    color="dark",
    className="p-3 mb-4"
)

# Layout ของ Dash App
app.layout = dbc.Container([
    header,  # แสดงข้อมูล ISP ด้านบน
    dbc.Row([
        dbc.Col(sidebar, width=3),
        dbc.Col([
            html.H3("📶 Wi-Fi Performance Dashboard", className="text-center text-light mb-4"),
            dcc.Interval(id='interval-update', interval=10*1000, n_intervals=1),
            dbc.Alert(id='alert-message', color='danger', is_open=False, dismissable=True, className="mt-3"),
            dcc.Graph(id='wifi-graph', className="mt-3")
        ], width=9)
    ])
], fluid=True)

# Callback สำหรับอัปเดตตัวเลือก SSID
@app.callback(
    Output('wifi-ssid-dropdown', 'options'),
    Input('interval-update', 'n_intervals')
)
def update_ssid_options(n):
    conn = sqlite3.connect('network_metrics.db')
    ssids = pd.read_sql("SELECT DISTINCT ssid FROM network_metrics WHERE ssid IS NOT NULL", conn)['ssid'].dropna().tolist()
    conn.close()
    return [{'label': ssid, 'value': ssid} for ssid in ['All'] + ssids]

# Callback สำหรับอัปเดตกราฟและแจ้งเตือน
@app.callback(
    [Output('wifi-graph', 'figure'),
     Output('alert-message', 'children'),
     Output('alert-message', 'is_open')],
    [Input('wifi-ssid-dropdown', 'value'),
     Input('data-type-radio', 'value'),
     Input('interval-update', 'n_intervals')],
    [State('threshold-download', 'value'),
     State('threshold-latency', 'value'),
     State('threshold-packet-loss', 'value'),
     State('threshold-upload', 'value'),
     State('threshold-bandwidth', 'value'),
     State('threshold-device-count', 'value')]
)
def update_graph_and_alert(selected_ssids, data_type, n, threshold_download, threshold_latency, threshold_packet_loss,
                           threshold_upload, threshold_bandwidth, threshold_device_count):
    # กรองข้อมูลตาม SSID ที่เลือก
    df = get_data_from_db(selected_ssids)
    
    if df.empty:
        return {'data': [], 'layout': {}}, "", False
    
    alert_message = ""
    is_alert = False
    
    # ตรวจสอบเงื่อนไขที่กำหนด
    if threshold_download and df['download_speed'].min() < threshold_download:
        alert_message += f"⚠️ Download Speed ต่ำกว่า {threshold_download} Mbps!\n"
        is_alert = True

    if threshold_latency and df['latency'].max() > threshold_latency:
        alert_message += f"⚠️ Latency สูงกว่า {threshold_latency} ms!\n"
        is_alert = True

    if threshold_packet_loss and df['packet_loss'].max() > threshold_packet_loss:
        alert_message += f"⚠️ Packet Loss สูงกว่า {threshold_packet_loss}%!\n"
        is_alert = True

    if threshold_upload and df['upload_speed'].min() < threshold_upload:
        alert_message += f"⚠️ Upload Speed ต่ำกว่า {threshold_upload} Mbps!\n"
        is_alert = True

    if threshold_bandwidth and df['bandwidth'].max() < threshold_bandwidth:
        alert_message += f"⚠️ Bandwidth Utilization ต่ำกว่า {threshold_bandwidth} Mbps!\n"
        is_alert = True

    if threshold_device_count and df['device_count'].max() > threshold_device_count:
        alert_message += f"⚠️ จำนวนอุปกรณ์เชื่อมต่อมากกว่า {threshold_device_count}!\n"
        is_alert = True

    # สร้างกราฟตามประเภทข้อมูลที่เลือก
    figure = create_graph(data_type, f"{data_type} Over Time", data_type, selected_ssids)
    
    return figure, alert_message, is_alert

# Callback สำหรับแสดง/ซ่อน Sidebar
@app.callback(
    Output("sidebar-content", "style"),
    Input("menu-button", "n_clicks"),
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks):
    return {"display": "block" if n_clicks % 2 == 1 else "none"}

# เรียกใช้งานแอป
if __name__ == '__main__':
    app.run_server(debug=True)
