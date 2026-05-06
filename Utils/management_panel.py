import os
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from Agent.db_manager import clear_database

load_dotenv("configs.env")

save_dir = os.getenv("SAVE_DIR", "Data")
chroma_path = os.getenv("CHROMA_PATH", "Chroma")


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def _get_dir_size(path: str) -> int:
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                continue
    return total


def _list_pdf_files(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []

    entries: list[dict] = []
    for name in os.listdir(path):
        if not name.lower().endswith(".pdf"):
            continue
        file_path = os.path.join(path, name)
        if not os.path.isfile(file_path):
            continue
        try:
            stats = os.stat(file_path)
        except OSError:
            continue
        entries.append(
            {
                "name": name,
                "path": file_path,
                "size": stats.st_size,
                "modified": stats.st_mtime,
            }
        )

    entries.sort(key=lambda item: item["modified"], reverse=True)
    return entries


def _delete_pdf(file_path: str) -> bool:
    try:
        os.remove(file_path)
    except OSError as exc:
        st.error(f"Unable to delete file: {exc}")
        return False
    return True


def _render_file_row(file_item: dict):
    icon_html = (
        "<div style=\"font-weight:700;font-size:12px;"
        "color:#0f172a;background:#dbeafe;border-radius:6px;"
        "padding:4px 6px;display:inline-block;margin-bottom:6px;\">"
        "PDF"
        "</div>"
    )

    name = file_item["name"]
    size = _format_bytes(int(file_item["size"]))
    modified = datetime.fromtimestamp(file_item["modified"]).strftime(
        "%Y-%m-%d %H:%M"
    )

    icon_col, name_col, meta_col, action_col = st.columns([1, 5, 3, 2], gap="small")

    with icon_col:
        st.markdown(icon_html, unsafe_allow_html=True)

    with name_col:
        st.markdown(f"**{name}**")

    with meta_col:
        st.caption(f"Modified: {modified}")
        st.caption(f"Size: {size}")

    with action_col:
        if st.button("🗑️ Delete", key=f"delete_{name}"):
            if _delete_pdf(file_item["path"]):
                st.success(f"Deleted {name}")
                st.rerun()

def _get_dir_mtime(path: str) -> float:
    """Return the latest mtime among the directory itself and its PDF files."""
    if not os.path.exists(path):
        return 0.0
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    for name in os.listdir(path):
        if not name.lower().endswith(".pdf"):
            continue
        try:
            mtime = max(mtime, os.path.getmtime(os.path.join(path, name)))
        except OSError:
            continue
    return mtime


def render_management_panel():
    st.subheader("Data & Cache Manager")

    st.markdown(
        "Manage stored PDFs and clear the Chroma cache when needed. "
        "Deleting a PDF here does not remove it from the Chroma database."
    )

    chroma_size = _format_bytes(_get_dir_size(chroma_path))

    st.markdown("#### Chroma Cache")
    st.caption(f"Current cache size: {chroma_size}")

    confirm_clear = st.checkbox("I understand this deletes the Chroma cache.")
    if st.button("Clear Chroma cache"):
        if confirm_clear:
            clear_database()
            st.success("Chroma cache cleared.")
            st.rerun()
        else:
            st.warning("Please confirm before clearing the cache.")

    st.markdown("#### Stored PDFs")
    
    col_spacer, col_refresh = st.columns([9, 2], gap="small")
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_pdf_list"):
            st.rerun()

    pdf_files = _list_pdf_files(save_dir)
    if not pdf_files:
        st.info("No PDFs found in the Data directory.")
        return

    for file_item in pdf_files:
        _render_file_row(file_item)
