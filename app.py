import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time
import requests

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="TopInvest Robot Scanner (DNSE Data)",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS CHUẨN GIAO DIỆN TOPINVEST ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f5; font-family: 'Helvetica', sans-serif; }
    
    /* Header */
    .header-bar {
        background-color: #2c3e50;
        color: white;
        padding: 10px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #f39c12;
        margin-bottom: 15px;
    }
    .logo { font-size: 24px; font-weight: 900; }
    .logo span { color: #f39c12; }
    
    /* Nút bấm */
    .stButton>button {
        background: linear-gradient(90deg, #f39c12, #d35400);
        color: white;
        font-weight: bold;
        border: none;
        padding: 10px 25px;
        border-radius: 5px;
        width: 100%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #d35400, #f39c12);
        color: white;
    }
    
    /* Live Indicator */
    .live-dot {
        height: 10px; width: 10px; background-color: #2ecc71;
        border-radius: 50%; display: inline-block;
        box-shadow: 0 0 5px #2ecc71;
    }
    
    /* Bảng dữ liệu */
    div[data-testid="stDataFrame"] { width: 100%; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU TỪ DNSE (ENTRADE X) - SIÊU NHANH ---

@st.cache_data(ttl=10)
def get_dnse_data(symbol):
    """
    Lấy dữ liệu nến lịch sử từ API của DNSE.
    Nguồn này cực nhanh và Realtime.
    """
    try:
        # Tính timestamp cho API (Lấy 1 năm)
        to_ts = int(time.time())
        from_ts = int((datetime.now() - timedelta(days=365)).timestamp())
        
        url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1D&from={from_ts}&to={to_ts}"
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 't' in data and len(data['t']) > 0:
                df = pd.DataFrame({
                    'Date': pd.to_datetime(data['t'], unit='s') + timedelta(hours=7), # UTC -> UTC+7
                    'Open': data['o'],
                    'High': data['h'],
                    'Low': data['l'],
                    'Close': data['c'],
                    'Volume': data['v']
                })
                df.set_index('Date', inplace=True)
                
                # Ép kiểu số
                cols = ['Open','High','Low','Close','Volume']
                for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                return df
    except Exception as e:
        # print(f"Lỗi DNSE {symbol}: {e}")
        pass
    return pd.DataFrame()

@st.cache_data(ttl=10)
def get_market_index_dnse():
    # Lấy VNINDEX
    df = get_dnse_data("VNINDEX")
    if not df.empty:
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        return curr['Close'], curr['Close'] - prev['Close'], (curr['Close'] - prev['Close'])/prev['Close']*100
    return 1250.00, 0.0, 0.0

# --- HEADER ---
vn_p, vn_c, vn_pct = get_market_index_dnse()
vn_col = "#27ae60" if vn_c >= 0 else "#c0392b"
vn_sym = "+" if vn_c >= 0 else ""
now_str = datetime.now().strftime("%H:%M:%S")

st.markdown(f"""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div>
        <span class="live-dot"></span> <span style="font-size: 12px; color: #ccc;">LIVE DATA {now_str}</span> |
        VN-INDEX: <span style="color:{vn_col}; font-weight:bold">{vn_p:,.2f}</span>
        <span style="font-size:0.9em; color:{vn_col}">{vn_sym}{vn_c:,.2f} ({vn_sym}{vn_pct:.2f}%)</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. CÔNG THỨC CHUẨN TOPINVEST ---
def analyze_stock_dnse(symbol, df):
    if df.empty or len(df) < 25: return None
    
    # --- CÔNG THỨC ĐIỂM CÂN BẰNG (VWAP 20) ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    df['Balance_Point'] = df['VP'].rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # Dữ liệu hiện tại
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    balance = curr['Balance_Point']
    
    # Nếu chưa có Balance (do mới niêm yết), lấy MA20
    if pd.isna(balance): balance = df['Close'].rolling(20).mean().iloc[-1]
    
    change_pct = (price - prev['Close']) / prev['Close']
    
    # --- LOGIC ROBOT ---
    robot_signal = "NẮM GIỮ"
    t_plus = 0
    buy_date_str = "-"
    entry_price = balance 
    
    # 1. Logic Gãy Trend (Cắt lỗ)
    if price < balance:
        robot_signal = "BÁN HẾT"
        t_plus = 0
        buy_date_str = "-"
        
    # 2. Logic Uptrend
    else:
        # Tìm ngày Breakout
        found = False
        closes = df['Close'].values
        balances = df['Balance_Point'].values
        dates = df.index
        
        # Quét 40 phiên
        scan_limit = min(40, len(closes)-1)
        for i in range(len(closes)-1, len(closes)-scan_limit, -1):
            if closes[i] > balances[i] and closes[i-1] <= balances[i-1]:
                breakout_date = dates[i]
                buy_date_str = breakout_date.strftime('%d/%m')
                t_plus = (datetime.now() - breakout_date).days
                entry_price = closes[i]
                found = True
                break
        
        if found:
            pnl = (price - entry_price) / entry_price
            
            # Trạng thái
            if t_plus <= 2: robot_signal = "MUA"
            elif pnl > 0.15: robot_signal = "GIỮ 1/3"
            elif pnl > 0.08: robot_signal = "GIỮ 2/3"
            else: robot_signal = "NẮM GIỮ"
        else:
            robot_signal = "NẮM GIỮ"
            t_plus = 99
            buy_date_str = ">2T"
            
    pnl_display = 0
    if robot_signal != "BÁN HẾT":
        pnl_display = (price - entry_price) / entry_price
        
    target_1 = entry_price * 1.07
    target_2 = entry_price * 1.15

    # Định dạng ngày dữ liệu
    data_date = curr.name.strftime('%d/%m')

    return {
        "Mã CK": symbol,
        "Giá": price*1000 if price < 500 else price, # Fix đơn vị nếu DNSE trả về nghìn đồng
        "%": change_pct,
        "Vol": curr['Volume'],
        "Cân bằng": balance*1000 if balance < 500 else balance,
        "ROBOT": robot_signal,
        "T+": f"T+{t_plus}" if robot_signal != "BÁN HẾT" else "-",
        "Ngày mua": buy_date_str,
        "Target 1": (target_1*1000 if target_1 < 500 else target_1),
        "Target 2": (target_2*1000 if target_2 < 500 else target_2),
        "Lãi/Lỗ": pnl_display,
        "Date": data_date
    }

# --- 3. GIAO DIỆN ---
col1, col2 = st.columns([1, 4])

# Danh sách mã quét
SCAN_LIST = [
    'AGR', 'ASM', 'BHI', 'CII', 'FRT', 'FTS', 'KBC', 'MBB', 'MSB', 'NLG', 'NVL', 
    'SCR', 'TCB', 'VGC', 'VID', 'HPG', 'ANV', 'DBC', 'DC1', 'DCM', 'DDV', 'DGC',
    'DGW', 'DIG', 'DPG', 'DTD', 'FPT', 'GVR', 'HDB', 'HDG', 'LPB', 'MWG', 'PDR'
]

with col1:
    st.info("Nguồn dữ liệu: **DNSE (Entrade X)**. Tốc độ cao & Realtime.")
    
    if st.button("🔄 CẬP NHẬT DỮ LIỆU"):
        st.cache_data.clear()
        st.rerun()

    if st.button("🚀 RÀ SOÁT ROBOT"):
        st.session_state['scanning'] = True

with col2:
    if st.session_state.get('scanning'):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(SCAN_LIST):
            status.text(f"Đang tải từ DNSE: {sym}...")
            bar.progress((i+1)/len(SCAN_LIST))
            
            # Hàm mới dùng DNSE
            df = get_dnse_data(sym)
            res = analyze_stock_dnse(sym, df)
            if res: results.append(res)
            
        bar.empty()
        status.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            
            # --- STYLING ---
            def style_robot(v):
                if v == 'MUA': return 'color: #27ae60; font-weight: bold' 
                if v == 'BÁN HẾT': return 'background-color: #e74c3c; color: white; font-weight: bold; border-radius: 4px; padding: 2px 5px'
                if 'GIỮ' in v: return 'color: #7f8c8d; font-weight: bold'
                return 'color: #2c3e50'

            st.dataframe(
                df_res.style.format({
                    "Giá": "{:,.0f}",
                    "%": "{:+.2%}",
                    "Vol": "{:,.0f}",
                    "Cân bằng": "{:,.0f}",
                    "Target 1": "{:,.0f}",
                    "Target 2": "{:,.0f}",
                    "Lãi/Lỗ": "{:+.2%}"
                })
                .applymap(lambda v: style_robot(v), subset=['ROBOT'])
                .applymap(lambda v: 'color: #27ae60' if v > 0 else 'color: #e74c3c', subset=['%', 'Lãi/Lỗ'])
                .applymap(lambda v: 'background-color: #2ecc71; color: white; font-weight: bold; border-radius: 4px', subset=['Cân bằng']),
                use_container_width=True,
                height=900
            )
            st.success(f"Quét xong {len(results)} mã từ nguồn DNSE.")
        else:
            st.error("Không kết nối được API DNSE.")
