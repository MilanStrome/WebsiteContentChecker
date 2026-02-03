import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import cv2
import numpy as np

# OPTIONAL: Uncomment if Tesseract not in PATH (Windows local)
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

# ---------- OCR (best-effort) ----------
def extract_text_from_image(img_url):
    try:
        r = requests.get(img_url, timeout=10)

        # Convert palette/transparency images safely
        img = Image.open(BytesIO(r.content)).convert("RGBA")

        # OCR preprocessing
        img = img.convert("L")
        img = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2)

        return pytesseract.image_to_string(
            img, config="--psm 6"
        ).lower()
    except:
        return ""

# ---------- Visual text detection (OCR-independent) ----------
def image_contains_text(img_url):
    try:
        r = requests.get(img_url, timeout=10)
        img_array = np.frombuffer(r.content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)

        thresh = cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            15,
            3
        )

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        text_like_regions = 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 20 < w < 500 and 10 < h < 200:
                text_like_regions += 1

        return text_like_regions >= 3
    except:
        return False

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

        progress_bar.progress(scanned / max_pages)
        counter_text.info(f"Pages scanned: {scanned} / {max_pages}")
        status_text.write(f"🔍 Scanning: {url}")

        soup, page_text = get_page_content(url)

        text_count = 0
        image_count = 0
        image_has_text = False

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

                # OCR count
                ocr_text = extract_text_from_image(img_url)
                image_count += count_occurrences(ocr_text, search_text)

                # Visual detection fallback
                if not image_has_text and image_contains_text(img_url):
                    image_has_text = True

        if text_count > 0 or image_count > 0 or image_has_text:
            results.append({
                "URL": url,
                "Found in Text": "Yes" if text_count > 0 else "No",
                "Text Count": text_count,
                "Found in Images (OCR)": "Yes" if image_count > 0 else "No",
                "Image Count": image_count,
                "Image Contains Text (Visual)": "Yes" if image_has_text else "No",
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

st.title("🔍 Website Content Checker")
st.write(
    "Scans an entire website for a word or phrase. "
    "Includes page text, OCR image text, and visual image-text detection."
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
    help="Text-only is fastest. Image scanning is slower."
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
                f"Images (OCR): {total_images}"
            )

            st.warning(
                f"⚠️ Found **'{search_text}'** on {len(results)} page(s)."
            )

            st.dataframe(results, use_container_width=True)
        else:
            st.success(f"✅ '{search_text}' not found on scanned pages.")
