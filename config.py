"""
Auto Shorts Image Generator - Configuration
"""
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CHROME_PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profile")

# Chrome settings
CHROME_OPTIONS = {
    "user_data_dir": CHROME_PROFILE_DIR,
    "headless": False,
    "window_size": (1920, 1080),
    "disable_automation": True,
}

# AI Provider settings
DEFAULT_AI_PROVIDER = "gemini"  # "gemini" veya "grok"

# Gemini settings
GEMINI_URL = "https://gemini.google.com/app"
GEMINI_SELECTORS = {
    # Input alanı
    "prompt_input": 'div[contenteditable="true"].ql-editor',
    "prompt_input_alt": 'p[data-placeholder="Enter a prompt here"]',
    "rich_text_editor": 'rich-textarea',

    # Gönder butonu
    "send_button": 'button[data-test-id="send-button"]',
    "send_button_alt": 'button[aria-label="Send message"]',

    # Görsel indirme - İKİ ADIMLI
    "download_dropdown_button": 'button[data-test-id="download-generated-image-button"]',
    "download_button": 'button[data-test-id="image-download-button"]',

    # Görsel yükleme
    "upload_button": 'input[type="file"]',
    "image_upload_area": 'button[aria-label="Add image"]',

    # Görsel sonucu
    "generated_image": 'img[data-test-id="generated-image"]',
    "response_container": 'message-content',

    # Yeni chat
    "new_chat_button": 'button[aria-label="New chat"]',
}

# Grok settings
GROK_URL = "https://grok.com/"
GROK_SELECTORS = {
    # Input alanı
    "prompt_input": 'textarea[placeholder*="Ask"]',
    "prompt_input_alt": 'div[contenteditable="true"]',

    # Gönder butonu
    "send_button": 'button[type="submit"]',
    "send_button_alt": 'button[aria-label*="Send"]',

    # Görsel indirme
    "download_button": 'button[aria-label*="download" i]',

    # Yeni chat
    "new_chat_button": 'a[href="/i/grok"]',
}

# Timeouts (seconds)
TIMEOUTS = {
    "page_load": 30,
    "element_wait": 20,
    "image_generation": 180,  # Görsel üretimi uzun sürebilir (3 dakika)
    "video_generation": 180,  # Video üretimi daha uzun sürebilir (3 dakika)
    "download_wait": 10,
    "retry_delay": 3,
}

# Retry settings
MAX_RETRIES = 3

# Image settings
IMAGE_SUFFIX = "vertical 9:16 aspect ratio, portrait orientation, 1080x1920"
WATERMARK_REMOVAL_PROMPT = "Remove all watermarks from this image naturally"

# Flask settings
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5050
FLASK_DEBUG = True

# Logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(LOGS_DIR, "generator.log")

# ===========================================
# Gemini Pro Hesap Ayarları
# ===========================================
GEMINI_PRO_CONFIG_FILE = os.path.join(BASE_DIR, "gemini_pro_config.json")

# Varsayılan değerler (config dosyası yoksa kullanılır)
DEFAULT_GEMINI_PRO_CONFIG = {
    "total_accounts": 4,           # Toplam hesap sayısı
    "daily_limit_per_account": 3,  # Her hesabın günlük video limiti
}

def get_gemini_pro_config():
    """Gemini Pro config'ini oku (dosya yoksa varsayılanı döndür)"""
    import json
    if os.path.exists(GEMINI_PRO_CONFIG_FILE):
        try:
            with open(GEMINI_PRO_CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Eksik alanları varsayılanla doldur
                for key, value in DEFAULT_GEMINI_PRO_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except:
            pass
    return DEFAULT_GEMINI_PRO_CONFIG.copy()

def save_gemini_pro_config(config):
    """Gemini Pro config'ini kaydet"""
    import json
    with open(GEMINI_PRO_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    return True

# Dinamik değerler (config'den okunur)
def get_total_accounts():
    return get_gemini_pro_config()["total_accounts"]

def get_daily_limit():
    return get_gemini_pro_config()["daily_limit_per_account"]

def get_max_daily_videos():
    """Günlük maksimum video sayısı (hesap sayısı x limit)"""
    cfg = get_gemini_pro_config()
    return cfg["total_accounts"] * cfg["daily_limit_per_account"]
