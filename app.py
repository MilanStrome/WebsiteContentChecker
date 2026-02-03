import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO

# OPTIONAL: Uncomment if Tesseract not in PATH (mainly for local Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ================== STREAMLIT CONFIG ==================
st.set_page_config(
    page_title="Website Content Checker",
    layout="wide"
)

# ================== HELPER FUNCTIONS ==================

def is_internal_link(base_url, link):
    return urlparse(link).netloc == urlparse(base_url).netloc

def get_page_content(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ").lower()
        return soup, text
    except:
        return None, ""

def count_occurrences(text, keyword):
    if not text:
        return 0
    return text.count(keyword)

def extract_text_from_image(img_url):
    try:
        r = requests.get(img_url, timeout=10)
        img = Image.open(BytesIO(r.content))

        # OCR preprocessing
        img = img.convert("L")
        img = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2)

        return pytesseract.image_to_string(
            img,
            config="--psm 6"
        ).lower()
    except:
        return ""

# ================== SCANNER ==================

def scan_website(
    base_url,
    search_text,
    mode,
    max_pages,
    progress_bar,
    status_text,
    counter_text
):
    visited = set()
    queue = deque([base_url])
    results = []
    scanned = 0

    while queue and scanned < max_pages:
        url = queue.popleft()
        if url in visited:
            continue

        visited.add(url)
        scanned += 1

        # ---- LIVE UI UPDATES ----
        progress_bar.progress(scanned / max_pages)
        counter_text.info(f"Pages scanned: {scanned} / {max_pages}")
        status_text.write(f"🔍 Scanning: {url}")

        soup, page_text = get_page_content(url)

        text_count = 0
        image_count = 0

        # ---- TEXT SEARCH ----
        if mode in ("Text only", "Text + Images"):
            text_count = count_occurrences(page_text, search_text)

        # ---- IMAGE SEARCH ----
        if mode in ("Images only", "Text + Images") and soup:
            for img in soup.find_all("img"):
                src = img.get("src")
                if not src:
                    continue

                img_url = urljoin(url, src)
                ocr_text = extract_text_from_image(img_url)
                image_count += count_occurrences(ocr_text, search_text)

        if text_count > 0 or image_count > 0:
            results.append({
                "URL": url,
                "Found in Text": "Yes" if text_count > 0 else "No",
                "Text Count": text_count,
                "Found in Images": "Yes" if image_count > 0 else "No",
                "Image Count": image_count,
                "Total Count": text_count + image_count
            })

        # ---- DISCOVER NEW LINKS ----
        if soup:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"])
                if is_internal_link(base_url, link) and link not in visited:
                    queue.append(link)

    return results, scanned

# ================== UI ==================

st.title("🔍 Website Content Compliance Checker")
st.write(
    "Scan an entire website for a specific word or phrase. "
    "Counts how many times it appears in page text and images."
)

st.divider()

website_url = st.text_input(
    "Website URL",
    value="https://www.rvappstudios.com/"
)

search_text = st.text_input(
    "Text or phrase to search",
    value="kids"
)

search_mode = st.radio(
    "Search mode",
    ["Text only", "Images only", "Text + Images"],
    help="Text-only is fastest. Image scanning (OCR) is slower."
)

max_pages = st.slider(
    "Maximum pages to scan",
    1,
    500,
    150
)

st.divider()

if st.button("🚀 Start Scan"):
    if not website_url or not search_text:
        st.error("Please enter website URL and search text.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        counter_text = st.empty()

        with st.spinner("Scanning website…"):
            results, scanned = scan_website(
                website_url.rstrip("/"),
                search_text.lower(),
                search_mode,
                max_pages,
                progress_bar,
                status_text,
                counter_text
            )

        progress_bar.empty()
        status_text.empty()
        counter_text.empty()

        st.success(f"Scan complete. Pages scanned: {scanned}")

        if results:
            total_text = sum(r["Text Count"] for r in results)
            total_images = sum(r["Image Count"] for r in results)

            st.info(
                f"🔢 Total occurrences — "
                f"Text: {total_text} | "
                f"Images: {total_images} | "
                f"Overall: {total_text + total_images}"
            )

            st.warning(
                f"⚠️ Found **'{search_text}'** on {len(results)} page(s)."
            )

            st.dataframe(results, use_container_width=True)
        else:
            st.success(f"✅ '{search_text}' not found on scanned pages.")


