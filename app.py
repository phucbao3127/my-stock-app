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
    
    /* Custom Table Styling */
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM LẤY DỮ LIỆU SIÊU ỔN ĐỊNH (Yahoo Finance Priority) ---

@st.cache_data(ttl=60)
def get_market_index():
    """Lấy VN-Index: Ưu tiên Yahoo vì không bị chặn IP Cloud"""
    # 1. Thử Yahoo Finance (Nhanh & Ổn định quốc tế)
    try:
        import yfinance as yf
        # Mã VN-Index trên Yahoo là ^VNINDEX
        ticker = yf.Ticker("^VNINDEX")
        hist = ticker.history(period="5d")
        if not hist.empty:
            curr = hist.iloc[-1]
            prev = hist.iloc[-2]
            return curr['Close'], curr['Close'] - prev['Close'], (curr['Close'] - prev['Close']) / prev['Close'] * 100
    except Exception as e:
        # print(f"Yahoo Index Error: {e}")
        pass
        
    # 2. Fallback sang Vnstock nếu Yahoo lỗi
    try:
        from vnstock3 import Vnstock
        stock = Vnstock().stock(symbol='VNINDEX', source='TCBS')
        df = stock.quote.history(start=(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'), end=datetime.now().strftime('%Y-%m-%d'))
        if df is not None and not df.empty:
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            return curr['close'], curr['close'] - prev['close'], (curr['close'] - prev['close']) / prev['close'] * 100
    except:
        pass
    
    return 0, 0, 0

@st.cache_data(ttl=300)
def fetch_stock_data(symbol):
    """
    Hàm lấy dữ liệu thông minh:
    - Ưu tiên 1: Yahoo Finance (yfinance) -> Chạy tốt trên Streamlit Cloud, không bị chặn.
    - Ưu tiên 2: Vnstock (TCBS/VCI) -> Dữ liệu chi tiết nhưng hay bị chặn IP nước ngoài.
    """
    
    # --- KÊNH 1: YAHOO FINANCE (ƯU TIÊN CHO CLOUD) ---
    try:
        import yfinance as yf
        # Yahoo quy ước mã VN có đuôi .VN
        symbol_yahoo = f"{symbol}.VN"
        
        # Lấy 6 tháng để đủ tính toán
        df = yf.download(symbol_yahoo, period="6mo", progress=False)
        
        if df is not None and not df.empty and len(df) > 20:
            # Xử lý MultiIndex của Yahoo phiên bản mới
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Đảm bảo index là datetime
            df.index = pd.to_datetime(df.index)
            
            # Yahoo đã có sẵn cột chuẩn: Open, High, Low, Close, Volume
            # Cần đảm bảo không có dòng nào Volume = 0 quá nhiều
            return df
    except Exception:
        pass

    # --- KÊNH 2: VNSTOCK (DỰ PHÒNG) ---
    try:
        from vnstock3 import Vnstock
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        stock = Vnstock().stock(symbol=symbol, source='TCBS') 
        df = stock.quote.history(start=start_date, end=end_date)
        
        if df is not None and not df.empty and len(df) > 20:
            df = df.rename(columns={'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df
    except Exception:
        pass

    return pd.DataFrame()

# --- HEADER REALTIME ---
vn_price, vn_change, vn_pct = get_market_index()
vn_color = "#00c087" if vn_change >= 0 else "#ff3b30"
vn_sign = "+" if vn_change >= 0 else ""
vn_display = f"{vn_price:,.2f}" if vn_price > 0 else "Đang kết nối..."
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

# --- 2. THUẬT TOÁN PHÂN TÍCH (ROBUST) ---
def analyze_stock(symbol, df):
    # Data Validation cực mạnh để tránh crash
    if df.empty or len(df) < 20: return None
    
    # Ép kiểu và xử lý NaN
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    
    df = df.dropna(subset=['Close', 'Volume'])
    if len(df) < 20: return None

    # Tính toán chỉ số
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    
    # Điểm cân bằng: Fallback về MA7 nếu Volume bị lỗi
    try:
        df['Balance_Point'] = df['VP'].rolling(7).sum() / df['Volume'].rolling(7).sum()
    except:
        df['Balance_Point'] = df['Close'].rolling(7).mean()

    # Xử lý Balance Point NaN ở đầu chu kỳ
    df['Balance_Point'] = df['Balance_Point'].fillna(df['Close'])

    # MA20 Volume
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # Lấy dữ liệu hiện tại
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    change_pct = (price - prev['Close']) / prev['Close']
    volume = curr['Volume']
    balance_val = curr['Balance_Point']
    
    # --- LOGIC QUÉT NGÀY MUA ---
    buy_date_str = "-"
    trend_days = 0
    entry_price = balance_val 
    signal = "QUAN SÁT"
    vol_status = "" 

    # Logic: Giá > Balance Point là xu hướng Tăng
    if price > balance_val:
        found_breakout = False
        
        # Chuyển về numpy array để chạy nhanh hơn
        closes = df['Close'].values
        balances = df['Balance_Point'].values
        volumes = df['Volume'].values
        vol_ma20s = df['Vol_MA20'].values
        dates = df.index
        
        # Quét ngược tối đa 40 phiên
        lookback = min(40, len(closes)-1)
        
        for i in range(len(closes)-1, len(closes)-lookback, -1):
            # Điều kiện Breakout: Cắt lên đường vàng
            if closes[i] > balances[i] and closes[i-1] <= balances[i-1]:
                breakout_date = dates[i]
                buy_date_str = breakout_date.strftime('%d/%m/%Y')
                trend_days = (datetime.now() - breakout_date).days
                entry_price = closes[i]
                
                # Check Volume tại điểm nổ
                v_curr = volumes[i]
                v_ma = vol_ma20s[i]
                
                # Logic mềm dẻo hơn: Nếu Volume > 90% MA20 cũng chấp nhận (để bắt được nhiều mã hơn)
                if not np.isnan(v_ma) and v_curr > (v_ma * 0.9):
                    vol_status = " (Vol Đột Biến)"
                
                found_breakout = True
                break
        
        if found_breakout:
            if trend_days <= 5: # Mở rộng T+ lên 5 ngày để bắt tín hiệu
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

    # Tính Lãi/Lỗ
    pnl = 0
    if signal not in ["BÁN HẾT", "QUAN SÁT"]:
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

# Danh sách quét mở rộng (Những mã thanh khoản cao dễ lấy dữ liệu)
SCAN_LIST = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE',
    'DIG', 'DXG', 'CEO', 'PDR', 'NVL', 'DGC', 'DGW', 'FRT', 'FTS', 'VIX',
    'KBC', 'KDH', 'LPB', 'MSB', 'OCB', 'PNJ', 'REE', 'SHS', 'VND'
]

with col_control:
    st.header("Bộ lọc TopInvest")
    st.info("Trạng thái: Đã chuyển sang chế độ dữ liệu Quốc tế (Yahoo) để tránh nghẽn mạng.")
    
    st.write("Tiêu chuẩn Robot:")
    st.markdown("- Giá cắt lên **Điểm Cân Bằng**")
    st.markdown("- Ưu tiên **Nổ Volume**")
    
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
        
        success_count = 0
        fail_count = 0
        
        for i, symbol in enumerate(SCAN_LIST):
            status_text.text(f"Robot đang quét: {symbol}...")
            progress_bar.progress((i + 1) / len(SCAN_LIST))
            
            # Không cần sleep khi dùng Yahoo vì nó chịu tải tốt hơn
            df = fetch_stock_data(symbol)
            
            if not df.empty:
                res = analyze_stock(symbol, df)
                if res:
                    results.append(res)
                    success_count += 1
            else:
                fail_count += 1
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            
            # Styling bảng dữ liệu
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

            st.subheader("📋 KẾT QUẢ KHUYẾN NGHỊ")
            if fail_count > 0:
                st.caption(f"Quét thành công: {success_count} mã. Không lấy được dữ liệu: {fail_count} mã (Do mạng).")
            
            st.dataframe(
                style_dataframe(df_res),
                use_container_width=True,
                height=800,
                column_config={
                    "Ngày mua": st.column_config.TextColumn("Ngày mua", help="Ngày Breakout kèm Volume"),
                }
            )
            st.success("Hoàn tất rà soát.")
        else:
            st.error("Không có dữ liệu nào được tải về. Vui lòng thử lại sau ít phút.")
            
    else:
        st.info("Nhấn nút RÀ SOÁT để bắt đầu.")
