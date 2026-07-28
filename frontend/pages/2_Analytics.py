import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="EcoSort AI - Analytics", page_icon="📊", layout="wide")

from frontend.auth_utils import check_auth, get_auth_headers
check_auth()

API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def load_detections_dataframe(days=30):
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    df = pd.DataFrame()
    try:
        response = requests.get(f"{API_URL}/detections?limit=1000", timeout=10, headers=get_auth_headers())
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
        else:
            st.error(f"Could not load detections (status {response.status_code}).")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df[df['timestamp'] >= start_date]
    return df

st.title("📊 Sustainability Analytics Dashboard")
st.write("Examine waste classification distribution, recycle rate performance metrics, and carbon footprint trends.")

st.sidebar.subheader("Analytics Settings")
timeframe = st.sidebar.selectbox("Select Timeframe", ["Last 7 Days", "Last 30 Days", "Last 90 Days"], index=1)
days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90}
days = days_map[timeframe]

df = load_detections_dataframe(days)

if df.empty:
    st.info("No historical detection records found. Log some detections on the Detection page first!")
else:
    total_scanned = len(df)
    RECYCLABLE_CATEGORIES = ["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass", "White-glass", "Cardboard"]
    recyclable_df = df[df['category'].isin(RECYCLABLE_CATEGORIES)]
    recycling_rate = (len(recyclable_df) / total_scanned * 100) if total_scanned > 0 else 0
    total_co2 = df['carbon_saved_kg'].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"Total Detections ({timeframe})", f"{total_scanned} items")
    with col2:
        st.metric("Recycling Efficiency", f"{recycling_rate:.1f}%")
    with col3:
        st.metric("Net Carbon Savings", f"{total_co2:.2f} kg CO₂")

    st.markdown("---")
    row1_col1, row1_col2 = st.columns([1, 1])

    with row1_col1:
        st.subheader("Material Classification Share")
        cat_counts = df['category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        fig_pie = px.pie(cat_counts, values='Count', names='Category',
                         color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.4)
        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                               font_color='#f3f4f6',
                               legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        st.plotly_chart(fig_pie, width="stretch", config={'displayModeBar': False})

    with row1_col2:
        st.subheader("Daily Scanning Volumes")
        df['date'] = df['timestamp'].dt.date
        daily_trends = df.groupby(['date', 'category']).size().reset_index(name='Count')
        fig_bar = px.bar(daily_trends, x='date', y='Count', color='category',
                         color_discrete_sequence=px.colors.qualitative.Pastel, barmode='stack',
                         labels={'date': 'Date', 'Count': 'Items Logged', 'category': 'Category'})
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                               font_color='#f3f4f6',
                               xaxis=dict(showgrid=False, color='#9ca3af'),
                               yaxis=dict(gridcolor='rgba(255,255,255,0.05)', color='#9ca3af'))
        st.plotly_chart(fig_bar, width="stretch", config={'displayModeBar': False})

    st.markdown("---")
    row2_col1, row2_col2 = st.columns([1, 1])

    with row2_col1:
        st.subheader("Carbon Mitigation Trend (Cumulative)")
        df_sorted = df.sort_values('timestamp')
        df_sorted['cumulative_co2'] = df_sorted['carbon_saved_kg'].cumsum()
        fig_line = px.area(df_sorted, x='timestamp', y='cumulative_co2',
                           labels={'timestamp': 'Time', 'cumulative_co2': 'Cumulative CO₂ Saved (kg)'},
                           color_discrete_sequence=['#10b981'])
        fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                font_color='#f3f4f6',
                                xaxis=dict(showgrid=False, color='#9ca3af'),
                                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', color='#9ca3af'))
        st.plotly_chart(fig_line, width="stretch", config={'displayModeBar': False})

    with row2_col2:
        st.subheader("Top Detected Waste Items")
        top_items = df['object_name'].value_counts().head(10).reset_index()
        top_items.columns = ['Item', 'Count']
        fig_top = px.bar(top_items, x='Count', y='Item', orientation='h',
                         color_discrete_sequence=['#1e3a8a'],
                         labels={'Count': 'Count', 'Item': 'Material'})
        fig_top.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                               font_color='#f3f4f6',
                               yaxis=dict(autorange="reversed", showgrid=False, color='#9ca3af'),
                               xaxis=dict(gridcolor='rgba(255,255,255,0.05)', color='#9ca3af'))
        st.plotly_chart(fig_top, width="stretch", config={'displayModeBar': False})