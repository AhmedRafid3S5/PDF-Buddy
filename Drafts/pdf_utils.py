import streamlit as st
import io
from pypdf import PdfReader

try:
    from streamlit_pdf_viewer import pdf_viewer
except Exception:
    pdf_viewer = None


class PDFUtils:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def _read_pdf_structure(pdf_bytes):
        reader = PdfReader(io.BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
        toc_entries = PDFUtils._extract_outline_entries(reader)
        return total_pages, toc_entries

    @staticmethod
    def _extract_outline_entries(reader):
        entries = []

        def walk(items, level=0):
            for item in items:
                if isinstance(item, list):
                    walk(item, level + 1)
                    continue

                title = None
                if hasattr(item, "title"):
                    title = item.title
                elif isinstance(item, dict):
                    title = item.get("/Title")

                if not title:
                    continue

                try:
                    page = reader.get_destination_page_number(item) + 1
                except Exception:
                    continue

                entries.append(
                    {"title": str(title), "page": int(page), "level": int(level)}
                )

        try:
            walk(reader.outline)
        except Exception:
            return []

        return entries

    @staticmethod
    def _on_toc_change(option_to_page: dict):
        """Called immediately when the TOC selectbox changes — no form submit needed."""
        label = st.session_state.get("pdf_toc_select", "(None)")
        if label != "(None)" and label in option_to_page:
            st.session_state.pdf_current_page = int(option_to_page[label])
            # Switch to single-page mode for faster rendering on TOC jump
            st.session_state.pdf_render_mode = "Current page only (faster)"

    @staticmethod
    def pdf_viewer():
        st.subheader("PDF Viewer")

        # --- Session state defaults ---
        if "pdf_bytes" not in st.session_state:
            st.session_state.pdf_bytes = None
        if "pdf_file_id" not in st.session_state:
            st.session_state.pdf_file_id = None
        if "pdf_current_page" not in st.session_state:
            st.session_state.pdf_current_page = 1
        if "pdf_render_mode" not in st.session_state:
            st.session_state.pdf_render_mode = "Current page only (faster)"
        if "pdf_zoom_level" not in st.session_state:
            st.session_state.pdf_zoom_level = "auto"

        # --- Upload ---
        upload_file = st.sidebar.file_uploader("Upload a PDF", type=["pdf"])

        if upload_file is not None:
            current_file_id = (upload_file.name, upload_file.size)
            if st.session_state.pdf_file_id != current_file_id:
                st.session_state.pdf_bytes = upload_file.getvalue()
                st.session_state.pdf_file_id = current_file_id
                st.session_state.pdf_current_page = 1
                # Reset TOC selector when a new file is loaded
                if "pdf_toc_select" in st.session_state:
                    st.session_state.pdf_toc_select = "(None)"

        if not st.session_state.pdf_bytes:
            st.info("Upload a PDF to start viewing.")
            return

        pdf_bytes = st.session_state.pdf_bytes

        # --- Read structure ---
        try:
            total_pages, toc_entries = PDFUtils._read_pdf_structure(pdf_bytes)
        except Exception as error:
            st.error(f"Unable to read PDF structure: {error}")
            return

        max_pages = max(1, total_pages)
        st.session_state.pdf_current_page = min(
            max(1, st.session_state.pdf_current_page),
            max_pages,
        )

        # --- Build TOC labels ---
        option_labels = []
        option_to_page = {}
        for entry in toc_entries:
            indent = "  " * entry["level"]
            label = f"{indent}{entry['title']} (p.{entry['page']})"
            option_labels.append(label)
            option_to_page[label] = entry["page"]

        # --- TOC selectbox OUTSIDE the form — triggers on_change instantly ---
        if option_labels:
            st.sidebar.markdown("### Table of Contents")
            st.sidebar.selectbox(
                "Jump to section",
                ["(None)"] + option_labels,
                key="pdf_toc_select",
                on_change=PDFUtils._on_toc_change,
                args=(option_to_page,),
            )
        else:
            st.sidebar.info("No embedded bookmarks found.")

        # --- Sidebar navigation form (page controls only) ---
        with st.sidebar.form("pdf_navigation_form"):
            st.markdown("### Navigation")
            st.caption(
                f"Current page: {int(st.session_state.pdf_current_page)} / {max_pages}"
            )

            page_input = st.number_input(
                "Go to page",
                min_value=1,
                max_value=max_pages,
                value=int(st.session_state.pdf_current_page),
                step=1,
            )

            jump_step = st.selectbox("Quick jump step", [5, 10, 25], index=1)

            render_mode = st.selectbox(
                "Rendering mode",
                ["Current page only (faster)", "Full document"],
                index=0
                if st.session_state.pdf_render_mode == "Current page only (faster)"
                else 1,
            )

            zoom_options = ["auto", "auto-height", "50%", "75%", "100%", "125%", "150%"]
            current_zoom = (
                st.session_state.pdf_zoom_level
                if st.session_state.pdf_zoom_level in zoom_options
                else "auto"
            )
            zoom_choice = st.selectbox(
                "Zoom level",
                zoom_options,
                index=zoom_options.index(current_zoom),
            )

            col1, col2 = st.columns(2)
            prev_page = col1.form_submit_button("Previous")
            next_page = col2.form_submit_button("Next")

            col3, col4 = st.columns(2)
            jump_back = col3.form_submit_button(f"-{jump_step} pages")
            jump_forward = col4.form_submit_button(f"+{jump_step} pages")

            apply_navigation = st.form_submit_button("Apply")

        # --- Handle navigation form events ---
        if prev_page or next_page or jump_back or jump_forward or apply_navigation:
            st.session_state.pdf_render_mode = render_mode
            st.session_state.pdf_zoom_level = zoom_choice

            current_page = int(st.session_state.pdf_current_page)

            if prev_page:
                st.session_state.pdf_current_page = current_page - 1
            elif next_page:
                st.session_state.pdf_current_page = current_page + 1
            elif jump_back:
                st.session_state.pdf_current_page = current_page - int(jump_step)
            elif jump_forward:
                st.session_state.pdf_current_page = current_page + int(jump_step)
            else:
                st.session_state.pdf_current_page = int(page_input)

            st.session_state.pdf_current_page = min(
                max(1, int(st.session_state.pdf_current_page)),
                max_pages,
            )

        # --- Render PDF ---
        # Stable key prevents component remount when only page/scroll changes.
        viewer_key = f"pdf_viewer_{hash(st.session_state.pdf_file_id)}"

        if pdf_viewer:
            zoom_param = st.session_state.pdf_zoom_level
            if isinstance(zoom_param, str) and zoom_param.endswith("%"):
                zoom_level = float(zoom_param.strip("%")) / 100.0
            else:
                zoom_level = zoom_param

            if st.session_state.pdf_render_mode == "Current page only (faster)":
                pdf_viewer(
                    input=pdf_bytes,
                    key=viewer_key,
                    width="100%",
                    height=900,
                    pages_to_render=[int(st.session_state.pdf_current_page)],
                    scroll_to_page=int(st.session_state.pdf_current_page),
                    scroll_behavior="instant",
                    zoom_level=zoom_level,
                    show_page_separator=False,
                )
            else:
                pdf_viewer(
                    input=pdf_bytes,
                    key=viewer_key,
                    width="100%",
                    height=900,
                    scroll_to_page=int(st.session_state.pdf_current_page),
                    scroll_behavior="instant",
                    zoom_level=zoom_level,
                    show_page_separator=False,
                )
        else:
            st.warning(
                "streamlit-pdf-viewer unavailable. Falling back to st.pdf without TOC jumping."
            )
            st.pdf(pdf_bytes, height=700)
