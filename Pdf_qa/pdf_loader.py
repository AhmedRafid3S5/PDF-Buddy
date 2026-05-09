import streamlit as st
import io
import base64
import fitz
from pypdf import PdfReader, PdfWriter
from Utils.image_encoder import pdf_pages_to_images
import json
import os


try:
    from streamlit_pdf_viewer import pdf_viewer
except Exception:
    pdf_viewer = None



class PDFUtils:
    @staticmethod
    def get_current_page(default=1):
        return int(st.session_state.get("pdf_current_page", default))

    @staticmethod
    def get_total_pages(default=1):
        return int(st.session_state.get("pdf_total_pages", default))
    
    @staticmethod
    def split_pdf(start_page, end_page, save_dir, output_name=None):
        
        pdf_bytes = st.session_state.get("pdf_bytes")
        if not pdf_bytes:
          st.toast("No pdf selected !!")
          raise ValueError("No PDF loaded in st.session_state.pdf_bytes")  
        
        reader = PdfReader(io.BytesIO(pdf_bytes))
        start_page = int(start_page)
        end_page = int(end_page)
        total_pages = PDFUtils.get_total_pages()
        pdf_name = st.session_state.get("pdf_name","unnamed").strip(".pdf")

        if start_page < 1:
            st.toast("Invalid start page value")
            raise ValueError("start_page must be at least 1")
        if end_page < start_page or end_page > total_pages:
            st.toast("Invalid end page value")
            raise ValueError("end_page must be greater than or equal to start_page")
        
        os.makedirs(save_dir, exist_ok=True)

        writer = PdfWriter()
        for page_index in range(start_page - 1 , end_page ):
            writer.add_page(reader.pages[page_index])

        if output_name is None:
            output_name = f"{pdf_name}_{start_page}_to_{end_page}.pdf"

        output_path = os.path.join(save_dir, output_name)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        #keep a base64 image copy of the splitted pdf, saved to 
        images = pdf_pages_to_images(output_path, 1, end_page - start_page + 1)
        page_map = {}
        for idx, img_b64 in enumerate(images, start=1):
            page_map[str(idx)] = img_b64
        
        sidecar_path = output_path.replace(".pdf", ".pages.json")
        with open(sidecar_path, "w", encoding="utf-8") as f:
             json.dump(page_map, f)
        
        return output_path

    @staticmethod
    def get_page_images(start_page, end_page, dpi=150):
        pdf_bytes = st.session_state.get("pdf_bytes")
        if not pdf_bytes:
            st.toast("No pdf selected !!")
            raise ValueError("No PDF loaded in st.session_state.pdf_bytes")

        start_page = int(start_page)
        end_page = int(end_page)
        total_pages = PDFUtils.get_total_pages()

        if start_page < 1:
            st.toast("Invalid start page value")
            raise ValueError("start_page must be at least 1")
        if end_page < start_page:
            st.toast("Invalid end page value")
            raise ValueError("end_page must be greater than or equal to start_page")
        if start_page > total_pages:
            return []

        last_page = min(end_page, total_pages)
        images: list[str] = []
        mat = fitz.Matrix(dpi / 72, dpi / 72)

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page_index in range(start_page - 1, last_page):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("jpeg")
                images.append(base64.b64encode(img_bytes).decode("ascii"))

        return images

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
    def pdf_viewer():

   
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
        if "pdf_total_pages" not in st.session_state:
            st.session_state.pdf_total_pages = 1
        if "pdf_name" not in st.session_state:
            st.session_state.pdf_name = None

        # --- Upload ---
        upload_file = st.sidebar.file_uploader("Upload a PDF", type=["pdf"])

        if upload_file is not None:
            current_file_id = (upload_file.name, upload_file.size)
            if st.session_state.pdf_file_id != current_file_id:
                st.session_state.pdf_bytes = upload_file.getvalue()
                st.session_state.pdf_file_id = current_file_id
                st.session_state.pdf_current_page = 1
                st.session_state.pdf_name = upload_file.name

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
        st.session_state.pdf_total_pages = max_pages
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

        # --- Sidebar navigation form ---
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
                if st.session_state.pdf_render_mode
                == "Current page only (faster)"
                else 1,
            )

            # Persisted zoom control
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

            selected_label = "(None)"
            if option_labels:
                st.markdown("### Table of Contents")
                selected_label = st.selectbox(
                    "Jump to section", ["(None)"] + option_labels
                )
            else:
                st.info("No embedded bookmarks found.")

            col1, col2 = st.columns(2)
            prev_page = col1.form_submit_button("Previous")
            next_page = col2.form_submit_button("Next")

            col3, col4 = st.columns(2)
            jump_back = col3.form_submit_button(f"-{jump_step} pages")
            jump_forward = col4.form_submit_button(f"+{jump_step} pages")

            apply_navigation = st.form_submit_button("Apply")

        # --- Handle navigation events ---
        if prev_page or next_page or jump_back or jump_forward or apply_navigation:
            st.session_state.pdf_render_mode = render_mode
            st.session_state.pdf_zoom_level = zoom_choice  # persist zoom

            current_page = int(st.session_state.pdf_current_page)

            if prev_page:
                st.session_state.pdf_current_page = current_page - 1
            elif next_page:
                st.session_state.pdf_current_page = current_page + 1
            elif jump_back:
                st.session_state.pdf_current_page = current_page - int(jump_step)
            elif jump_forward:
                st.session_state.pdf_current_page = current_page + int(jump_step)
            elif selected_label != "(None)":
                st.session_state.pdf_current_page = int(option_to_page[selected_label])
            else:
                st.session_state.pdf_current_page = int(page_input)

            st.session_state.pdf_current_page = min(
                max(1, int(st.session_state.pdf_current_page)),
                max_pages,
            )
            st.rerun()
   
        # --- Render PDF ---
        if pdf_viewer:
            # Decide zoom parameter: convert "125%" -> 1.25, keep "auto"/"auto-height"
            zoom_param = st.session_state.pdf_zoom_level
            if isinstance(zoom_param, str) and zoom_param.endswith("%"):
                zoom_level = float(zoom_param.strip("%")) / 100.0
            else:
                zoom_level = zoom_param  # "auto" or "auto-height" are supported [web:3][web:18]

            # Only pass pages_to_render in single-page mode, so in full mode
            # the component renders all pages by default [web:3].
            if st.session_state.pdf_render_mode == "Current page only (faster)":
                nav_left, nav_center, nav_right = st.columns([1, 6, 1], gap="small")
                with nav_left:
                    if st.button("◀", key="viewer_prev"):
                        st.session_state.pdf_current_page = max(
                            1, int(st.session_state.pdf_current_page) - 1
                        )
                        st.rerun()

                with nav_center:
                    st.markdown(
                        f"<div style=\"text-align:center;font-weight:600;\">"
                        f"Page {int(st.session_state.pdf_current_page)} / {max_pages}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with nav_right:
                    if st.button("▶", key="viewer_next"):
                        st.session_state.pdf_current_page = min(
                            max_pages, int(st.session_state.pdf_current_page) + 1
                        )
                        st.rerun()

                pdf_viewer(
                    input=pdf_bytes,
                    width="100%",
                    height=900,
                    pages_to_render=[int(st.session_state.pdf_current_page)],
                    scroll_to_page=int(st.session_state.pdf_current_page),
                    scroll_behavior="instant",
                    zoom_level=zoom_level,
                    show_page_separator=False,
                    render_text=True,  # <-- enable selectable text
                )
            else:
                # Full document: NO pages_to_render, so all pages show as a scrollable stream.
                pdf_viewer(
                    input=pdf_bytes,
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