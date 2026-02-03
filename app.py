import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO

# OPTIONAL: Uncomment if Tesseract not in PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

st.set_page_config(
    page_title="Website Content Compliance Checker",
    layout="wide"
)

# ================== HELPERS ==================

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

def extract_text_from_image(img_url):
    try:
        r = requests.get(img_url, timeout=10)
        img = Image.open(BytesIO(r.content))

        # Preprocess for better OCR
        img = img.convert("L")
        img = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2)

        return pytesseract.image_to_string(img, config="--psm 6").lower()
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

        progress_bar.progress(scanned / max_pages)
        counter_text.info(f"Pages scanned: {scanned} / {max_pages}")
        status_text.write(f"🔍 Scanning: {url}")

        soup, page_text = get_page_content(url)

        found_text = False
        found_image = False

        # ---- TEXT SEARCH ----
        if mode in ("Text only", "Text + Images"):
            found_text = search_text in page_text

        # ---- IMAGE SEARCH ----
        if mode in ("Images only", "Text + Images") and soup:
            for img in soup.find_all("img"):
                src = img.get("src")
                if not src:
                    continue

                img_url = urljoin(url, src)
                if search_text in extract_text_from_image(img_url):
                    found_image = True
                    break

        if found_text or found_image:
            results.append({
                "URL": url,
                "Found in Text": "Yes" if found_text else "No",
                "Found in Images": "Yes" if found_image else "No"
            })

        # ---- FIND NEW LINKS ----
        if soup:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"])
                if is_internal_link(base_url, link) and link not in visited:
                    queue.append(link)

    return results, scanned

# ================== UI ==================

st.title("🔍 Website Content Compliance Checker")
st.write(
    "Fast and accurate scanning of website content with selectable search modes."
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
            st.warning(f"⚠️ Found '{search_text}' on {len(results)} page(s).")
            st.dataframe(results, use_container_width=True)
        else:
            st.success(f"✅ '{search_text}' not found.")

