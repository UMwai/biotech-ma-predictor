"""
Streamlit Dashboard for Biotech M&A Predictor.

Provides interactive visualization of:
- M&A Watchlist rankings
- Company profiles and scores
- Signal activity
- Historical trends
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import httpx
from datetime import datetime, timedelta
import os

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Biotech M&A Predictor",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e3a5f;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #1e3a5f;
    }
    .score-high { color: #e74c3c; }
    .score-medium { color: #f39c12; }
    .score-low { color: #27ae60; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def fetch_watchlist():
    """Fetch current M&A watchlist from API."""
    try:
        response = httpx.get(f"{API_URL}/predictions/watchlist", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch watchlist: {e}")
        return {"companies": []}


@st.cache_data(ttl=300)
def fetch_company(ticker: str):
    """Fetch company details from API."""
    try:
        response = httpx.get(f"{API_URL}/companies/{ticker}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch company {ticker}: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_signals(ticker: str = None, days: int = 7):
    """Fetch recent signals from API."""
    try:
        params = {"days": days}
        if ticker:
            params["ticker"] = ticker
        response = httpx.get(f"{API_URL}/signals", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch signals: {e}")
        return {"signals": []}


def render_score_gauge(score: int, title: str = "M&A Score"):
    """Render a gauge chart for the score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 20}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#1e3a5f"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 50], 'color': '#d4edda'},
                {'range': [50, 75], 'color': '#fff3cd'},
                {'range': [75, 100], 'color': '#f8d7da'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 75
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def render_score_breakdown(components: dict):
    """Render radar chart of score components."""
    categories = list(components.keys())
    values = list(components.values())
    values.append(values[0])  # Close the polygon
    categories.append(categories[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(30, 58, 95, 0.3)',
        line=dict(color='#1e3a5f', width=2),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=300,
        margin=dict(l=60, r=60, t=40, b=40),
    )
    return fig


def main():
    # Sidebar
    st.sidebar.markdown("## 🧬 Biotech M&A Predictor")
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Watchlist", "Company Deep Dive", "Signal Feed", "Reports"]
    )

    if page == "Dashboard":
        render_dashboard()
    elif page == "Watchlist":
        render_watchlist()
    elif page == "Company Deep Dive":
        render_company_detail()
    elif page == "Signal Feed":
        render_signal_feed()
    elif page == "Reports":
        render_reports()


def render_dashboard():
    """Main dashboard view."""
    st.markdown('<p class="main-header">Biotech M&A Dashboard</p>', unsafe_allow_html=True)

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🎯 Active Watchlist",
            value="47",
            delta="3 new this week"
        )
    with col2:
        st.metric(
            label="📊 Avg M&A Score",
            value="68.4",
            delta="2.1"
        )
    with col3:
        st.metric(
            label="⚡ Signals Today",
            value="23",
            delta="8 high-impact"
        )
    with col4:
        st.metric(
            label="🔔 Active Alerts",
            value="5",
            delta="-2"
        )

    st.markdown("---")

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top M&A Candidates")
        st.subheader("Top M&A Candidates")
        watchlist_data = fetch_watchlist()
        if watchlist_data and "watchlist" in watchlist_data:
            top_items = watchlist_data["watchlist"][:5] # Top 5
            df = pd.DataFrame([
                {
                    'Company': item.get('ticker'),
                    'Score': item.get('ma_score'),
                } for item in top_items
            ])
        else:
             df = pd.DataFrame(columns=['Company', 'Score'])
             
        if not df.empty:
            fig = px.bar(
                df, x='Company', y='Score',
                color='Score',
                color_continuous_scale=['#27ae60', '#f39c12', '#e74c3c'],
            )
        else:
            fig = go.Figure()
            fig.add_annotation(text="No data available", showarrow=False)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Signal Distribution (7 Days)")
        signal_data = pd.DataFrame({
            'Type': ['Clinical Trial', 'Patent/IP', 'Insider', 'Regulatory', 'Financial'],
            'Count': [45, 23, 67, 12, 34]
        })
        fig = px.pie(
            signal_data, values='Count', names='Type',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Recent high-impact signals
    st.subheader("Recent High-Impact Signals")
    signals_df = pd.DataFrame({
        'Time': ['2 hours ago', '4 hours ago', '6 hours ago', '8 hours ago'],
        'Company': ['ACAD', 'MRNA', 'SGEN', 'IONS'],
        'Signal': [
            'Phase 3 trial success announced',
            'Insider purchase: CEO bought $2M shares',
            'FDA granted priority review',
            'Patent cliff approaching for competitor'
        ],
        'Impact': ['High', 'Medium', 'High', 'Medium']
    })
    st.dataframe(signals_df, use_container_width=True, hide_index=True)


def render_watchlist():
    """Watchlist view with full rankings."""
    st.markdown('<p class="main-header">M&A Watchlist</p>', unsafe_allow_html=True)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 50)
    with col2:
        therapeutic_area = st.multiselect(
            "Therapeutic Area",
            ["Oncology", "Neurology", "Immunology", "Cardiology", "Rare Disease"]
        )
    with col3:
        sort_by = st.selectbox("Sort By", ["Score", "Score Change", "Market Cap"])

    # Fetch watchlist data
    data = fetch_watchlist()
    if data and "watchlist" in data:
        items = data["watchlist"]
        # Convert API response to DataFrame
        watchlist = pd.DataFrame([
            {
                'Rank': item.get('rank'),
                'Ticker': item.get('ticker'),
                'Company': item.get('name'),
                'M&A Score': item.get('ma_score'),
                'Change (7d)': item.get('score_change_7d'),
                'Market Cap ($B)': (item.get('market_cap_usd', 0) or 0) / 1e9,
                'Top Acquirer': 'N/A' # Placeholder until matching API integrated
            } for item in items
        ])
    else:
        # Fallback to empty
        watchlist = pd.DataFrame(columns=[
            'Rank', 'Ticker', 'Company', 'M&A Score', 
            'Change (7d)', 'Market Cap ($B)', 'Top Acquirer'
        ])

    st.dataframe(
        watchlist,
        use_container_width=True,
        hide_index=True,
        column_config={
            "M&A Score": st.column_config.ProgressColumn(
                "M&A Score",
                format="%d",
                min_value=0,
                max_value=100,
            ),
            "Change (7d)": st.column_config.NumberColumn(
                "Change (7d)",
                format="%+d",
            ),
        }
    )


def render_company_detail():
    """Deep dive into a specific company."""
    st.markdown('<p class="main-header">Company Deep Dive</p>', unsafe_allow_html=True)

    ticker = st.text_input("Enter Ticker Symbol", "ACAD").upper()

    if ticker:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.plotly_chart(render_score_gauge(92, f"{ticker} M&A Score"), use_container_width=True)

        with col2:
            components = {
                'Pipeline': 95,
                'Patent': 78,
                'Financial': 88,
                'Insider': 92,
                'Strategic Fit': 85,
                'Regulatory': 90
            }
            st.plotly_chart(render_score_breakdown(components), use_container_width=True)

        # Company details
        st.subheader("Company Profile")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Market Cap", "$4.2B")
        col2.metric("Cash Position", "$890M")
        col3.metric("Cash Runway", "24 months")
        col4.metric("Pipeline Assets", "6")

        # Pipeline
        st.subheader("Drug Pipeline")
        pipeline = pd.DataFrame({
            'Drug': ['Nuplazid', 'ACP-101', 'ACP-319', 'ACP-204'],
            'Indication': ['Parkinson psychosis', 'Schizophrenia', 'Depression', 'Alzheimers'],
            'Phase': ['Approved', 'Phase 3', 'Phase 2', 'Phase 1'],
            'Catalyst': ['Expansion', 'Q2 2024', 'Q4 2024', 'Q1 2025'],
        })
        st.dataframe(pipeline, use_container_width=True, hide_index=True)

        # Potential acquirers
        st.subheader("Potential Acquirers")
        acquirers = pd.DataFrame({
            'Acquirer': ['Pfizer', 'Bristol Myers', 'Johnson & Johnson'],
            'Fit Score': [89, 82, 78],
            'Rationale': [
                'CNS pipeline gap, patent cliff 2025',
                'Neuroscience expansion strategy',
                'Portfolio diversification'
            ]
        })
        st.dataframe(acquirers, use_container_width=True, hide_index=True)


def render_signal_feed():
    """Real-time signal feed."""
    st.markdown('<p class="main-header">Signal Feed</p>', unsafe_allow_html=True)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        signal_types = st.multiselect(
            "Signal Type",
            ["Clinical Trial", "Patent/IP", "Insider Activity", "Regulatory", "Financial"],
            default=["Clinical Trial", "Insider Activity"]
        )
    with col2:
        impact_filter = st.multiselect("Impact Level", ["High", "Medium", "Low"], default=["High"])
    with col3:
        days = st.slider("Days Back", 1, 30, 7)

    # Signal feed
    signal_data = fetch_signals(days=days)
    if signal_data and "signals" in signal_data:
        raw_signals = signal_data["signals"]
        # Map to display format
        signals = []
        for s in raw_signals:
            signals.append({
                "time": s.get("event_date", "N/A"),
                "ticker": "N/A", # API needs to return ticker or we fetch. Assuming signal object has it for now or we skip.
                "type": s.get("signal_type", "Unknown"),
                "impact": s.get("severity", "Medium").title(),
                "message": s.get("title", ""),
            })
    else:
        signals = []

    for signal in signals:
        impact_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[signal["impact"]]
        st.markdown(f"""
        **{signal['time']}** | {impact_color} **{signal['ticker']}** - {signal['type']}

        {signal['message']}

        ---
        """)


def render_reports():
    """Reports access page."""
    st.markdown('<p class="main-header">Reports</p>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Daily Digest", "Weekly Watchlist", "Custom Report"])

    with tab1:
        st.subheader("Daily Digest Reports")
        reports = pd.DataFrame({
            'Date': pd.date_range(end=datetime.now(), periods=7).strftime('%Y-%m-%d').tolist()[::-1],
            'Signals': [23, 31, 18, 27, 22, 35, 19],
            'High Impact': [5, 8, 3, 6, 4, 9, 4],
        })
        st.dataframe(reports, use_container_width=True, hide_index=True)
        st.download_button("Download Latest", "report_content", "daily_digest.pdf")

    with tab2:
        st.subheader("Weekly Watchlist Reports")
        weeks = pd.DataFrame({
            'Week': ['Dec 4-8', 'Nov 27-Dec 1', 'Nov 20-24', 'Nov 13-17'],
            'New Additions': [3, 5, 2, 4],
            'Removed': [1, 2, 0, 3],
        })
        st.dataframe(weeks, use_container_width=True, hide_index=True)
        st.download_button("Download Latest", "report_content", "weekly_watchlist.pdf")

    with tab3:
        st.subheader("Generate Custom Report")
        ticker = st.text_input("Company Ticker")
        report_type = st.selectbox("Report Type", ["Deep Dive", "Acquirer Analysis", "Signal Summary"])
        if st.button("Generate Report"):
            st.info("Report generation started. You'll receive an email when ready.")


if __name__ == "__main__":
    main()
