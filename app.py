import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="TopInvest Robot Scanner (Live)",
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
    .live-indicator {
        display: inline-block;
        width: 10px; height: 10px;
        background-color: #2ecc71;
        border-radius: 50%;
        margin-right: 5px;
        animation: blink 1s infinite;
    }
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    
    /* Bảng dữ liệu */
    div[data-testid="stDataFrame"] { width: 100%; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU THỰC TẾ (REALTIME) ---

@st.cache_data(ttl=10) 
def get_market_index():
    """Lấy chỉ số VN-Index Realtime"""
    try:
        import yfinance as yf
        # Lấy khung 1 phút để có giá chính xác nhất tại thời điểm hiện tại
        tick = yf.Ticker("^VNINDEX")
        # period='5d' để chắc chắn có dữ liệu dù là cuối tuần
        hist = tick.history(period="5d", interval="1m")
        
        if not hist.empty:
            curr = hist.iloc[-1]
            # Lấy giá đóng cửa phiên trước đó để tính tham chiếu
            # Dùng ngày hôm trước
            prev_day = hist[hist.index.date < curr.name.date()]
            if not prev_day.empty:
                prev_close = prev_day.iloc[-1]['Close']
            else:
                prev_close = curr['Open'] # Fallback
            
            price = curr['Close']
            change = price - prev_close
            pct = (change / prev_close) * 100
            return price, change, pct
    except:
        pass
    return 0.0, 0.0, 0.0

@st.cache_data(ttl=10)
def fetch_stock_data_final(symbol):
    """
    Kết hợp nguồn dữ liệu để lấy giá mới nhất từ sàn.
    """
    # 1. Yahoo Finance (Nhanh & Ổn định trên Cloud)
    try:
        import yfinance as yf
        # period='1y' là đủ để tính toán các chỉ số
        df = yf.download(f"{symbol}.VN", period="1y", progress=False)
        
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.rename(columns={'Date':'Date','Open':'Open','High':'High','Low':'Low','Close':'Close','Volume':'Volume'})
            # Đảm bảo index là datetime
            df.index = pd.to_datetime(df.index)
            df = df.dropna()
            return df
    except:
        pass
    
    # 2. Vnstock - TCBS (Dự phòng)
    try:
        from vnstock3 import Vnstock
        # Lấy dư thêm 1 ngày ở tương lai để đảm bảo bao trùm hết hôm nay (do múi giờ server)
        end = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        
        stock = Vnstock().stock(symbol=symbol, source='TCBS')
        df = stock.quote.history(start=start, end=end)
        
        if df is not None and not df.empty:
            df = df.rename(columns={'time':'Date','open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df
    except:
        pass
    
    return pd.DataFrame()

# --- HEADER ---
vn_p, vn_c, vn_pct = get_market_index()
# Nếu không lấy được VN-Index (do lỗi mạng), hiển thị trạng thái chờ
if vn_p == 0.0:
    vn_display = "Đang kết nối..."
    vn_color = "#bdc3c7"
else:
    vn_display = f"{vn_p:,.2f}"
    vn_color = "#27ae60" if vn_c >= 0 else "#c0392b"

vn_sym = "+" if vn_c >= 0 else ""
# Lấy giờ hệ thống hiện tại
now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

st.markdown(f"""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div>
        <span class="live-indicator"></span>CẬP NHẬT: {now_str} | 
        VN-INDEX: <span style="color:{vn_color}; font-weight:bold">{vn_display}</span>
        <span style="font-size:0.9em; color:{vn_color}">{vn_sym}{vn_c:,.2f} ({vn_sym}{vn_pct:.2f}%)</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. CÔNG THỨC CHUẨN TOPINVEST ---
def analyze_stock_final(symbol, df):
    if df.empty or len(df) < 25: return None
    
    # Ép kiểu số
    cols = ['Open','High','Low','Close','Volume']
    for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
    
    # --- CÔNG THỨC ĐIỂM CÂN BẰNG (VWAP 20) ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    df['Balance_Point'] = df['VP'].rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # Dữ liệu hiện tại (Phiên mới nhất)
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    balance = curr['Balance_Point']
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
        for i in range(len(closes)-1, len(closes)-40, -1):
            if closes[i] > balances[i] and closes[i-1] <= balances[i-1]:
                breakout_date = dates[i]
                # Format ngày mua
                buy_date_str = breakout_date.strftime('%d/%m')
                t_plus = (datetime.now() - breakout_date).days
                entry_price = closes[i]
                found = True
                break
        
        if found:
            pnl = (price - entry_price) / entry_price
            
            # Trạng thái
            if t_plus <= 1: robot_signal = "MUA"
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

    # Lấy ngày của dữ liệu cuối cùng để kiểm chứng
    data_date = curr.name.strftime('%d/%m')

    return {
        "Mã CK": symbol,
        "Giá": price,
        "%": change_pct,
        "Vol": curr['Volume'],
        "Cân bằng": balance,
        "ROBOT": robot_signal,
        "T+": f"T+{t_plus}" if robot_signal != "BÁN HẾT" else "-",
        "Ngày mua": buy_date_str,
        "Target 1": target_1,
        "Target 2": target_2,
        "Lãi/Lỗ": pnl_display,
        "Thời gian": data_date # Cột kiểm chứng dữ liệu mới
    }

# --- 3. GIAO DIỆN ---
col1, col2 = st.columns([1, 4])

SCAN_LIST = [
    'AGR', 'ASM', 'BHI', 'CII', 'FRT', 'FTS', 'KBC', 'MBB', 'MSB', 'NLG', 'NVL', 
    'SCR', 'TCB', 'VGC', 'VID', 'HPG', 'ANV', 'DBC', 'DC1', 'DCM', 'DDV', 'DGC',
    'DGW', 'DIG', 'DPG', 'DTD', 'FPT', 'GVR', 'HDB', 'HDG', 'LPB', 'MWG', 'PDR'
]

with col1:
    st.info("Hệ thống kết nối trực tiếp với API chứng khoán (Yahoo/TCBS) để lấy dữ liệu giao dịch mới nhất.")
    
    # Nút cập nhật cưỡng bức
    if st.button("🔄 CẬP NHẬT DỮ LIỆU MỚI"):
        st.cache_data.clear() # Xóa cache cũ
        st.session_state['scanning'] = True
        st.rerun() # Chạy lại trang

    if st.button("🚀 RÀ SOÁT ROBOT"):
        st.session_state['scanning'] = True

with col2:
    if st.session_state.get('scanning'):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(SCAN_LIST):
            status.text(f"Đang tải dữ liệu mới nhất: {sym}...")
            bar.progress((i+1)/len(SCAN_LIST))
            
            df = fetch_stock_data_final(sym)
            res = analyze_stock_final(sym, df)
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
            st.success(f"Dữ liệu được lấy thành công từ thị trường. Tìm thấy {len(results)} mã.")
        else:
            st.error("Không thể kết nối đến máy chủ dữ liệu. Vui lòng thử lại sau.")
