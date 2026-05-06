import streamlit as st
from Pdf_qa.pdf_loader import PDFUtils
from Utils.management_panel import render_management_panel
from Agent.agent_panel import render_agent_panel

st.set_page_config(page_title="PDF Buddy", layout="wide")

# Remove default Streamlit top/header spacing so content starts flush.
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-right: 0.5rem;
        padding-left: 1rem;
    }

    h1, h2, h3, h4, h5, h6 {
       
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
show_agent_panel = st.sidebar.checkbox("Show AI panel", value=True)
agent_width = st.sidebar.slider(
    "Agent panel width (%)",
    min_value=28,
    max_value=50,
    value=int(st.session_state.agent_panel_width),
    step=1,
    help="Drag to make the AI panel wider or narrower.",
    disabled=not show_agent_panel,
)
st.sidebar.markdown("------------------")
st.session_state.agent_panel_width = agent_width

if show_agent_panel:
    # Compute column ratios based on the chosen percentage
    agent_ratio = st.session_state.agent_panel_width
    viewer_ratio = 100 - agent_ratio

    viewer_col, agent_col = st.columns([viewer_ratio, agent_ratio], gap="small")

    with viewer_col:
        viewer_tab, manage_tab = st.tabs(["📄 PDF Viewer", "🗂️ Data & Cache"])

        with viewer_tab:
            PDFUtils.pdf_viewer()

        with manage_tab:
            render_management_panel()

    with agent_col:
        render_agent_panel()
else:
    viewer_tab, manage_tab = st.tabs(["📄 PDF Viewer", "🗂️ Data & Cache"])

    with viewer_tab:
        PDFUtils.pdf_viewer()

    with manage_tab:
        render_management_panel()