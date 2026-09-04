import streamlit as st
from utils import inject_css
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="EcoSort AI - Analytics", page_icon="📊", layout="wide")
inject_css()

from auth_utils import check_auth, get_current_user
from database import Repository
check_auth()

def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def load_detections_dataframe(days=None):
    if days is not None:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
    else:
        start_date = None
        
    df = pd.DataFrame()
    try:
        username = get_current_user()
        filters = {}
        if start_date:
            filters["start_date"] = start_date
            
        if username != "anonymous":
            filters["username"] = username
        data = Repository.get_detections(filters=filters, limit=1000)
        if data:
            df = pd.DataFrame(data)
    except Exception as e:
        st.error(f"Cannot load detections: {e}")
        
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if start_date:
            df = df[df['timestamp'] >= start_date]
    return df

st.title("📊 Sustainability Analytics Dashboard")
st.write("Examine waste classification distribution, recycle rate performance metrics, and carbon footprint trends.")

st.sidebar.subheader("Analytics Settings")
timeframe = st.sidebar.selectbox("Select Timeframe", ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"], index=3)
days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "All Time": None}
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
                               font_color='#103b27',
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
                               font_color='#103b27',
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
                                font_color='#103b27',
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
                               font_color='#103b27',
                               yaxis=dict(autorange="reversed", showgrid=False, color='#9ca3af'),
                               xaxis=dict(gridcolor='rgba(255,255,255,0.05)', color='#9ca3af'))
        st.plotly_chart(fig_top, width="stretch", config={'displayModeBar': False})
