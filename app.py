import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(
    page_title="TopInvest Pro (Real Data)",
    page_icon="🦈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Thiết lập múi giờ Việt Nam
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# CSS Tùy chỉnh (Giữ nguyên giao diện đẹp)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .metric-container { 
        background-color: #1e2127; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #30363d; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    /* Màu sắc thương hiệu */
    h1, h2, h3 { color: #f1c40f !important; }
    
    /* Box Tín hiệu */
    .signal-active {
        background: rgba(0, 192, 135, 0.1); 
        border: 1px solid #00c087; 
        color: #00c087; 
        padding: 10px; 
        border-radius: 5px; 
        text-align: center; 
        font-weight: bold;
    }
    .signal-neutral {
        background: rgba(128, 128, 128, 0.1); 
        border: 1px solid #666; 
        color: #aaa; 
        padding: 10px; 
        border-radius: 5px; 
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. MODULE DỮ LIỆU (ROBUST DATA LOADER) ---

@st.cache_data(ttl=300) # Cache 5 phút
def fetch_data(symbol):
    """
    Hàm lấy dữ liệu "bất tử":
    1. Thử Vnstock (Ưu tiên)
    2. Thử Yahoo Finance (Dự phòng)
    3. Trả về DataFrame chuẩn hóa hoặc Rỗng.
    """
    symbol = symbol.strip().upper()
    df = pd.DataFrame()
    source = "N/A"
    
    # Lấy ngày giờ hiện tại theo giờ VN
    now_vn = datetime.now(VN_TZ)
    end_date_str = now_vn.strftime('%Y-%m-%d')
    start_date_str = (now_vn - timedelta(days=365)).strftime('%Y-%m-%d')

    # --- KÊNH 1: VNSTOCK ---
    try:
        from vnstock3 import Vnstock
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df_vn = stock.quote.history(start=start_date_str, end=end_date_str)
        
        if df_vn is not None and not df_vn.empty and len(df_vn) > 10:
            # Chuẩn hóa tên cột
            cols_map = {'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}
            df = df_vn.rename(columns=cols_map)
            # Giữ lại các cột cần thiết
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            source = "Vnstock (VN)"
    except Exception:
        pass # Lặng lẽ bỏ qua để thử kênh 2

    # --- KÊNH 2: YAHOO FINANCE (BACKUP) ---
    if df.empty:
        try:
            import yfinance as yf
            # Yahoo cần hậu tố .VN
            yf_ticker = f"{symbol}.VN"
            df_yf = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
            
            if not df_yf.empty and len(df_yf) > 10:
                # Yahoo trả về MultiIndex, cần làm phẳng
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                
                df = df_yf[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                source = "Yahoo Finance (Intl)"
        except Exception:
            pass

    # --- XỬ LÝ CUỐI CÙNG ---
    if not df.empty:
        # Xử lý Volume = 0 (Tránh chia cho 0)
        df['Volume'] = df['Volume'].replace(0, 1)
        # Ép kiểu số
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        
    return df, source

# --- 2. MODULE TÍNH TOÁN (SHARK ALGORITHM) ---

def calculate_metrics(df_input):
    if df_input.empty: return df_input
    
    df = df_input.copy()
    
    # 1. Điểm cân bằng (Balance Point) - VWAP 7 ngày
    # Công thức: Tổng(Giá trị khớp) / Tổng(Khối lượng)
    df['Total_Value'] = (df['Close'] * df['Volume'])
    df['Balance_Point'] = df['Total_Value'].rolling(window=7).sum() / df['Volume'].rolling(window=7).sum()
    
    # 2. Shark Score (Sức mạnh dòng tiền)
    # Logic: Phân tích chênh lệch giá (Spread) và Volume
    # Spread dương + Vol lớn => Mua chủ động
    # Spread âm + Vol lớn => Bán chủ động
    
    df['Spread'] = df['Close'].diff()
    
    # Dòng tiền dương (Gom)
    df['Money_Flow_Pos'] = np.where(df['Spread'] > 0, df['Volume'] * df['Close'], 0)
    # Dòng tiền âm (Xả)
    df['Money_Flow_Neg'] = np.where(df['Spread'] < 0, df['Volume'] * df['Close'], 0)
    
    # Tổng hợp 14 phiên (Giống RSI)
    mf_pos_sum = df['Money_Flow_Pos'].rolling(14).sum()
    mf_neg_sum = df['Money_Flow_Neg'].rolling(14).sum()
    
    # Tránh chia cho 0
    mf_neg_sum = mf_neg_sum.replace(0, 1)
    
    mfi = 100 - (100 / (1 + (mf_pos_sum / mf_neg_sum)))
    df['Shark_Score'] = mfi.fillna(50)
    
    # Làm mượt (EMA 3) để biểu đồ đỡ giật
    df['Shark_Score_Smooth'] = df['Shark_Score'].ewm(span=3, adjust=False).mean()
    
    return df

def get_ai_signal(row):
    """Trả về trạng thái, màu sắc và lý do"""
    price = row['Close']
    balance = row['Balance_Point']
    score = row['Shark_Score_Smooth']
    
    # Ngưỡng (Threshold)
    if score >= 65 and price >= balance:
        return "CÁ MẬP GOM", "#00c087", "Dòng tiền Lớn vào + Giá trên nền"
    elif score <= 35:
        return "CÁ MẬP XẢ", "#ff3b30", "Dòng tiền rút ra mạnh"
    elif price > balance:
        return "NẮM GIỮ", "#f1c40f", "Xu hướng tăng (Uptrend)"
    else:
        return "QUAN SÁT", "#888888", "Chưa có tín hiệu rõ ràng"

# --- 3. GIAO DIỆN CHÍNH (FRONTEND) ---

# Sidebar điều khiển
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bullish.png", width=60)
    st.title("TopInvest Pro")
    
    symbol_input = st.text_input("Nhập mã cổ phiếu (VN30):", value="HPG").strip().upper()
    
    st.divider()
    st.write("Cấu hình hiển thị:")
    show_ma = st.checkbox("Đường xu hướng (MA20)", True)
    show_balance = st.checkbox("Đường cân bằng (Balance)", True)

# Main Logic
if symbol_input:
    # 1. Tải dữ liệu
    df_raw, source_name = fetch_data(symbol_input)
    
    if df_raw.empty:
        st.error(f"⚠️ Không tìm thấy dữ liệu cho mã '{symbol_input}'. Vui lòng kiểm tra lại mã hoặc thử lại sau.")
        st.info("Gợi ý: Thử các mã phổ biến như HPG, SSI, FPT, VCB...")
    else:
        # 2. Tính toán
        df_calc = calculate_metrics(df_raw)
        
        # Lấy phiên mới nhất
        last_row = df_calc.iloc[-1]
        prev_row = df_calc.iloc[-2]
        
        # Tính biến động
        price_change = last_row['Close'] - prev_row['Close']
        pct_change = (price_change / prev_row['Close']) * 100
        
        # --- PHẦN 1: HEADER & METRICS ---
        st.caption(f"Dữ liệu cập nhật từ: {source_name} • Ngày: {last_row.name.strftime('%d/%m/%Y')}")
        
        c1, c2, c3 = st.columns([1.5, 1, 1])
        
        with c1:
            # Giá lớn
            color_txt = "#00c087" if price_change >= 0 else "#ff3b30"
            st.markdown(f"<h1 style='margin:0; padding:0'>{symbol_input}</h1>", unsafe_allow_html=True)
            st.markdown(f"""
                <div style='font-size: 38px; font-weight: bold; color: {color_txt}'>
                    {last_row['Close']:,.0f} 
                    <span style='font-size: 18px; color: #aaa'>
                        {price_change:+,.0f} ({pct_change:+.2f}%)
                    </span>
                </div>
            """, unsafe_allow_html=True)
            
        with c2:
            # Shark Score
            score_val = last_row['Shark_Score_Smooth']
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.write("🦈 Sức mạnh Dòng tiền")
            st.markdown(f"<div style='font-size: 24px; font-weight: bold; color: white'>{score_val:.0f}/100</div>", unsafe_allow_html=True)
            st.progress(int(score_val))
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c3:
            # Tín hiệu AI
            sig_text, sig_color, sig_reason = get_ai_signal(last_row)
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.write("🤖 Tín hiệu AI")
            st.markdown(f"""
                <div style='color: {sig_color}; font-size: 20px; font-weight: bold; border: 1px solid {sig_color}; border-radius: 5px; text-align: center; padding: 2px;'>
                    {sig_text}
                </div>
            """, unsafe_allow_html=True)
            st.caption(sig_reason)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- PHẦN 2: BIỂU ĐỒ NÂNG CAO ---
        st.divider()
        
        # Chart 1: Giá & Balance
        fig = go.Figure()
        
        # Nến Nhật
        fig.add_trace(go.Candlestick(
            x=df_calc.index,
            open=df_calc['Open'], high=df_calc['High'],
            low=df_calc['Low'], close=df_calc['Close'],
            name='Giá',
            increasing_line_color='#00c087', decreasing_line_color='#ff3b30'
        ))
        
        # Đường Balance Point (Đặc sản TopInvest)
        if show_balance:
            fig.add_trace(go.Scatter(
                x=df_calc.index, y=df_calc['Balance_Point'],
                mode='lines', name='Đường Cân Bằng (Shark Cost)',
                line=dict(color='#f1c40f', width=2)
            ))
            
        # MA20
        if show_ma:
            ma20 = df_calc['Close'].rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=df_calc.index, y=ma20,
                mode='lines', name='MA20 (Xu hướng)',
                line=dict(color='#3498db', width=1, dash='dot')
            ))

        fig.update_layout(
            title="Biểu đồ Giá & Vùng Cân Bằng",
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            height=450,
            hovermode="x unified",
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Chart 2: Shark Flow Bar
        st.subheader("Dòng tiền Cá Mập (Shark Flow)")
        
        fig_flow = go.Figure()
        
        # Tô màu cột
        colors = []
        for v in df_calc['Shark_Score_Smooth']:
            if v >= 60: colors.append('#f1c40f') # Vàng (Gom)
            elif v <= 40: colors.append('#ff3b30') # Đỏ (Xả)
            else: colors.append('#555555') # Xám (Trung tính)
            
        fig_flow.add_trace(go.Bar(
            x=df_calc.index, y=df_calc['Shark_Score_Smooth'],
            marker_color=colors, name='Shark Score'
        ))
        
        # Các đường ngưỡng
        fig_flow.add_hline(y=60, line_dash="dot", line_color="#00c087", annotation_text="Vùng GOM (Big Buy)")
        fig_flow.add_hline(y=40, line_dash="dot", line_color="#ff3b30", annotation_text="Vùng XẢ (Sell)")
        
        fig_flow.update_layout(
            template="plotly_dark",
            height=250,
            yaxis=dict(range=[0, 100], title="Sức mạnh (%)"),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig_flow, use_container_width=True)

# --- PHẦN 3: BỘ LỌC (SCANNER) ---
st.divider()
with st.expander("🔍 QUÉT TÍN HIỆU NHANH (VN30)"):
    if st.button("Bắt đầu Quét"):
        watchlist = ['ACB', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
                     'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 
                     'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE']
        
        results = []
        progress_text = st.empty()
        my_bar = st.progress(0)
        
        for i, tick in enumerate(watchlist):
            my_bar.progress((i + 1) / len(watchlist))
            progress_text.text(f"Đang phân tích {tick}...")
            
            # Lấy data nhanh
            d_raw, _ = fetch_data(tick)
            if not d_raw.empty:
                d_calc = calculate_metrics(d_raw)
                curr = d_calc.iloc[-1]
                
                # Logic lọc
                sc = curr['Shark_Score_Smooth']
                pr = curr['Close']
                bl = curr['Balance_Point']
                
                status = ""
                if sc >= 60 and pr > bl: status = "🔥 MUA"
                elif sc <= 35: status = "❌ BÁN"
                
                if status:
                    results.append({
                        "Mã": tick,
                        "Giá": f"{pr:,.0f}",
                        "Shark Score": f"{sc:.1f}",
                        "Tín hiệu": status
                    })
        
        my_bar.empty()
        progress_text.text("Hoàn tất!")
        
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.info("Hiện tại chưa có mã nào trong VN30 có tín hiệu Mua/Bán mạnh.")

# Footer
st.markdown("---")
st.markdown("<center style='color:#555'>TopInvest Ultimate v3.0 | Real Data Engine</center>", unsafe_allow_html=True)


