import os
import re
import streamlit as st
from Pdf_qa.pdf_loader import PDFUtils
from .db_manager import *
from .rag import *
from dotenv import load_dotenv

load_dotenv("configs.env")

save_dir = os.getenv("SAVE_DIR","Data")


def normalize_math(text: str) -> str:
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    return text

def summarize_pages_from(start_page, end_page):
    current_page = PDFUtils.get_current_page()
    save_path = PDFUtils.split_pdf(start_page,end_page,save_dir)
    return (
        f"Summarize pages from {int(start_page)} to {int(end_page)}. "
        f"Current page: {current_page}."
        f"Save path: {save_path}"
    )


def run_query_on_pages(start_page, end_page, query):
    #current_page = PDFUtils.get_current_page()
    save_path = PDFUtils.split_pdf(start_page,end_page,save_dir)
    
    if save_path:
        documents = load_documents()
        chunks = split_documents(documents)
        add_to_chroma(chunks)
        response_txt = query_rag(query)

        return response_txt
    else:
        return "Could not save to directory, so no response"
        



def render_agent_panel():
    if "ai_agent_output" not in st.session_state:
        st.session_state.ai_agent_output = ""
    if "agent_task" not in st.session_state:
        st.session_state.agent_task = "Ask about current page"

    current_page = PDFUtils.get_current_page()
    max_pages = PDFUtils.get_total_pages()

    st.markdown("<div style=\"margin-top:0.5rem;\"></div>", unsafe_allow_html=True)
    st.markdown("### AI Agent")
    st.selectbox(
        "Task",
        [
            "Ask about current page",
            "Select a page range"
        ],
        key="agent_task",
    )

    show_page_range = st.session_state.agent_task == "Select a page range"
    
    if show_page_range:
        if "agent_start_page" not in st.session_state:
            st.session_state.agent_start_page = current_page
        if "agent_end_page" not in st.session_state:
            st.session_state.agent_end_page = current_page

        start_col, end_col = st.columns([1, 1], gap="small")

        with start_col:
            st.number_input(
                "Start page",
                min_value=1,
                max_value=max_pages,
                key="agent_start_page",
            )

        with end_col:
            st.number_input(
                "End page",
                min_value=1,
                max_value=max_pages,
                key="agent_end_page",
            )

       
    else:
        apply_page_range = False



    agent_prompt = st.text_area(
        "Prompt",
        placeholder="Type your question or instruction...",
        height=140,
    )

    run_agent = st.button("Run agent", use_container_width=True)
    clear_agent = st.button("Clear output", use_container_width=True)

    output_area = st.empty()

    if run_agent:
        prompt_text = agent_prompt.strip() if agent_prompt else "(no prompt provided)"

        if show_page_range:
            start_page = int(st.session_state.agent_start_page)
            end_page = int(st.session_state.agent_end_page)
            if start_page > end_page:
                st.error("Start page must be less than or equal to end page.")
            else:
                with output_area:
                    with st.spinner("Generating response..."):
                        result = run_query_on_pages(start_page, end_page, prompt_text)
                if result:
                    st.session_state.ai_agent_output = result
                else:
                    st.session_state.ai_agent_output = (
                        "No response from backend. Please check the logs and try again."
                    )

        elif st.session_state.agent_task == "Ask about current page":
            #TODO : Test if this works correctly for full document render
            start_page = PDFUtils.get_current_page()
            end_page = start_page
            if start_page > end_page:
                st.error("Start page must be less than or equal to end page.")
            else:
                with output_area:
                    with st.spinner("Generating response..."):
                        result = run_query_on_pages(start_page, end_page, prompt_text)
                if result:
                    st.session_state.ai_agent_output = result
                else:
                    st.session_state.ai_agent_output = (
                        "No response from backend. Please check the logs and try again."
                    )
                
            
        #st.session_state.ai_agent_output = (
        #    f"Task: {st.session_state.agent_task}\n"
        #    f"Current page: {current_page} / {max_pages}\n"
        #    f"Prompt: {prompt_text}\n\n"
        #    "Agent backend is not connected yet. "
        #    "Wire this panel to your AI pipeline to return real answers."
        #)

    if clear_agent:
        st.session_state.ai_agent_output = ""

    st.markdown("#### Output")
    if st.session_state.ai_agent_output:
        output_area.markdown(normalize_math(st.session_state.ai_agent_output))
    else:
        output_area.caption("No output yet.")
