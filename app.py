import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="TopInvest Pro Simulator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS GIỐNG 100% ẢNH TOPINVEST ---
st.markdown("""
<style>
    /* Reset nền */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    /* Header Bar Đen - Cam */
    .header-bar {
        background-color: #2b2b2b;
        color: white;
        padding: 15px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid #d35400;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .logo { font-size: 28px; font-weight: 900; letter-spacing: 1px; }
    .logo span { color: #f39c12; } /* Màu cam TopInvest */
    
    /* Nút Rà soát */
    .stButton>button {
        background: linear-gradient(to bottom, #f39c12, #d35400);
        color: white;
        font-weight: bold;
        border: none;
        padding: 12px 25px;
        border-radius: 4px;
        width: 100%;
        text-transform: uppercase;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stButton>button:hover {
        background: linear-gradient(to bottom, #e67e22, #ba4a00);
    }
    
    /* Bảng dữ liệu */
    div[data-testid="stDataFrame"] { width: 100%; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# --- 1. MODULE DỮ LIỆU "BẤT TỬ" (YAHOO FINANCE FIX) ---
# Sử dụng yfinance làm nguồn chính vì nó ổn định nhất trên Cloud

@st.cache_data(ttl=60)
def get_real_market_index():
    """Lấy VN-Index Realtime từ Yahoo"""
    try:
        import yfinance as yf
        # Yahoo dùng ^VNINDEX
        ticker = yf.Ticker("^VNINDEX")
        # Lấy dữ liệu ngắn nhất có thể để nhanh
        hist = ticker.history(period="5d")
        
        if not hist.empty:
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            price = curr['Close']
            change = price - prev['Close']
            pct = (change / prev['Close']) * 100
            return price, change, pct
    except Exception as e:
        pass
    return 1250.50, 0.0, 0.0 # Fallback hiển thị nếu mất mạng

@st.cache_data(ttl=300)
def fetch_stock_data_pro(symbol):
    """
    Lấy dữ liệu lịch sử chuẩn để tính toán.
    Tự động fix lỗi MultiIndex của Yahoo Finance mới.
    """
    try:
        import yfinance as yf
        symbol_yahoo = f"{symbol}.VN"
        
        # Lấy 6 tháng dữ liệu
        df = yf.download(symbol_yahoo, period="6mo", progress=False)
        
        if df is None or df.empty: return pd.DataFrame()
        
        # FIX LỖI YAHOO MỚI (QUAN TRỌNG)
        # Yahoo mới trả về cột dạng ('Close', 'HPG.VN') -> Cần làm phẳng
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Đổi tên cột về chuẩn
        df = df.rename(columns={
            'Date': 'Date', 'Open': 'Open', 'High': 'High', 
            'Low': 'Low', 'Close': 'Close', 'Volume': 'Volume'
        })
        
        # Ép kiểu số
        cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
        df = df.dropna()
        return df
    except:
        return pd.DataFrame()

# --- HEADER REALTIME ---
vn_p, vn_c, vn_pct = get_real_market_index()
color_idx = "#2ecc71" if vn_c >= 0 else "#e74c3c"
sign_idx = "+" if vn_c >= 0 else ""

st.markdown(f"""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div style="text-align: right;">
        <div style="font-size: 12px; opacity: 0.8; color: #ccc">THỊ TRƯỜNG CHỨNG KHOÁN</div>
        <div style="font-size: 18px; font-weight: bold;">
            VN-INDEX: <span style="color:{color_idx}">{vn_p:,.2f}</span> 
            <span style="font-size: 14px; color:{color_idx}"> {sign_idx}{vn_c:,.2f} ({sign_idx}{vn_pct:.2f}%)</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. THUẬT TOÁN TOPINVEST CORE (ĐÃ FIX LOGIC) ---
def analyze_stock_pro(symbol, df):
    if df.empty or len(df) < 25: return None
    
    # --- CÔNG THỨC 1: ĐIỂM CÂN BẰNG (SHARK COST) ---
    # TopInvest dùng VWAP 20 phiên (Tương đương 1 tháng giao dịch - Bollinger Band Middle)
    # Đây là đường hỗ trợ cứng uy tín hơn 7 ngày.
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    
    # Tính VWAP 20 ngày
    df['Balance_Point'] = df['VP'].rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # Fallback: Nếu lỗi chia 0 thì dùng SMA 20
    df['Balance_Point'] = df['Balance_Point'].fillna(df['Close'].rolling(20).mean())
    
    # --- CÔNG THỨC 2: TÍNH TOÁN TRẠNG THÁI ---
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    change_pct = (price - prev['Close']) / prev['Close']
    volume = curr['Volume']
    balance = curr['Balance_Point']
    
    # Logic xác định Ngày Mua & T+
    buy_date_str = ""
    t_plus = 0
    entry_price = balance
    
    # ROBOT LOGIC (Mô phỏng 4 trạng thái trong ảnh)
    robot_signal = "NẮM GIỮ" # Mặc định
    
    # 1. Nếu Giá < Điểm cân bằng -> BÁN HẾT (Gãy trend)
    if price < balance:
        robot_signal = "BÁN HẾT"
        t_plus = 0
        buy_date_str = "-"
    
    # 2. Nếu Giá > Điểm cân bằng -> ĐANG UPTREND
    else:
        # Quét ngược để tìm ngày Breakout (Ngày cắt lên)
        found = False
        closes = df['Close'].values
        balances = df['Balance_Point'].values
        dates = df.index
        
        # Quét 60 phiên gần nhất
        for i in range(len(closes)-1, len(closes)-60, -1):
            if closes[i] > balances[i] and closes[i-1] <= balances[i-1]:
                # Tìm thấy ngày mua
                breakout_date = dates[i]
                buy_date_str = breakout_date.strftime('%d/%m/%Y')
                t_plus = (datetime.now() - breakout_date).days # Tính số ngày nắm giữ
                entry_price = closes[i]
                found = True
                break
        
        if found:
            # Tính Lãi/Lỗ hiện tại
            pnl_pct = (price - entry_price) / entry_price
            
            # LOGIC CHỐT LỜI TỰ ĐỘNG (Giống ảnh: GIỮ 1/3, GIỮ 2/3)
            if t_plus <= 3:
                robot_signal = "MUA" # Mới mua
            elif pnl_pct > 0.15: # Lãi > 15%
                robot_signal = "GIỮ 1/3" # Chốt lời bớt
            elif pnl_pct > 0.07: # Lãi > 7%
                robot_signal = "GIỮ 2/3"
            else:
                robot_signal = "NẮM GIỮ" # Lãi nhẹ hoặc hòa vốn
        else:
            # Uptrend dài hạn (trên 60 ngày)
            robot_signal = "NẮM GIỮ"
            t_plus = 99
            buy_date_str = "> 2 tháng"

    # Tính PnL
    pnl_val = 0
    if robot_signal != "BÁN HẾT":
        pnl_val = (price - entry_price) / entry_price

    # Target
    target_1 = entry_price * 1.07 # 7%
    target_2 = entry_price * 1.15 # 15%

    return {
        "Mã CK": symbol,
        "Giá H.Tại": price,
        "Thay đổi": change_pct,
        "Khối lượng": volume,
        "Điểm cân bằng": balance,
        "ROBOT": robot_signal,
        "T+": f"T+{t_plus}" if robot_signal != "BÁN HẾT" else "-",
        "Ngày mua": buy_date_str,
        "Target 1": target_1,
        "Target 2": target_2,
        "Lãi/Lỗ": pnl_val
    }

# --- 3. GIAO DIỆN CHÍNH ---

col1, col2 = st.columns([1, 4])

# Danh sách mã Hot để quét (Đa dạng ngành để ra nhiều màu)
SCAN_LIST = [
    'HPG', 'SSI', 'VND', 'DIG', 'CEO', 'NVL', 'PDR', 'DXG', # BĐS - Thép
    'STB', 'MBB', 'ACB', 'TCB', 'VPB', 'SHB', # Bank
    'FPT', 'MWG', 'DGC', 'VHC', 'ANV', 'DBC', # Bán lẻ - SX
    'VIX', 'FTS', 'BSI', 'CTS', 'AGR' # Chứng khoán nhỏ (Hay trần)
]

with col1:
    st.subheader("BỘ LỌC ROBOT")
    st.info("""
    **Tiêu chí TopInvest Pro:**
    1. Giá > Điểm Cân Bằng (VWAP 20)
    2. Báo **BÁN HẾT** khi gãy nền.
    3. Báo **GIỮ 1/3, 2/3** khi đạt Target.
    """)
    
    if st.button("🚀 RÀ SOÁT THỊ TRƯỜNG"):
        st.session_state['scanning'] = True

with col2:
    if st.session_state.get('scanning'):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        # Quét từng mã
        for i, sym in enumerate(SCAN_LIST):
            status.text(f"Đang phân tích kỹ thuật: {sym}...")
            progress.progress((i+1)/len(SCAN_LIST))
            
            # Không sleep để chạy nhanh hơn (Yahoo chịu tải tốt)
            df = fetch_stock_data_pro(sym)
            res = analyze_stock_pro(sym, df)
            if res:
                results.append(res)
        
        progress.empty()
        status.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            
            # --- STYLING GIỐNG HỆT ẢNH ---
            def highlight_robot(val):
                if val == 'MUA':
                    return 'background-color: #27ae60; color: white; font-weight: bold; padding: 5px; border-radius: 4px;' # Xanh lá đậm
                elif val == 'BÁN HẾT':
                    return 'background-color: #c0392b; color: white; font-weight: bold; padding: 5px; border-radius: 4px;' # Đỏ đậm
                elif 'GIỮ' in val:
                    return 'background-color: #ffffff; color: #2c3e50; font-weight: bold; border: 1px solid #bdc3c7;' # Trắng viền xám
                return ''

            def highlight_change(val):
                color = '#27ae60' if val > 0 else ('#c0392b' if val < 0 else '#7f8c8d')
                return f'color: {color}; font-weight: bold'

            # Áp dụng Style
            st.dataframe(
                df_res.style
                .format({
                    "Giá H.Tại": "{:,.0f}",
                    "Thay đổi": "{:+.2%}",
                    "Khối lượng": "{:,.0f}",
                    "Điểm cân bằng": "{:,.0f}",
                    "Target 1": "{:,.0f}",
                    "Target 2": "{:,.0f}",
                    "Lãi/Lỗ": "{:+.2%}"
                })
                .applymap(highlight_robot, subset=['ROBOT'])
                .applymap(highlight_change, subset=['Thay đổi', 'Lãi/Lỗ'])
                .applymap(lambda x: 'background-color: #d5f5e3; color: #1e8449; font-weight: bold', subset=['Điểm cân bằng']), # Xanh nhạt cho cột Balance
                use_container_width=True,
                height=800
            )
            st.success(f"Đã cập nhật dữ liệu mới nhất. Tìm thấy {len(df_res)} mã.")
        else:
            st.error("Lỗi kết nối máy chủ dữ liệu. Vui lòng thử lại.")
    else:
        st.write("👈 Bấm nút bên trái để chạy Robot.")
