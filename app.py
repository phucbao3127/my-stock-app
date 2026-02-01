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

# --- CSS ĐỂ GIỐNG GIAO DIỆN TRONG ẢNH ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    
    /* Header Bar giống TopInvest */
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
    
    /* Nút bấm Quét */
    .stButton>button {
        background-color: #f1c40f;
        color: #000;
        font-weight: bold;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        width: 100%;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #d4ac0d;
        color: white;
    }
    
    /* Tinh chỉnh bảng dữ liệu */
    div[data-testid="stDataFrame"] {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER GIẢ LẬP ---
st.markdown("""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div>
        <span>VN-INDEX: <span style="color:#00c087">1,250.50 (+0.5%)</span></span> &nbsp;|&nbsp; 
        <span>VN30: <span style="color:#00c087">1,280.10 (+0.8%)</span></span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU (REAL DATA) ---
@st.cache_data(ttl=300)
def fetch_stock_data(symbol):
    try:
        from vnstock3 import Vnstock
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date)
        
        # Fallback Yahoo nếu lỗi
        if df is None or df.empty:
             raise ValueError("Empty data")
             
        # Chuẩn hóa
        df = df.rename(columns={'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df
    except:
        # Fallback nhanh
        try:
            import yfinance as yf
            df = yf.download(f"{symbol}.VN", period="3mo", progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            return df
        except:
            return pd.DataFrame()

# --- 2. THUẬT TOÁN TÍNH TOÁN CÁC CỘT TRONG BẢNG ---
def analyze_stock(symbol, df):
    if df.empty or len(df) < 20: return None
    
    # Lấy dữ liệu phiên mới nhất
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Giá & Thay đổi
    price = curr['Close']
    change_pct = (price - prev['Close']) / prev['Close']
    volume = curr['Volume']
    
    # 2. Điểm cân bằng (Balance Point - VWAP 7 ngày)
    # Trong ảnh: Điểm cân bằng là số, nền xanh
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    balance = df['VP'].rolling(7).sum() / df['Volume'].rolling(7).sum()
    balance_val = balance.iloc[-1]
    
    # 3. ROBOT (Tín hiệu)
    # Logic: Giá > Balance => MUA/GIỮ. Giá < Balance => BÁN
    trend_days = 0
    signal = "NẮM GIỮ"
    
    # Tính T+ (Giả lập số ngày xu hướng duy trì)
    if price > balance_val:
        signal = "MUA" if (price - balance_val)/balance_val < 0.02 else "GIỮ 1/3" # Mới vượt thì Mua, vượt lâu thì Giữ
        trend_days = np.random.randint(0, 5) if signal == "MUA" else np.random.randint(5, 20)
    else:
        signal = "BÁN HẾT"
        trend_days = np.random.randint(0, 3)

    # 4. Target & Lãi/Lỗ
    # Giả định giá mua là giá cân bằng để tính Lãi/Lỗ tạm tính
    buy_price = balance_val 
    pnl = (price - buy_price) / buy_price
    
    target_1 = buy_price * 1.07
    target_2 = buy_price * 1.15
    
    # Format ngày mua
    buy_date = (datetime.now() - timedelta(days=trend_days)).strftime('%d/%m/%Y')
    
    return {
        "Mã CK": symbol,
        "Giá HT": price,
        "Thay đổi": change_pct,
        "Khối lượng": volume,
        "Điểm cân bằng": balance_val,
        "ROBOT": signal,
        "T+": f"T+{trend_days}",
        "Ngày mua": buy_date,
        "Target 1": target_1,
        "Target 2": target_2,
        "Lãi/Lỗ": pnl
    }

# --- 3. GIAO DIỆN CHÍNH ---

col_control, col_display = st.columns([1, 4])

# Danh sách quét (Để demo nhanh, dùng ~30 mã tiêu biểu, thực tế có thể load full sàn)
SCAN_LIST = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE',
    'DIG', 'DXG', 'CEO', 'PDR', 'NVL', 'DGC', 'DGW', 'FRT', 'FTS', 'VIX'
]

with col_control:
    st.header("Bộ lọc")
    st.write("Chọn nhóm ngành hoặc sàn để quét tín hiệu.")
    
    filter_group = st.selectbox("Nhóm cổ phiếu", ["VN30", "Bất Động Sản", "Ngân Hàng", "Chứng Khoán", "Tất cả"])
    
    st.info("Nhấn nút bên dưới để Robot rà soát toàn bộ thị trường và tìm điểm mua.")
    
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
        
        # Vòng lặp quét
        for i, symbol in enumerate(SCAN_LIST):
            status_text.text(f"Đang phân tích kỹ thuật: {symbol}...")
            progress_bar.progress((i + 1) / len(SCAN_LIST))
            
            # 1. Lấy dữ liệu
            df = fetch_stock_data(symbol)
            
            # 2. Phân tích
            res = analyze_stock(symbol, df)
            if res:
                results.append(res)
        
        progress_bar.empty()
        status_text.empty()
        
        # --- HIỂN THỊ KẾT QUẢ GIỐNG HÌNH ẢNH ---
        if results:
            df_res = pd.DataFrame(results)
            
            # Style bảng bằng Pandas Styler (Đây là chìa khóa để giống ảnh)
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
                                else f'background-color: white; color: black; border: 1px solid gray; font-weight: bold;'), subset=['ROBOT'])\
                .applymap(lambda v: 'background-color: #e8f5e9; color: #2e7d32; font-weight: bold; border: 1px solid #c8e6c9;', subset=['Điểm cân bằng'])

            st.subheader("📋 KẾT QUẢ KHUYẾN NGHỊ ĐẦU TƯ")
            
            # Hiển thị bảng
            st.dataframe(
                style_dataframe(df_res),
                use_container_width=True,
                height=800,
                column_config={
                    "Mã CK": st.column_config.TextColumn("Mã CK", help="Mã chứng khoán"),
                    "ROBOT": st.column_config.TextColumn("Tín hiệu", help="Khuyến nghị của AI"),
                }
            )
            
            st.success(f"Đã tìm thấy {len(df_res)} mã phù hợp tiêu chí!")
        else:
            st.warning("Không lấy được dữ liệu. Vui lòng thử lại.")
            
    else:
        st.info("👋 Chào mừng! Hãy nhấn nút 'RÀ SOÁT THỊ TRƯỜNG' bên trái để bắt đầu.")
        st.image("https://topinvest.vn/images/feature/feature-1.png", caption="Giao diện mô phỏng tính năng Robot")


