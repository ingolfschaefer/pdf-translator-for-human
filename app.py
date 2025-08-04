import os
import json
import hashlib
from pathlib import Path
import streamlit as st
import pymupdf
from deep_translator import (
    ChatGptTranslator,
    OpenAICompatibleTranslator,
)
import logging
import argparse

# Constants
DEFAULT_PAGES_PER_LOAD = 2
DEFAULT_MODEL = "gemma3:12b"
DEFAULT_API_BASE = "http://localhost:11434/v1"

# Supported translators (only OpenAI-compatible now)
TRANSLATORS = {
    'OpenAI Compatible': OpenAICompatibleTranslator,
    'ChatGPT': ChatGptTranslator,
}

# Color options
COLOR_MAP = {
    "darkred": (0.8, 0, 0),
    "black": (0, 0, 0),
    "blue": (0, 0, 0.8),
    "darkgreen": (0, 0.5, 0),
    "purple": (0.5, 0, 0.5),
}

# Target language options for ChatGPT
LANGUAGE_OPTIONS = {
    "English": "en",
    "简体中文": "zh-CN",
    "繁體中文": "zh-TW",
    "日本語": "ja",
    "한국어": "ko",
    "Español": "es",
    "Français": "fr",
    "Deutsch": "de",
}

# Add source language options
SOURCE_LANGUAGE_OPTIONS = {
    "Deutsch": "de",
    "English": "en",
    "简体中文": "zh-CN",
    "繁體中文": "zh-TW",
    "日本語": "ja",
    "한국어": "ko",
    "Español": "es",
    "Français": "fr",
    "Auto": "auto",
}

# Global translation configuration (updated for OpenAI-only)
TRANSLATOR_CONFIG = {
    "type": "OpenAI Compatible",  # Default to OpenAI Compatible
    # OpenAI settings
    "openai": {
        "default_api_base": DEFAULT_API_BASE,
        "default_model": DEFAULT_MODEL,
        "default_api_key": ""  # Empty by default
    }
}

# Add argument parser
def parse_args():
    parser = argparse.ArgumentParser(description='PDF Translator Application')
    parser.add_argument(
        '--translator', 
        type=str, 
        choices=['openai', 'chatgpt'], 
        default='openai',
        help='Specify translator type: openai or chatgpt'
    )
    parser.add_argument(
        '--api-base',
        type=str,
        help='API base URL for the translator'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='API key for OpenAI compatible translator'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Model name for OpenAI compatible translator'
    )
    return parser.parse_args()

# Update TRANSLATOR_CONFIG based on command line arguments
def update_translator_config(args):
    global TRANSLATOR_CONFIG
    
    TRANSLATOR_CONFIG["type"] = "ChatGPT" if args.translator.lower() == "chatgpt" else "OpenAI Compatible"
    
    if args.api_base:
        TRANSLATOR_CONFIG["openai"]["default_api_base"] = args.api_base
    if args.api_key:
        TRANSLATOR_CONFIG["openai"]["default_api_key"] = args.api_key
    if args.model:
        TRANSLATOR_CONFIG["openai"]["default_model"] = args.model

def get_cache_dir():
    """Get or create cache directory"""
    cache_dir = Path('.cached')
    cache_dir.mkdir(exist_ok=True)
    return cache_dir

def get_cache_key(doc_info: dict, page_num: int, translator_name: str, target_lang: str, text_content: str):
    """Generate cache key for a specific page translation"""
    # 使用文档信息和页面内容的组合生成唯一标识
    content_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()[:8]
    doc_id = f"{doc_info.get('title', '')}_{doc_info.get('author', '')}_{doc_info.get('pagecount', '')}"
    doc_hash = hashlib.md5(doc_id.encode('utf-8')).hexdigest()[:8]
    return f"{doc_hash}_{content_hash}_page{page_num}_{translator_name}_{target_lang}.pdf"

def get_cached_translation(cache_key: str) -> pymupdf.Document:
    """Get cached translation if exists"""
    cache_path = get_cache_dir() / cache_key
    if cache_path.exists():
        try:
            return pymupdf.open(str(cache_path))
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            return None
    return None

def save_translation_cache(doc: pymupdf.Document, cache_key: str):
    """Save translation to cache"""
    cache_path = get_cache_dir() / cache_key
    doc.save(str(cache_path))  # 确保提供文件路径字符串

def translate_pdf_pages(doc, doc_bytes, start_page, num_pages, translator, text_color, translator_name, target_lang):
    """Translate specific pages of a PDF document with progress and caching"""
    # Log translator information
    logging.info(f"Using translator: {translator_name}, source: {translator._source}, target: {translator._target}")
    logging.info(f"Selected translator: {translator_name}, Class: {translator.__class__.__name__}")
    
    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])
    
    translated_pages = []
    total_pages = min(start_page + num_pages, doc.page_count) - start_page
    cache_hits = 0
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, page_num in enumerate(range(start_page, min(start_page + num_pages, doc.page_count))):
        status_text.text(f"Translating page {page_num + 1}...")
        
        # Extract text content for cache key
        page = doc[page_num]
        text_content = page.get_text("text")
        
        # Check cache first using text content
        cache_key = get_cache_key(
            doc.metadata,
            page_num,
            translator_name,
            target_lang,
            text_content
        )
        
        cached_doc = get_cached_translation(cache_key)
        
        if cached_doc is not None:
            translated_pages.append(cached_doc)
            cache_hits += 1
            logging.info(f"Cache hit: Using cached translation for page {page_num + 1}")
            status_text.text(f"Using cached translation for page {page_num + 1}")
        else:
            logging.info(f"Cache miss: Translating page {page_num + 1}")
            status_text.text(f"Translating page {page_num + 1} (not in cache)")
            
            # Create a new PDF document for this page
            new_doc = pymupdf.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            page = new_doc[0]
            
            # Extract and translate text blocks
            blocks = page.get_text("blocks", flags=pymupdf.TEXT_DEHYPHENATE)
            
            for block in blocks:
                bbox = block[:4]
                text = block[4]
                translated = translator.translate(text)
                translated = str(translated)  # Ensure the value is a string
                
                # Cover original text with white and add translation in color
                page.draw_rect(bbox, color=None, fill=WHITE)
                page.insert_htmlbox(
                    bbox,
                    translated,
                    css=f"* {{font-family: sans-serif; color: rgb({int(rgb_color[0]*255)}, {int(rgb_color[1]*255)}, {int(rgb_color[2]*255)});}}"
                )
            
            # Save to cache
            save_translation_cache(new_doc, cache_key)
            translated_pages.append(new_doc)
            logging.info(f"Cached new translation for page {page_num + 1}")
        
        # Update progress
        progress = (i + 1) / total_pages
        progress_bar.progress(progress)
    
    # Clear progress indicators and show summary
    progress_bar.empty()
    if cache_hits > 0:
        st.info(f"Used cache for {cache_hits} out of {total_pages} pages")
    
    return translated_pages

def get_page_image(page, scale=2):
    """Get high quality image from PDF page"""
    # 计算缩放后的尺寸
    zoom = scale
    mat = pymupdf.Matrix(zoom, zoom)
    
    # 使用较低分辨率渲染页面，但保持清晰度
    pix = page.get_pixmap(
        matrix=mat,
        alpha=False,
        colorspace="rgb",  # Use RGB instead of RGBA
    )
    
    return pix

def translate_all_pages(
    input_doc,
    output_doc,
    translator,
    progress_bar,
    batch_size=1,
    **kwargs
):
    """Translate all pages of the PDF document"""
    # Log translator information for full document translation
    logging.info(f"Starting full document translation with: {kwargs.get('translator_name', 'unknown')}")
    logging.info(f"Translator settings - source: {translator._source}, target: {translator._target}")
    
    # Define colors
    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(kwargs.get('text_color', 'darkred').lower(), COLOR_MAP["darkred"])
    
    total_pages = input_doc.page_count
    
    # Create a progress bar for overall progress
    status_text = st.empty()
    
    # Translate all pages using translate_pdf_pages
    translated_pages = translate_pdf_pages(
        input_doc,
        None,  # doc_bytes not needed as we're using text content for cache
        0,  # start from first page
        total_pages,  # translate all pages
        translator,
        kwargs.get('text_color', 'darkred'),
        kwargs.get('translator_name', 'OpenAI Compatible'),
        kwargs.get('target_lang', 'zh-CN')
    )
    
    # Combine all pages into one PDF with compression
    output_path = kwargs.get('output_path', 'output.pdf')
    for trans_doc in translated_pages:
        output_doc.insert_pdf(trans_doc)
    
    # Save with compression options (removed linear=True due to compatibility issues)
    try:
        output_doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True
        )
    except Exception as e:
        # Fallback to basic save if compression options fail
        logging.warning(f"Failed to save with compression options: {e}")
        output_doc.save(output_path)
    
    return output_doc

def init_session_state():
    """Initialize session state variables"""
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'translation_started' not in st.session_state:
        st.session_state.translation_started = True
    if 'all_translated' not in st.session_state:
        st.session_state.all_translated = False
    if 'translated_doc' not in st.session_state:
        st.session_state.translated_doc = None
    if 'previous_file' not in st.session_state:
        st.session_state.previous_file = None
    if 'api_settings' not in st.session_state:
        st.session_state.api_settings = {}

def create_translator(translator_type, source_lang, target_lang_code, api_settings):
    """Create translator instance with proper error handling for empty API key"""
    try:
        if translator_type == "ChatGPT":
            api_key = api_settings.get('api_key', '').strip()
            if not api_key:
                st.error("API Key is required for ChatGPT translator. Please provide a valid API key.")
                return None
            
            return ChatGptTranslator(
                source=source_lang,
                target=target_lang_code,
                api_key=api_key,
                base_url=api_settings.get('api_base'),
                model=api_settings.get('model')
            )
        else:  # OpenAI Compatible
            api_key = api_settings.get('api_key', '').strip()
            # For OpenAI Compatible, empty API key might be acceptable for some local servers
            return OpenAICompatibleTranslator(
                source=source_lang,
                target=target_lang_code,
                api_key=api_key if api_key else None,
                base_url=api_settings.get('api_base'),
                model=api_settings.get('model')
            )
    except Exception as e:
        st.error(f"Failed to create translator: {str(e)}")
        return None

def main():
    st.set_page_config(layout="wide", page_title="PDF Translator for Human")
    st.title("PDF Translator for Human")

    # Initialize session state
    init_session_state()

    # Sidebar configuration
    with st.sidebar:
        st.header("Settings")
        
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        
        # Reset session state when a new file is uploaded
        if uploaded_file is not None and (st.session_state.previous_file is None or 
                                        uploaded_file.name != st.session_state.previous_file):
            st.session_state.current_page = 0
            st.session_state.translation_started = True
            st.session_state.all_translated = False
            st.session_state.translated_doc = None
            st.session_state.previous_file = uploaded_file.name
            st.rerun()
            
        # Add source language selection
        source_lang_name = st.selectbox(
            "Source Language",
            options=list(SOURCE_LANGUAGE_OPTIONS.keys()),
            index=0  # Default to German
        )
        source_lang = SOURCE_LANGUAGE_OPTIONS[source_lang_name]
        
        pages_per_load = st.number_input(
            "Pages per load",
            min_value=1,
            max_value=5,
            value=DEFAULT_PAGES_PER_LOAD
        )
        
        text_color = st.selectbox(
            "Translation Color",
            options=list(COLOR_MAP.keys()),
            index=0
        )
        
        target_lang = st.selectbox(
            "Target Language",
            options=list(LANGUAGE_OPTIONS.keys()),
            index=0  # Default to English
        )
        target_lang_code = LANGUAGE_OPTIONS[target_lang]
        
        # Add translator selection (only OpenAI-compatible options now)
        st.subheader("Translator Settings")
        translator_type = st.radio(
            "Translator",
            options=["OpenAI Compatible", "ChatGPT"],
            index=0
        )
        
        # API Configuration for OpenAI-compatible translators
        api_key = st.text_input(
            "API Key",
            value=TRANSLATOR_CONFIG["openai"]["default_api_key"],
            type="password",
            help="Leave empty if your local server doesn't require authentication"
        )
        api_base = st.text_input(
            "API Base URL",
            value=TRANSLATOR_CONFIG["openai"]["default_api_base"]
        )
        model = st.text_input(
            "Model Name",
            value=TRANSLATOR_CONFIG["openai"]["default_model"]
        )
        
        # Store API settings
        st.session_state.api_settings.update({
            'api_key': api_key,
            'api_base': api_base,
            'model': model
        })

    # Main content area
    if uploaded_file is not None:
        doc_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=doc_bytes)
        
        # Create two columns for side-by-side display
        col1, col2 = st.columns(2)
        
        # Display original pages
        with col1:
            st.header("Original")
            for page_num in range(st.session_state.current_page,
                                min(st.session_state.current_page + pages_per_load, doc.page_count)):
                page = doc[page_num]
                pix = get_page_image(page)
                st.image(pix.tobytes(), caption=f"Page {page_num + 1}", use_container_width=True)
        
        # Translation column
        with col2:
            st.header("Translated")
            
            # Create translator
            translator = create_translator(translator_type, source_lang, target_lang_code, st.session_state.api_settings)
            
            if translator is None:
                st.error("Cannot create translator. Please check your settings.")
            else:
                try:
                    # Translate current batch of pages
                    translated_pages = translate_pdf_pages(
                        doc,
                        doc_bytes,
                        st.session_state.current_page,
                        pages_per_load,
                        translator,
                        text_color,
                        translator_type,
                        target_lang_code
                    )
                    
                    # Display translated pages
                    for i, trans_doc in enumerate(translated_pages):
                        page = trans_doc[0]
                        pix = get_page_image(page)
                        st.image(pix.tobytes(), caption=f"Page {st.session_state.current_page + i + 1}", use_container_width=True)
                
                except Exception as e:
                    st.error(f"Translation error: {str(e)}")
                    logging.error(f"Translation error: {str(e)}")
                    return

        # Navigation and action buttons
        st.markdown("---")  # Add a separator
        button_col1, button_col2, button_col3, button_col4 = st.columns(4)
        
        # Previous Pages button
        with button_col1:
            if st.session_state.current_page > 0:
                if st.button("Previous Pages", use_container_width=True):
                    st.session_state.current_page = max(0, st.session_state.current_page - pages_per_load)
                    st.rerun()
            else:
                st.button("Previous Pages", disabled=True, use_container_width=True)
        
        # Next Pages button
        with button_col2:
            if st.session_state.current_page + pages_per_load < doc.page_count:
                if st.button("Next Pages", use_container_width=True):
                    st.session_state.current_page = min(
                        doc.page_count - 1,
                        st.session_state.current_page + pages_per_load
                    )
                    st.rerun()
            else:
                st.button("Next Pages", disabled=True, use_container_width=True)
        
        # Translate All button
        with button_col3:
            if st.button("Translate All", 
                        disabled=st.session_state.all_translated,
                        use_container_width=True):
                # Create translator for full translation
                translator = create_translator(translator_type, source_lang, target_lang_code, st.session_state.api_settings)
                
                if translator is None:
                    st.error("Cannot create translator for full translation. Please check your settings.")
                else:
                    try:
                        # Translate all pages
                        output_doc = pymupdf.open()
                        output_path = f"translated_{uploaded_file.name}"
                        output_doc = translate_all_pages(
                            doc,
                            output_doc,
                            translator,
                            st.empty(),
                            pages_per_load,
                            text_color=text_color,
                            translator_name=translator_type,
                            target_lang=target_lang_code,
                            output_path=output_path
                        )
                        
                        st.session_state.all_translated = True
                        st.session_state.translated_doc = output_path
                        st.rerun()
                    except Exception as e:
                        st.error(f"Translation error: {str(e)}")
                        logging.error(f"Translation error: {str(e)}")
                        return
        
        # Download button
        with button_col4:
            if not st.session_state.all_translated:
                st.markdown(
                    """
                    <div title="You can download the translated file after all content has been translated">
                        <button style="width: 100%" disabled>Download</button>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                with open(st.session_state.translated_doc, "rb") as file:
                    st.download_button(
                        "Download",
                        file,
                        file_name=f"translated_{uploaded_file.name}",
                        mime="application/pdf",
                        use_container_width=True
                    )
    else:
        st.info("Please upload a PDF file to begin translation")

    # Usage examples
    st.markdown("---")
    st.markdown("### Usage Examples")
    st.code("""
    # Using Ollama (default, no API key needed):
    streamlit run app.py --translator openai --api-base http://localhost:11434/v1 --model gemma2:12b

    # Using ChatGPT with API key:
    streamlit run app.py --translator chatgpt --api-key sk-your-key --api-base https://api.openai.com/v1 --model gpt-4o-mini

    # Using other local LLM server:
    streamlit run app.py --translator openai --model your-model --api-base http://localhost:8080/v1
    """)

if __name__ == "__main__":
    args = parse_args()
    update_translator_config(args)
    main()