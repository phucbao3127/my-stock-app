import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="TopInvest Robot Scanner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    
    .header-bar {
        background-color: #333333;
        color: white;
        padding: 10px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #f1c40f;
        margin-bottom: 20px;
    }
    .logo { font-size: 24px; font-weight: bold; }
    .logo span { color: #f1c40f; }
    
    .stButton>button {
        background-color: #f1c40f; color: #000; font-weight: bold; border: none;
        padding: 10px 20px; border-radius: 5px; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #d4ac0d; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU ---

@st.cache_data(ttl=60) # Cache 1 phút cho Index
def get_market_index():
    """Lấy chỉ số VN-Index thực tế"""
    try:
        from vnstock3 import Vnstock
        # Lấy dữ liệu VNINDEX
        stock = Vnstock().stock(symbol='VNINDEX', source='VCI')
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        df = stock.quote.history(start=start_date, end=end_date)
        
        if df is not None and not df.empty:
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr['close']
            change = curr['close'] - prev['close']
            pct = (change / prev['close']) * 100
            return price, change, pct
    except:
        pass
    return 0, 0, 0

@st.cache_data(ttl=300)
def fetch_stock_data(symbol):
    try:
        from vnstock3 import Vnstock
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date)
        
        if df is None or df.empty: return pd.DataFrame()
             
        df = df.rename(columns={'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df
    except:
        return pd.DataFrame()

# --- HEADER ĐỘNG (REALTIME) ---
vn_price, vn_change, vn_pct = get_market_index()

# Định dạng màu sắc cho Index
vn_color = "#00c087" if vn_change >= 0 else "#ff3b30"
vn_sign = "+" if vn_change >= 0 else ""
vn_display = f"{vn_price:,.2f}" if vn_price > 0 else "Đang cập nhật..."
vn_change_display = f"{vn_sign}{vn_change:,.2f} ({vn_sign}{vn_pct:.2f}%)" if vn_price > 0 else ""

st.markdown(f"""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div>
        <span>VN-INDEX: <span style="color:{vn_color}; font-weight:bold">{vn_display}</span> 
        <span style="color:{vn_color}; font-size: 0.9em">{vn_change_display}</span></span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. THUẬT TOÁN TÍNH TOÁN ---
def analyze_stock(symbol, df):
    if df.empty or len(df) < 30: return None
    
    # Chỉ số kỹ thuật
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    df['Balance_Point'] = df['VP'].rolling(7).sum() / df['Volume'].rolling(7).sum()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    change_pct = (price - prev['Close']) / prev['Close']
    volume = curr['Volume']
    balance_val = curr['Balance_Point']
    
    # Logic Quét
    buy_date_str = "-"
    trend_days = 0
    entry_price = balance_val 
    signal = "QUAN SÁT"
    vol_status = "" 

    if price > balance_val:
        found_breakout = False
        closes = df['Close'].values
        balances = df['Balance_Point'].values
        volumes = df['Volume'].values
        vol_ma20s = df['Vol_MA20'].values
        dates = df.index
        
        for i in range(len(closes)-1, len(closes)-30, -1):
            is_price_break = closes[i] > balances[i] and closes[i-1] <= balances[i-1]
            
            if is_price_break:
                breakout_date = dates[i]
                buy_date_str = breakout_date.strftime('%d/%m/%Y')
                days_diff = (datetime.now() - breakout_date).days
                trend_days = days_diff
                entry_price = closes[i]
                
                if volumes[i] > vol_ma20s[i]:
                    vol_status = " (Vol Đột Biến)"
                else:
                    vol_status = "" 
                
                found_breakout = True
                break
        
        if found_breakout:
            if trend_days <= 3:
                if "Vol Đột Biến" in vol_status:
                    signal = "MUA"
                else:
                    signal = "MUA TÍCH LŨY" 
            else:
                signal = f"GIỮ 1/{3 if trend_days < 10 else 2}"
        else:
            signal = "NẮM GIỮ"
            buy_date_str = "> 1 tháng"
            trend_days = 30
    
    elif price < balance_val:
        signal = "BÁN HẾT"
        trend_days = 0
        buy_date_str = "-"

    pnl = 0
    if signal != "BÁN HẾT" and signal != "QUAN SÁT":
        pnl = (price - entry_price) / entry_price

    target_1 = entry_price * 1.07
    target_2 = entry_price * 1.15
    
    return {
        "Mã CK": symbol,
        "Giá HT": price,
        "Thay đổi": change_pct,
        "Khối lượng": volume,
        "Điểm cân bằng": balance_val,
        "ROBOT": signal,
        "T+": f"T+{trend_days}" if trend_days > 0 else "-",
        "Ngày mua": buy_date_str,
        "Target 1": target_1,
        "Target 2": target_2,
        "Lãi/Lỗ": pnl
    }

# --- 3. GIAO DIỆN CHÍNH ---

col_control, col_display = st.columns([1, 4])

SCAN_LIST = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE',
    'DIG', 'DXG', 'CEO', 'PDR', 'NVL', 'DGC', 'DGW', 'FRT', 'FTS', 'VIX'
]

with col_control:
    st.header("Bộ lọc TopInvest")
    st.write("Robot lọc điểm Mua theo tiêu chuẩn:")
    st.markdown("- Giá cắt lên **Điểm Cân Bằng**")
    st.markdown("- Ưu tiên **Nổ Volume** (>TB 20 phiên)")
    
    if st.button("🚀 RÀ SOÁT THỊ TRƯỜNG", type="primary"):
        st.session_state['scanning'] = True
    else:
        if 'scanning' not in st.session_state:
            st.session_state['scanning'] = False

with col_display:
    if st.session_state['scanning']:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, symbol in enumerate(SCAN_LIST):
            status_text.text(f"Đang phân tích dòng tiền: {symbol}...")
            progress_bar.progress((i + 1) / len(SCAN_LIST))
            
            df = fetch_stock_data(symbol)
            res = analyze_stock(symbol, df)
            if res:
                results.append(res)
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            
            def style_dataframe(df):
                return df.style.format({
                    "Giá HT": "{:,.0f}",
                    "Thay đổi": "{:+.2%}",
                    "Khối lượng": "{:,.0f}",
                    "Điểm cân bằng": "{:,.0f}",
                    "Target 1": "{:,.0f}",
                    "Target 2": "{:,.0f}",
                    "Lãi/Lỗ": "{:+.2%}"
                }).applymap(lambda x: 'color: #00c087; font-weight: bold' if x > 0 else ('color: #ff3b30; font-weight: bold' if x < 0 else 'color: gray'), subset=['Thay đổi', 'Lãi/Lỗ'])\
                .applymap(lambda v: f'background-color: #00c087; color: white; font-weight: bold; padding: 5px; border-radius: 4px;' if v == 'MUA' 
                          else (f'background-color: #ff3b30; color: white; font-weight: bold; padding: 5px; border-radius: 4px;' if v == 'BÁN HẾT' 
                                else (f'background-color: #2196f3; color: white; font-weight: bold; padding: 5px; border-radius: 4px;' if v == 'MUA TÍCH LŨY'
                                else f'background-color: white; color: black; border: 1px solid gray; font-weight: bold;')), subset=['ROBOT'])\
                .applymap(lambda v: 'background-color: #e8f5e9; color: #2e7d32; font-weight: bold; border: 1px solid #c8e6c9;', subset=['Điểm cân bằng'])

            st.subheader("📋 BẢNG TÍN HIỆU (REALTIME)")
            st.dataframe(
                style_dataframe(df_res),
                use_container_width=True,
                height=800,
                column_config={
                    "Ngày mua": st.column_config.TextColumn("Ngày mua", help="Ngày Breakout kèm Volume"),
                }
            )
            st.success(f"Hoàn tất quét {len(df_res)} mã.")
        else:
            st.warning("Không có dữ liệu.")
            
    else:
        st.info("Nhấn nút RÀ SOÁT để Robot tìm điểm Mua chuẩn xác.")
