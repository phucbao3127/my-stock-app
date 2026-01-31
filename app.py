import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, price_board
from datetime import datetime, timedelta
import time

# --- 1. CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Hệ Thống Tự Doanh Pro",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. GIAO DIỆN (CSS DARK MODE) ---
st.markdown("""
<style>
    /* Nền tối chuyên nghiệp */
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    
    /* Thẻ chứa thông tin cổ phiếu */
    .stock-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Màu sắc tín hiệu */
    .text-up { color: #00FF00; font-weight: bold; }
    .text-down { color: #FF0000; font-weight: bold; }
    .text-ref { color: #FFC107; font-weight: bold; }
    
    /* Bảng sổ lệnh mini */
    .order-book { width: 100%; font-size: 13px; margin-top: 10px; border-collapse: collapse; }
    .order-book td { padding: 4px; border-bottom: 1px solid #333; }
    .bid-side { color: #00FF00; text-align: right; }
    .ask-side { color: #FF4500; text-align: left; }
    .header-row { font-size: 11px; color: #888; text-align: center; }
    
    /* Nút bấm */
    div.stButton > button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. THANH ĐIỀU KHIỂN (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Cấu hình")
    # Danh sách mặc định
    default_tickers = "HPG, SSI, VND, DIG, CEO, PDR, STB, MWG, DGC, FPT, ACB, MBB"
    user_tickers = st.text_area("Danh sách mã (cách nhau dấu phẩy):", default_tickers, height=200)
    
    auto_refresh = st.checkbox("Tự động làm mới (30s)", value=False)
    st.info("Dữ liệu được lấy trực tiếp từ bảng giá thị trường (Realtime).")

# --- 4. HÀM XỬ LÝ DỮ LIỆU ---
def get_market_data(symbols):
    """Lấy dữ liệu bảng giá trực tuyến"""
    try:
        # symbols là chuỗi dạng "HPG,SSI,VND"
        return price_board(symbols)
    except Exception as e:
        st.error(f"Lỗi kết nối dữ liệu: {e}")
        return pd.DataFrame()

def analyze_trend(symbol):
    """Robot phân tích xu hướng đơn giản"""
    try:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        df = stock_historical_data(symbol, start, end, "1D", "stock")
        if df is None or len(df) < 10: return "N/A"
        
        # So sánh giá hiện tại với MA10
        ma10 = df['close'].tail(10).mean()
        price = df.iloc[-1]['close']
        
        if price > ma10: return "MUA / NẮM GIỮ"
        else: return "CÂN NHẮC BÁN"
    except:
        return "N/A"

# --- 5. GIAO DIỆN CHÍNH ---
st.title("⚡ TRUNG TÂM DỮ LIỆU & SỔ LỆNH")
st.caption(f"Cập nhật lần cuối: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")

# Xử lý danh sách mã người dùng nhập
clean_tickers = [x.strip().upper() for x in user_tickers.split(',') if x.strip()]
symbols_str = ",".join(clean_tickers)

# Nút làm mới
if st.button("🔄 QUÉT THỊ TRƯỜNG NGAY") or auto_refresh:
    
    with st.spinner("Đang kết nối máy chủ dữ liệu..."):
        df = get_market_data(symbols_str)
    
    if not df.empty:
        # Chia lưới hiển thị (3 cột)
        cols = st.columns(3)
        
        for i, row in df.iterrows():
            # Lấy thông tin cơ bản
            sym = row.get('Mã CP', '')
            price = row.get('Khớp lệnh', 0)
            change = row.get('+/-', 0)
            percent = row.get('%', 0)
            vol = row.get('Tổng KL', 0)
            
            # Màu sắc
            color_cls = "text-up" if change > 0 else "text-down" if change < 0 else "text-ref"
            
            # Robot phân tích nhanh
            robot_signal = analyze_trend(sym)
            
            # Hiển thị vào cột tương ứng
            with cols[i % 3]:
                # Tạo khung HTML
                st.markdown(f"""
                <div class="stock-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h2 style="margin:0; color:#FFD700;">{sym}</h2>
                        <div class="{color_cls}" style="font-size:18px;">
                            {price} ({percent}%)
                        </div>
                    </div>
                    <div style="font-size:12px; color:#aaa; margin-top:5px; margin-bottom:10px;">
                        Tổng Vol: <b>{vol:,}</b> | Robot: <b>{robot_signal}</b>
                    </div>
                """, unsafe_allow_html=True)
                
                # --- VẼ BẢNG SỔ LỆNH (3 BƯỚC GIÁ) ---
                # Lấy dữ liệu an toàn (tránh lỗi nếu thiếu cột)
                b1_v = row.get('KL Mua 1', 0); b1_p = row.get('Mua 1', 0)
                b2_v = row.get('KL Mua 2', 0); b2_p = row.get('Mua 2', 0)
                b3_v = row.get('KL Mua 3', 0); b3_p = row.get('Mua 3', 0)
                
                a1_v = row.get('KL Bán 1', 0); a1_p = row.get('Bán 1', 0)
                a2_v = row.get('KL Bán 2', 0); a2_p = row.get('Bán 2', 0)
                a3_v = row.get('KL Bán 3', 0); a3_p = row.get('Bán 3', 0)

                st.markdown(f"""
                    <table class="order-book">
                        <tr class="header-row">
                            <td>KL Mua</td><td>Giá Mua</td><td>Giá Bán</td><td>KL Bán</td>
                        </tr>
                        <tr>
                            <td class="bid-side">{b1_v}</td><td class="bid-side"><b>{b1_p}</b></td>
                            <td class="ask-side"><b>{a1_p}</b></td><td class="ask-side">{a1_v}</td>
                        </tr>
                        <tr>
                            <td class="bid-side" style="opacity:0.7">{b2_v}</td><td class="bid-side" style="opacity:0.7">{b2_p}</td>
                            <td class="ask-side" style="opacity:0.7">{a2_p}</td><td class="ask-side" style="opacity:0.7">{a2_v}</td>
                        </tr>
                        <tr>
                            <td class="bid-side" style="opacity:0.5">{b3_v}</td><td class="bid-side" style="opacity:0.5">{b3_p}</td>
                            <td class="ask-side" style="opacity:0.5">{a3_p}</td><td class="ask-side" style="opacity:0.5">{a3_v}</td>
                        </tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.warning("Không lấy được dữ liệu. Kiểm tra lại kết nối mạng hoặc danh sách mã.")
        
    # Tự động refresh
    if auto_refresh:
        time.sleep(30)
        st.rerun()

else:
    st.info("👋 Bấm nút **'QUÉT THỊ TRƯỜNG NGAY'** để xem bảng giá & sổ lệnh.")


