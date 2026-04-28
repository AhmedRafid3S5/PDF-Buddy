import streamlit as st
from Pdf_qa.pdf_loader import PDFUtils
from Agent.agent_panel import render_agent_panel

st.set_page_config(page_title="PDF Buddy", layout="wide")

# Remove default Streamlit top/header spacing so content starts flush.
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0rem;
        padding-right: 0.5rem;
    }

    h1, h2, h3, h4, h5, h6 {
        margin-top: 0 !important;
        margin-right: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize agent panel width percentage (of total width)
if "agent_panel_width" not in st.session_state:
    st.session_state.agent_panel_width = 28  # start at 28%

# Optional: put the slider in the sidebar so it feels like a layout setting
st.sidebar.markdown("### Layout")
agent_width = st.sidebar.slider(
    "Agent panel width (%)",
    min_value=28,
    max_value=50,
    value=int(st.session_state.agent_panel_width),
    step=1,
    help="Drag to make the AI panel wider or narrower.",
)
st.session_state.agent_panel_width = agent_width

# Compute column ratios based on the chosen percentage
agent_ratio = st.session_state.agent_panel_width
viewer_ratio = 100 - agent_ratio

viewer_col, agent_col = st.columns([viewer_ratio, agent_ratio], gap="small")

with viewer_col:
    PDFUtils.pdf_viewer()

with agent_col:
    render_agent_panel()