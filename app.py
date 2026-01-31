import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TopInvest Pro", layout="wide", page_icon="📈")

# --- 2. XỬ LÝ THƯ VIỆN (BẮT LỖI CHẶT CHẼ) ---
try:
    # Đây là lệnh chỉ chạy được trên bản vnstock 0.2.9
    from vnstock import stock_historical_data, price_board
except ImportError:
    st.error("⚠️ LỖI PHIÊN BẢN: Hệ thống đang chạy phiên bản mới không tương thích.")
    st.info("👉 Cách sửa: Vào GitHub > mở file requirements.txt > sửa thành: vnstock==0.2.9")
    st.stop()

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: white; }
    .card { background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #333; }
    .up { color: #00FF00; font-weight: bold; }
    .down { color: #FF0000; font-weight: bold; }
    .ref { color: #FFC107; font-weight: bold; }
    .big-price { font-size: 20px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Cấu hình")
    tickers = st.text_area("Danh sách mã:", "HPG, SSI, VND, DIG, PDR, FPT, MWG", height=150)
    btn_scan = st.button("🚀 QUÉT THỊ TRƯỜNG", type="primary")

# --- HÀM LẤY DỮ LIỆU ---
def get_data(symbols):
    try:
        return price_board(symbols)
    except Exception as e:
        return pd.DataFrame()

def get_robot_status(symbol):
    try:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        df = stock_historical_data(symbol, start, end, "1D", "stock")
        if df is None or len(df) < 10: return "N/A"
        ma20 = df['close'].tail(20).mean()
        price = df.iloc[-1]['close']
        return "MUA" if price > ma20 else "BÁN"
    except:
        return "---"

# --- MAIN APP ---
st.title("📈 BẢNG GIÁ & TÍN HIỆU (Bản Ổn Định)")

if btn_scan:
    symbol_list = [x.strip().upper() for x in tickers.split(',') if x.strip()]
    
    with st.spinner("Đang tải dữ liệu bản 0.2.9..."):
        df = get_data(",".join(symbol_list))
    
    if not df.empty:
        cols = st.columns(3)
        for i, row in df.iterrows():
            sym = row.get('Mã CP', '')
            price = row.get('Khớp lệnh', 0)
            change = row.get('+/-', 0)
            per = row.get('%', 0)
            
            # Màu sắc
            color = "up" if change > 0 else "down" if change < 0 else "ref"
            
            with cols[i % 3]:
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-size:22px; color:gold; font-weight:bold;">{sym}</span>
                        <span class="{color} big-price">{price}</span>
                    </div>
                    <div style="text-align:right;" class="{color}">
                        {change} ({per}%)
                    </div>
                    <hr style="border-color:#333; margin:5px 0;">
                    <div style="font-size:12px; color:#aaa;">
                        Vol: {row.get('Tổng KL', 0):,} | Robot: <b>{get_robot_status(sym)}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.error("Không lấy được dữ liệu. Hãy thử lại sau 1 phút.")
else:
    st.info("Bấm nút 'QUÉT THỊ TRƯỜNG' để bắt đầu.")


