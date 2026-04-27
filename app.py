import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os

st.set_page_config(page_title="電力數據分析", layout="wide")
st.title("⚡ ItriGel J200 PA60互動式電力數據比對工具")

# ── 側欄署名 ──────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 12px 0 4px 0;">
        <a href="https://github.com/YORROY123" target="_blank">
            <img src="https://avatars.githubusercontent.com/YORROY123"
                 width="72" style="border-radius:50%; border:2px solid #4CAF50;"/>
        </a>
        <br/>
        <a href="https://github.com/YORROY123" target="_blank"
           style="color:#4CAF50; font-weight:bold; text-decoration:none; font-size:14px;">
            YORROY123
        </a>
        <p style="color:#888; font-size:11px; margin:2px 0 0 0;">Made by YORROY123</p>
    </div>
    <hr style="border-color:#333; margin: 8px 0;"/>
    """,
    unsafe_allow_html=True
)

@st.cache_data
def load_and_merge_data(files):
    """讀取多份 CSV，合併並計算衍生欄位，回傳單一連續時間序列的 DataFrame"""
    df_list = []
    for file in files:
        df = pd.read_csv(file)
        if '時間' in df.columns:
            df['時間'] = pd.to_datetime(df['時間'])
            df.set_index('時間', inplace=True)
        df_list.append(df)
        
    # 合併所有上傳的檔案
    master_df = pd.concat(df_list)
    
    # 依照時間排序，並去除重複的時間點 (以防同一天不小心上傳兩次)
    master_df = master_df.sort_index()
    master_df = master_df[~master_df.index.duplicated(keep='last')]
    
    # 計算衍生欄位
    derived = {
        "L1_kW_total (冷庫總電)": (["L1_kW_a", "L1_kW_b", "L1_kW_c"], lambda d: d["L1_kW_a"] + d["L1_kW_b"] + d["L1_kW_c"]),
        "L2_kW_total (壓縮機總電)": (["L2_kW_a", "L2_kW_b", "L2_kW_c"], lambda d: d["L2_kW_a"] + d["L2_kW_b"] + d["L2_kW_c"]),
        "L3_kW_total (除霜電熱)": (["L3_kW_a", "L3_kW_b", "L3_kW_c"], lambda d: d["L3_kW_a"] + d["L3_kW_b"] + d["L3_kW_c"]),
        "L4_除霧電熱": (["L4_V_ab", "L4_I_a"], lambda d: d["L4_V_ab"] * d["L4_I_a"] * 1.0),
        "L4_冷凝風扇": (["L4_V_bc", "L4_I_b"], lambda d: d["L4_V_bc"] * d["L4_I_b"] * 0.83),
        "L4_蒸發風扇": (["L4_V_ab", "L4_I_c"], lambda d: d["L4_V_ab"] * d["L4_I_c"] * 1.0),
    }
    
    for new_col, (required_cols, formula) in derived.items():
        if all(c in master_df.columns for c in required_cols):
            numeric = {c: pd.to_numeric(master_df[c], errors='coerce') for c in required_cols}
            master_df[new_col] = formula(numeric)
            
    return master_df

def calculate_total_kwh(df, power_col, freq_minutes):
    """計算總耗電量 (kWh)。邏輯：kW 加總 * (取樣頻率分鐘 / 60)"""
    if power_col in df.columns:
        return df[power_col].dropna().sum() * (freq_minutes / 60.0)
    return 0.0

# 載入樣式設定
PRESETS_FILE = "presets.json"
if 'presets' not in st.session_state:
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                st.session_state.presets = json.load(f)
        except:
            st.session_state.presets = {"樣式 1": [], "樣式 2": [], "樣式 3": []}
    else:
        st.session_state.presets = {"樣式 1": [], "樣式 2": [], "樣式 3": []}

uploaded_files = st.file_uploader("📁 1. 請框選並批量上傳你要分析的 CSV 資料檔 (可選一整個月)", type="csv", accept_multiple_files=True)

if uploaded_files:
    # 核心改動：直接合併所有檔案成為一個 Master DataFrame
    master_df = load_and_merge_data(uploaded_files)
    all_columns = master_df.columns.tolist()
    
    min_time = master_df.index.min()
    max_time = master_df.index.max()
    
    st.sidebar.success(f"✅ 成功整合 {len(uploaded_files)} 份檔案！")
    st.sidebar.info(f"📅 資料區間:\n{min_time.strftime('%Y-%m-%d %H:%M')} \n~\n {max_time.strftime('%Y-%m-%d %H:%M')}")
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("💾 常用欄位樣式")
    preset_slot = st.sidebar.radio("選擇槽位", ["樣式 1", "樣式 2", "樣式 3"], horizontal=True, label_visibility="collapsed")
    p_col1, p_col2 = st.sidebar.columns(2)

    if p_col1.button("📥 載入樣式", use_container_width=True):
        saved_cols = st.session_state.presets.get(preset_slot, [])
        matched = [c for c in all_columns if c in saved_cols]
        st.session_state.selected_cols = matched

    if p_col2.button("💾 儲存選項", use_container_width=True):
        current_sel = st.session_state.get('selected_cols', [])
        st.session_state.presets[preset_slot] = current_sel
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.presets, f, ensure_ascii=False)
        st.sidebar.success(f"已儲存至 {preset_slot}！")
        
    st.sidebar.markdown("---")

    resample_rule = st.sidebar.selectbox(
        "2. 資料抽樣與計算頻率",
        ["每 1 分鐘平均 (推薦)", "每 5 分鐘平均", "每 10 分鐘平均"],
        index=0 
    )
    
    rule_map = {
        "每 1 分鐘平均 (推薦)": ("1min", 1),
        "每 5 分鐘平均": ("5min", 5),
        "每 10 分鐘平均": ("10min", 10)
    }
    freq_str, freq_mins = rule_map[resample_rule]

    selected_columns = st.sidebar.multiselect(
        "3. 選擇要顯示的欄位 (例如各區總電)", 
        all_columns,
        key='selected_cols' 
    )
    
    plot_mode = st.sidebar.radio("4. 顯示模式", ["分開顯示 (逐列子圖)", "合併顯示 (畫在同一張圖)"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("📏 座標軸與時間設定")
    
    min_dt = min_time.to_pydatetime().replace(microsecond=0)
    max_dt = max_time.to_pydatetime().replace(microsecond=0)
    
    selected_time = st.sidebar.slider(
        "X 軸：選擇要統計與顯示的時間範圍",
        min_value=min_dt,
        max_value=max_dt,
        value=(min_dt, max_dt),
        format="MM-DD HH:mm"
    )
    
    enable_y_axis = st.sidebar.checkbox("開啟手動設定 Y 軸上下限")
    if enable_y_axis:
        col1, col2 = st.sidebar.columns(2)
        y_min = col1.number_input("Y 軸下限", value=0.0, step=10.0)
        y_max = col2.number_input("Y 軸上限", value=500.0, step=10.0)

    # ==========================================
    # 🌟 資料過濾與重採樣
    # ==========================================
    # 根據 Slider 選擇的時間過濾
    mask = (master_df.index >= selected_time[0]) & (master_df.index <= selected_time[1])
    filtered_df = master_df.loc[mask]
    
    # 根據選擇的頻率進行重採樣
    if not filtered_df.empty:
        resampled_df = filtered_df.resample(freq_str).mean()
    else:
        resampled_df = pd.DataFrame()

    # ==========================================
    # 📊 耗電量統計卡片 (動態計算)
    # ==========================================
    st.markdown("### 📊 區間累積耗電量統計 (kWh)")
    
    if not resampled_df.empty:
        # 依照過濾與重採樣後的資料計算度數
        total_L1 = calculate_total_kwh(resampled_df, "L1_kW_total (冷庫總電)", freq_mins)
        total_L2 = calculate_total_kwh(resampled_df, "L2_kW_total (壓縮機總電)", freq_mins)
        total_L3 = calculate_total_kwh(resampled_df, "L3_kW_total (除霜電熱)", freq_mins)
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("⚡ 冷庫總耗電", f"{total_L1:.2f} 度 (kWh)")
        m_col2.metric("❄️ 壓縮機總耗電", f"{total_L2:.2f} 度 (kWh)")
        m_col3.metric("🔥 除霜總耗電", f"{total_L3:.2f} 度 (kWh)")
    else:
        st.warning("⚠️ 所選時間範圍內無資料")

    st.markdown("---")

    # ==========================================
    # 📈 開始繪圖 
    # ==========================================
    if selected_columns and not resampled_df.empty:
        
        if len(selected_columns) > 1:
            safe_spacing = min(0.05, 0.8 / len(selected_columns))
        else:
            safe_spacing = 0.0

        if plot_mode == "合併顯示 (畫在同一張圖)":
            fig = go.Figure()
        else:
            fig = make_subplots(
                rows=len(selected_columns), cols=1, 
                shared_xaxes=True, 
                subplot_titles=selected_columns,
                vertical_spacing=safe_spacing
            )
            
        for i, col_name in enumerate(selected_columns):
            s = resampled_df[col_name]
                
            trace = go.Scatter(x=s.index, y=s, mode='lines', name=col_name, line=dict(width=1.5))
            
            if plot_mode == "合併顯示 (畫在同一張圖)":
                fig.add_trace(trace)
            else:
                fig.add_trace(trace, row=i+1, col=1)
        
        fig.update_xaxes(
            range=[selected_time[0], selected_time[1]],
            showticklabels=True,      
            title_text="時間"         
        )
        
        if enable_y_axis:
            fig.update_yaxes(range=[y_min, y_max])
            
        if plot_mode == "合併顯示 (畫在同一張圖)":
            fig.update_layout(height=600, hovermode="x unified", dragmode="zoom")
        else:
            fig.update_layout(height=max(400, 250 * len(selected_columns)), hovermode="x unified", dragmode="zoom", showlegend=False)
            
        st.plotly_chart(fig, width="stretch")
    elif not selected_columns:
        st.info("👈 請在左側「3. 選擇要顯示的欄位」中挑選資料以產生圖表。")

else:
    st.info("👈 請先上傳檔案 (可按住 Shift 或 Ctrl 選擇多份 CSV)，系統會自動整合為長期資料。")
