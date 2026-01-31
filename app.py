import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CẤU HÌNH ---
st.set_page_config(page_title="TopInvest Classic", layout="wide", page_icon="📉")

# --- 1. KIỂM TRA THƯ VIỆN NGHIÊM NGẶT ---
try:
    from vnstock import price_board, stock_historical_data
except ImportError:
    st.error("❌ LỖI CÀI ĐẶT: Máy chủ chưa nhận phiên bản 0.2.9.")
    st.info("Hãy Reboot App để hệ thống tải lại file requirements.txt")
    st.stop()

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: white; }
    .card { 
        background-color: #1E1E1E; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        border: 1px solid #333; 
    }
    .price { font-size: 24px; font-weight: bold; }
    .up { color: #00FF00; }
    .down { color: #FF4500; }
    .ref { color: #FFC107; }
</style>
""", unsafe_allow_html=True)

st.title("📉 BẢNG GIÁ CHUẨN (VNSTOCK 0.2.9)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Danh mục")
    default_tickers = "HPG,SSI,VND,DIG,CEO,FPT,MWG,TCB,STB,PDR"
    user_input = st.text_area("Nhập mã:", default_tickers, height=150)
    
    if st.button("QUÉT DỮ LIỆU"):
        st.rerun()

# --- HÀM XỬ LÝ DỮ LIỆU (CHỈ DÙNG CODE 0.2.9) ---
def get_classic_data(symbols_str):
    try:
        # Lệnh price_board chỉ có ở bản 0.2.9
        df = price_board(symbols_str)
        return df
    except Exception as e:
        return pd.DataFrame()

def get_robot_029(symbol):
    try:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        # Lệnh stock_historical_data chuẩn
        df = stock_historical_data(symbol, start, end, "1D", "stock")
        if df is None or len(df) < 5: return "N/A"
        
        # Logic Robot
        ma20 = df['close'].tail(20).mean()
        price = df.iloc[-1]['close']
        return "MUA" if price > ma20 else "BÁN"
    except:
        return "---"

# --- CHẠY CHƯƠNG TRÌNH ---
# Xử lý chuỗi mã chứng khoán
tickers = [x.strip().upper() for x in user_input.split(',') if x.strip()]
symbols_str = ",".join(tickers)

if tickers:
    with st.spinner("Đang tải dữ liệu từ Vnstock 0.2.9..."):
        df = get_classic_data(symbols_str)

    if not df.empty:
        # Kiểm tra xem có đúng tên cột tiếng Việt của bản cũ không
        # Bản 0.2.9 trả về: "Mã CP", "Khớp lệnh", "+/-", "%", "Tổng KL"
        if 'Khớp lệnh' not in df.columns:
            st.error("⚠️ CẢNH BÁO: Dữ liệu trả về không đúng định dạng bản 0.2.9!")
            st.dataframe(df) # Hiện dữ liệu thô để debug
        else:
            cols = st.columns(3)
            for i, row in df.iterrows():
                try:
                    sym = row['Mã CP']
                    price = row['Khớp lệnh']
                    change = row['+/-']
                    pct = row['%']
                    vol = row['Tổng KL']
                    
                    # Robot
                    signal = get_robot_029(sym)
                    
                    color = "up" if change > 0 else "down" if change < 0 else "ref"
                    
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div class="card">
                            <div style="display:flex; justify-content:space-between;">
                                <h3 style="margin:0; color:gold;">{sym}</h3>
                                <span class="price {color}">{price}</span>
                            </div>
                            <div style="text-align:right; font-weight:bold;" class="{color}">
                                {change} ({pct}%)
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:12px; color:#aaa;">
                                <span>Vol: {vol:,}</span>
                                <span>Robot: <b>{signal}</b></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                except:
                    continue
    else:
        st.warning("Không có dữ liệu. (Lưu ý: Bản 0.2.9 cũ có thể nguồn dữ liệu gốc đã thay đổi API).")

else:
    st.info("Nhập mã cổ phiếu để bắt đầu.")





