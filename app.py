import streamlit as st
import pandas as pd
import time

# --- CẤU HÌNH ---
st.set_page_config(page_title="TopInvest Auto", layout="wide", page_icon="🤖")

# --- PHẦN QUAN TRỌNG NHẤT: TỰ ĐỘNG NHẬN DIỆN PHIÊN BẢN ---
# Đoạn này giúp web chạy được trên CẢ bản cũ và bản mới
try:
    # Thử gọi theo cách cũ (Bản 0.2.9)
    from vnstock import price_board
    VERSION = "OLD"
    st.toast("Đang chạy phiên bản: Ổn định (Old Core)", icon="✅")
except ImportError:
    # Nếu lỗi, chuyển sang gọi theo cách mới (Bản 3.x)
    try:
        from vnstock import quote
        VERSION = "NEW"
        st.toast("Đang chạy phiên bản: Mới nhất (New Core)", icon="🚀")
    except ImportError:
        st.error("Lỗi nghiêm trọng: Không tìm thấy thư viện Vnstock.")
        st.stop()

# --- CSS GIAO DIỆN DARK MODE ---
st.markdown("""
<style>
    .stApp { background-color: #111; color: #eee; }
    .card { background-color: #222; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #333; }
    .big-text { font-size: 24px; font-weight: bold; }
    .green { color: #0f0; }
    .red { color: #f44; }
    .yellow { color: #fd0; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ BẢNG GIÁ THÔNG MINH (AUTO-ADAPT)")
st.caption("Hệ thống tự động điều chỉnh theo thư viện máy chủ.")

# --- INPUT ---
with st.sidebar:
    st.header("Danh mục")
    default = "HPG, SSI, VND, FPT, MWG, TCB, STB, DIG, PDR"
    tickers = st.text_area("Nhập mã:", default, height=150)
    auto_ref = st.checkbox("Tự động cập nhật (30s)", value=True)
    if st.button("Làm mới ngay"):
        st.rerun()

# --- HÀM XỬ LÝ ĐA NĂNG ---
def get_universal_data(symbol_list):
    symbols_str = ",".join(symbol_list)
    
    if VERSION == "OLD":
        # Xử lý cho bản cũ (price_board trả về tiếng Việt)
        try:
            df = price_board(symbols_str)
            # Đổi tên cột cho thống nhất
            df = df.rename(columns={
                'Mã CP': 'symbol', 
                'Khớp lệnh': 'price', 
                '+/-': 'change', 
                '%': 'percent',
                'Tổng KL': 'volume'
            })
            return df
        except: return pd.DataFrame()
        
    elif VERSION == "NEW":
        # Xử lý cho bản mới (quote trả về tiếng Anh)
        try:
            df = quote(symbols_str)
            # Bản mới đôi khi trả về cột khác nhau, ta map lại
            # Ưu tiên các tên cột thường gặp trong bản 3.x
            # Ví dụ: stockSymbol, lastPrice, change, changePercent
            df['price'] = df.get('price', df.get('lastPrice', 0))
            # Nếu giá nhỏ (đơn vị nghìn), nhân lên
            if df['price'].mean() < 500: df['price'] = df['price'] * 1000
                
            df['symbol'] = df.get('symbol', df.get('stockSymbol', ''))
            df['percent'] = df.get('percent', df.get('changePercent', 0)) * 100
            
            # Xử lý lỗi % quá lớn do định dạng
            if df['percent'].mean() > 50: df['percent'] = df['percent'] / 100
                
            return df
        except: return pd.DataFrame()

# --- CHẠY CHƯƠNG TRÌNH ---
symbol_list = [x.strip().upper() for x in tickers.split(',') if x.strip()]

with st.spinner("Đang kết nối dữ liệu..."):
    df = get_universal_data(symbol_list)

if not df.empty:
    cols = st.columns(3)
    for i, row in df.iterrows():
        try:
            sym = row['symbol']
            price = row['price']
            change = row['change']
            pct = row['percent']
            vol = row.get('volume', row.get('totalVol', 0))
            
            color = "green" if change > 0 else "red" if change < 0 else "yellow"
            
            with cols[i % 3]:
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between;">
                        <h3 style="margin:0; color:gold;">{sym}</h3>
                        <span class="big-text {color}">{price:,.0f}</span>
                    </div>
                    <div style="text-align:right; font-weight:bold;" class="{color}">
                        {change:,.0f} ({pct:.2f}%)
                    </div>
                    <div style="font-size:12px; color:#888;">Vol: {vol:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
        except:
            continue
else:
    st.warning("Chưa lấy được dữ liệu. Vui lòng đợi 30s hoặc bấm Làm mới.")

if auto_ref:
    time.sleep(30)
    st.rerun()


