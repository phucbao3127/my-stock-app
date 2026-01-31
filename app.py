import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# --- XỬ LÝ KẾT NỐI CHO BẢN VNSTOCK MỚI (v3.x) ---
try:
    # Bản mới dùng hàm 'quote' thay vì 'price_board'
    from vnstock import stock_historical_data, quote
except ImportError:
    st.error("Lỗi thư viện: Vui lòng Reboot App để cập nhật.")
    st.stop()

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="TopInvest 2026 (New Core)",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GIAO DIỆN (CSS) ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .stock-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #444;
        margin-bottom: 10px;
    }
    .price-up { color: #00FF00; font-size: 24px; font-weight: bold; }
    .price-down { color: #FF4500; font-size: 24px; font-weight: bold; }
    .price-ref { color: #FFC107; font-size: 24px; font-weight: bold; }
    .small-text { font-size: 12px; color: #888; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Cấu hình (Core v3)")
    default_tickers = "HPG, SSI, VND, DIG, CEO, FPT, MWG, TCB"
    user_tickers = st.text_area("Mã cổ phiếu:", default_tickers, height=150)
    auto_refresh = st.checkbox("Tự động làm mới (30s)", value=False)

# --- HÀM XỬ LÝ DỮ LIỆU ---
def get_live_data_v3(symbols_list):
    """Hàm lấy giá cho Vnstock bản mới nhất"""
    try:
        # Chuyển list thành chuỗi "HPG,SSI"
        symbols_str = ",".join(symbols_list)
        # Hàm quote mới trả về DataFrame với tên cột tiếng Anh
        df = quote(symbols_str)
        return df
    except Exception as e:
        st.error(f"Không lấy được dữ liệu: {e}")
        return pd.DataFrame()

def get_robot_signal(symbol):
    try:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        df = stock_historical_data(symbol, start, end, "1D", "stock")
        
        if df is None or df.empty: return "Chờ dữ liệu..."
        
        # Tính MA20
        ma20 = df['close'].tail(20).mean()
        last_price = df.iloc[-1]['close']
        
        if last_price > ma20: return "🟢 MUA / NẮM GIỮ"
        else: return "🔴 CÂN NHẮC BÁN"
    except:
        return "⚪ N/A"

# --- MAIN APP ---
st.title("🚀 TOPINVEST - NEXT GEN CORE")
st.caption(f"Sử dụng thư viện Vnstock mới nhất | Cập nhật: {datetime.now().strftime('%H:%M:%S')}")

tickers = [x.strip().upper() for x in user_tickers.split(',') if x.strip()]

if st.button("🔄 QUÉT THỊ TRƯỜNG") or auto_refresh:
    
    with st.spinner("Đang kết nối Server v3..."):
        df = get_live_data_v3(tickers)
    
    if not df.empty:
        # Mapping tên cột từ bản mới sang tên hiển thị
        # Bản mới thường trả về: stockSymbol, lastPrice, change, changePercent, totalVol
        
        cols = st.columns(3)
        for index, row in df.iterrows():
            # Xử lý an toàn các tên cột (vì bản mới hay đổi tên cột)
            sym = row.get('symbol', row.get('stockSymbol', 'N/A'))
            
            # Giá và thay đổi
            price = row.get('price', row.get('lastPrice', 0)) * 1000 # Có thể cần nhân 1000 tùy nguồn
            if price < 1000: price *= 1000 # Fix lỗi hiển thị nếu đơn vị là nghìn
                
            change = row.get('change', 0)
            pct = row.get('percent', row.get('changePercent', 0)) * 100
            if abs(pct) > 20: pct /= 100 # Fix lỗi nếu API trả về số thập phân
            
            vol = row.get('volume', row.get('totalVol', 0))
            
            # Robot
            signal = get_robot_signal(sym)
            
            # Màu sắc
            color_class = "price-up" if change > 0 else "price-down" if change < 0 else "price-ref"
            
            with cols[index % 3]:
                st.markdown(f"""
                <div class="stock-card">
                    <div style="display:flex; justify-content:space-between;">
                        <h2 style="color:white; margin:0;">{sym}</h2>
                        <span class="{color_class}">{price:,.0f}</span>
                    </div>
                    <div style="text-align:right; font-weight:bold; color:{'#0f0' if change>0 else '#f00'};">
                        {change:,.0f} ({pct:.2f}%)
                    </div>
                    <hr style="border-color:#555;">
                    <div style="display:flex; justify-content:space-between;" class="small-text">
                        <span>Vol: {vol:,.0f}</span>
                        <span>Robot: <b>{signal}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
    else:
        st.warning("Chưa có dữ liệu trả về. Hãy kiểm tra lại danh sách mã.")

    if auto_refresh:
        time.sleep(30)
        st.rerun()


