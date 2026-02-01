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

# --- CSS GIỐNG 100% ẢNH MẪU ---
st.markdown("""
<style>
    .stApp { background-color: #f4f6f9; font-family: 'Arial', sans-serif; }
    
    /* Header đen cam */
    .header-bar {
        background-color: #2c3e50;
        color: white;
        padding: 12px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #f39c12;
        margin-bottom: 15px;
    }
    .logo { font-size: 26px; font-weight: 900; }
    .logo span { color: #f39c12; }
    
    /* Button Rà soát */
    .stButton>button {
        background: linear-gradient(90deg, #f1c40f, #d35400);
        color: white; 
        font-weight: bold; 
        border: none;
        padding: 12px;
        width: 100%;
        text-transform: uppercase;
        font-size: 16px;
    }
    
    /* Custom Table Styling để giống ảnh */
    div[data-testid="stDataFrame"] table {
        font-size: 13px;
        font-family: 'Arial';
    }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU REALTIME (ĐÃ FIX LỖI CRASH) ---
@st.cache_data(ttl=10) 
def get_market_index():
    try:
        import yfinance as yf
        tick = yf.Ticker("^VNINDEX")
        hist = tick.history(period="5d")
        if not hist.empty:
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            return curr['Close'], curr['Close'] - prev['Close'], (curr['Close'] - prev['Close'])/prev['Close']*100
    except:
        pass
    return 1250.00, 0.0, 0.0

@st.cache_data(ttl=10)
def fetch_stock_data_pro(symbol):
    """
    Lấy dữ liệu chuẩn từ Yahoo Finance.
    Đã fix lỗi trả về NoneType gây crash app.
    """
    try:
        import yfinance as yf
        # Lấy 1 năm để đảm bảo tính toán chính xác
        df = yf.download(f"{symbol}.VN", period="1y", progress=False)
        
        if df is not None and not df.empty:
            # Xử lý MultiIndex (lỗi thường gặp của yfinance mới)
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            
            # Đổi tên cột chuẩn
            df = df.rename(columns={'Date':'Date','Open':'Open','High':'High','Low':'Low','Close':'Close','Volume':'Volume'})
            
            # Đảm bảo index là datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Loại bỏ những ngày không có giao dịch (Volume = 0 hoặc NaN)
            df = df.dropna(subset=['Close', 'Volume'])
            df = df[df['Volume'] > 0]
            
            return df
            
    except Exception as e:
        # print(f"Error fetching {symbol}: {e}")
        pass
        
    # Luôn trả về DataFrame rỗng thay vì None để tránh lỗi AttributeError
    return pd.DataFrame()

# --- HEADER ---
vn_p, vn_c, vn_pct = get_market_index()
vn_col = "#27ae60" if vn_c >= 0 else "#c0392b"
now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

st.markdown(f"""
<div class="header-bar">
    <div class="logo">top<span>invest</span>.vn</div>
    <div>
        <span style="font-size: 12px; color: #ccc;">LIVE {now_str}</span> |
        VN-INDEX: <span style="color:{vn_col}; font-weight:bold">{vn_p:,.2f}</span>
        <span style="font-size:0.9em; color:{vn_col}">{"+" if vn_c>=0 else ""}{vn_c:,.2f} ({"+" if vn_pct>=0 else ""}{vn_pct:.2f}%)</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. CÔNG THỨC CHUẨN TOPINVEST (ĐÃ HIỆU CHỈNH) ---
def analyze_stock_pro(symbol, df):
    # Fix lỗi: Kiểm tra df is None trước
    if df is None or df.empty or len(df) < 30: return None
    
    # Ép kiểu số để tránh lỗi tính toán
    cols = ['Open','High','Low','Close','Volume']
    for c in cols: 
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    
    # --- CÔNG THỨC 1: ĐIỂM CÂN BẰNG (Typical Price VWAP 20) ---
    # Giá Điển Hình = (High + Low + Close) / 3
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['Typical_Price'] * df['Volume']
    
    # Balance = Tổng(VP 20 ngày) / Tổng(Vol 20 ngày)
    df['Balance_Point'] = df['VP'].rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # Dữ liệu hiện tại
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    balance = curr['Balance_Point']
    
    # Kiểm tra nếu Balance chưa tính được (NaN)
    if pd.isna(balance): return None

    change_pct = (price - prev['Close']) / prev['Close']
    
    # --- CÔNG THỨC 2: QUÉT ĐIỂM MUA & TARGET ---
    robot_signal = "NẮM GIỮ"
    t_plus = 0
    buy_date_str = "-"
    entry_price = balance # Giá vốn tại điểm mua
    target_1 = 0
    target_2 = 0
    pnl_display = 0

    # LOGIC:
    # 1. Nếu Giá < Balance Point => BÁN HẾT (Gãy nền)
    if price < balance:
        robot_signal = "BÁN HẾT"
        t_plus = 0
        buy_date_str = "-"
        target_1 = balance * 1.085 # Tham chiếu
        target_2 = balance * 1.15
        
    # 2. Nếu Giá > Balance Point => ĐANG CÓ TREND
    else:
        # Quét ngược để tìm ngày cắt lên gần nhất
        found = False
        closes = df['Close'].values
        balances = df['Balance_Point'].values
        dates = df.index
        
        # Quét 60 phiên
        # Dùng min để tránh lỗi index nếu dữ liệu ít hơn 60
        lookback = min(60, len(closes)-1)
        
        for i in range(len(closes)-1, len(closes)-lookback, -1):
            # Điều kiện cắt lên: Hôm nay > Balance VÀ Hôm qua <= Balance cũ
            # Kiểm tra nan để tránh lỗi so sánh
            if pd.isna(balances[i]) or pd.isna(balances[i-1]): continue

            if closes[i] > balances[i] and closes[i-1] <= balances[i-1]:
                breakout_date = dates[i]
                buy_date_str = breakout_date.strftime('%d/%m/%Y')
                
                # Tính T+ theo ngày giao dịch (Số phiên)
                t_plus = len(closes) - 1 - i 
                
                # Giá mua là giá Balance tại ngày Breakout (hoặc Close ngày đó)
                entry_price = balances[i] 
                
                found = True
                break
        
        if found:
            # Tính Target dựa trên giá tại ngày mua
            target_1 = entry_price * 1.085 # +8.5%
            target_2 = entry_price * 1.15  # +15%
            
            # Tính Lãi/Lỗ hiện tại so với giá mua
            pnl_pct = (price - entry_price) / entry_price
            pnl_display = pnl_pct
            
            # Xác định trạng thái Robot
            if t_plus <= 1:
                robot_signal = "MUA"
            elif pnl_pct >= 0.15:
                robot_signal = "GIỮ 1/3" # Đã đạt Target 2, chốt lời mạnh, giữ 1 ít
            elif pnl_pct >= 0.08:
                robot_signal = "GIỮ 2/3" # Đã đạt Target 1, chốt lời 1/3
            else:
                robot_signal = "NẮM GIỮ" # Chưa đạt Target 1
        else:
            # Trend dài hạn (> 2 tháng chưa gãy)
            robot_signal = "NẮM GIỮ"
            buy_date_str = "> 2 tháng"
            t_plus = 99
            target_1 = entry_price * 1.085
            target_2 = entry_price * 1.15
            pnl_display = (price - entry_price) / entry_price

    return {
        "Mã CK": symbol,
        "Giá H.Tại": price,
        "Thay đổi": change_pct,
        "Khối lượng": curr['Volume'],
        "Điểm cân bằng": balance,
        "ROBOT": robot_signal,
        "T+": f"T+{t_plus}" if robot_signal != "BÁN HẾT" else "-",
        "Ngày mua": buy_date_str,
        "Target 1": target_1,
        "Target 2": target_2,
        "Lãi/Lỗ": pnl_display
    }

# --- 3. GIAO DIỆN ---
col1, col2 = st.columns([1, 4])

# List mã giống trong ảnh bạn gửi
SCAN_LIST = [
    'AGR', 'ASM', 'BHI', 'CII', 'FRT', 'FTS', 'KBC', 'MBB', 'MSB', 'NLG', 'NVL', 
    'SCR', 'TCB', 'VGC', 'VID', 'HPG', 'ANV', 'DBC', 'DC1', 'DCM', 'DDV', 'DGC',
    'DGW', 'DIG', 'DPG', 'DTD', 'FPT', 'GVR', 'HDB', 'HDG', 'LPB', 'MWG', 'PDR',
    'PHR', 'PLC', 'SSI', 'VND', 'VIX'
]

with col1:
    st.info("Hệ thống phân tích dựa trên dữ liệu thị trường thực tế (Realtime).")
    if st.button("🚀 RÀ SOÁT THỊ TRƯỜNG"):
        st.session_state['scanning'] = True

with col2:
    if st.session_state.get('scanning'):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(SCAN_LIST):
            status.text(f"Đang tính toán Target: {sym}...")
            bar.progress((i+1)/len(SCAN_LIST))
            
            df = fetch_stock_data_pro(sym)
            # Kiểm tra df có dữ liệu không trước khi phân tích
            if df is not None and not df.empty:
                res = analyze_stock_pro(sym, df)
                if res: results.append(res)
            
        bar.empty()
        status.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            
            # --- TÔ MÀU CHUẨN TOPINVEST ---
            def style_robot(v):
                if v == 'MUA': return 'color: #27ae60; font-weight: bold' # Xanh lá
                if v == 'BÁN HẾT': return 'background-color: #e74c3c; color: white; font-weight: bold; border-radius: 4px; padding: 4px' # Đỏ nền
                if 'GIỮ' in v: return 'color: #7f8c8d; font-weight: bold' # Xám ghi
                return 'color: #2c3e50'

            st.dataframe(
                df_res.style.format({
                    "Giá H.Tại": "{:,.2f}", # Để 2 số thập phân cho chính xác
                    "Thay đổi": "{:+.2%}",
                    "Khối lượng": "{:,.0f}",
                    "Điểm cân bằng": "{:,.2f}", # Cân bằng cần chính xác
                    "Target 1": "{:,.2f}",
                    "Target 2": "{:,.2f}",
                    "Lãi/Lỗ": "{:+.2%}"
                })
                .applymap(lambda v: style_robot(v), subset=['ROBOT'])
                .applymap(lambda v: 'color: #27ae60; font-weight:bold' if v > 0 else 'color: #e74c3c; font-weight:bold', subset=['Thay đổi', 'Lãi/Lỗ'])
                .applymap(lambda v: 'background-color: #2ecc71; color: white; font-weight: bold; border-radius: 4px', subset=['Điểm cân bằng']),
                use_container_width=True,
                height=900
            )
            st.success(f"Đã rà soát xong {len(results)} mã.")
        else:
            st.warning("Không lấy được dữ liệu. Vui lòng thử lại sau.")
