import sqlite3
import dash
from dash import dcc, html
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import requests
from ddos_detection import *

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
           packet_loss, bytes_sent, bytes_recv, device_count
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

# ฟังก์ชันสร้างตารางบันทึกการแจ้งเตือนในฐานข้อมูล
def create_alerts_table():
    conn = sqlite3.connect('network_metrics.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        alert_message TEXT
    )
    """)
    conn.commit()
    conn.close()

create_alerts_table()

# ฟังก์ชันบันทึกการแจ้งเตือน
def log_alert(alert_message):
    conn = sqlite3.connect('network_metrics.db')
    cursor = conn.cursor()
    timestamp = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO alerts (timestamp, alert_message) VALUES (?, ?)", (timestamp, alert_message))
    conn.commit()
    conn.close()

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
                dcc.Dropdown(id='wifi-ssid-dropdown', multi=True, placeholder="Select SSID...", style={'color': 'black'}),
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
                dbc.Input(id="threshold-bandwidth", type="number", placeholder="Bandwidth Utilization (%)"),
                dbc.Input(id="threshold-device-count", type="number", placeholder="Device Count", className="mb-2"),
            ],
            style={"display": "none"}
        )
    ],
    body=True,
    color="dark",
    className="p-3 mb-4"
)

# ปุ่มสำหรับดูประวัติการแจ้งเตือน
history_button = dbc.Button("📜 View Alert History", id="view-alert-history", color="info", className="mb-3")

# โครงสร้าง Modal สำหรับแสดงประวัติการแจ้งเตือน
alert_history_modal = dbc.Modal(
    [
        dbc.ModalHeader("⚠️ Alert History"),
        dbc.ModalBody(id="alert-history-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-modal", className="ml-auto", color="secondary")
        ),
    ],
    id="alert-history-modal",
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
            history_button,  # ปุ่มดูประวัติ
            alert_history_modal,  # Modal สำหรับแสดงประวัติ
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
     State('threshold-packet-loss', 'value')]
)
def update_graph_and_alert(selected_ssids, data_type, n, threshold_download, threshold_latency, threshold_packet_loss):
    df = get_data_from_db(selected_ssids)
    
    alert_message = ""
    is_alert = False
    
    if not df.empty:
        if threshold_download and df['download_speed'].min() < threshold_download:
            alert_message += f"⚠️  Download Speed lower than {threshold_download} Mbps!\n"
            is_alert = True
        if threshold_latency and df['latency'].max() > threshold_latency:
            alert_message += f"⚠️ Latency more than {threshold_latency} ms!\n"
            is_alert = True
        if threshold_packet_loss and df['packet_loss'].max() > threshold_packet_loss:
            alert_message += f"⚠️ Packet Loss more than {threshold_packet_loss}%!\n"
            is_alert = True
        
        # บันทึกการแจ้งเตือน
        if is_alert and alert_message:
            log_alert(alert_message)
    
    figure = create_graph(data_type, f"{data_type} Over Time", data_type, selected_ssids)
    return figure, alert_message, is_alert

# Callback สำหรับแสดงประวัติการแจ้งเตือน
@app.callback(
    Output("alert-history-body", "children"),
    Input("view-alert-history", "n_clicks"),
    prevent_initial_call=True
)
def show_alert_history(n_clicks):
    conn = sqlite3.connect('network_metrics.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "No alerts found."
    
    alert_list = []
    for row in rows:
        alert_list.append(html.Div([
            html.P(f"Timestamp: {row[1]}", className="font-weight-bold"),
            html.P(f"Message: {row[2]}"),
            html.Hr()
        ]))
    
    return alert_list

# Callback สำหรับเปิด/ปิด modal
@app.callback(
    Output("alert-history-modal", "is_open"),
    Input("view-alert-history", "n_clicks"),
    Input("close-modal", "n_clicks"),
    State("alert-history-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

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

