"""
Gemini Pro Manager - Multi-Account Image & Video Generator
3 Gemini Pro hesabı ile görsel ve video oluşturma
Her hesap günde 3 video limiti
Mevcut generator.py gibi adım adım çalışır
"""
import os
import json
import time
import glob
import shutil
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import config

logger = logging.getLogger(__name__)

# Hesap limitleri
DAILY_VIDEO_LIMIT = 3
TOTAL_ACCOUNTS = 3

# Gemini Pro URL
GEMINI_URL = "https://gemini.google.com"

# Timeouts
TIMEOUTS = {
    'page_load': 15,
    'element_wait': 30,
    'image_generation': 120,  # 2 dakika
    'video_generation': 180,  # 3 dakika
    'download_wait': 10,
}


class GeminiProAccount:
    """Tek bir Gemini Pro hesabını temsil eder"""

    def __init__(self, account_id: int, profile_dir: str, progress_callback: Callable = None):
        self.account_id = account_id
        self.profile_dir = profile_dir
        self.driver = None
        self.wait = None
        self.daily_usage = 0
        self.last_usage_date = None
        self.download_dir = os.path.join(profile_dir, "downloads")
        self.progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))

        os.makedirs(self.download_dir, exist_ok=True)

    def _update_progress(self, message: str, percentage: int):
        """İlerleme güncelle"""
        logger.info(f"[Hesap {self.account_id}] [{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(f"Hesap {self.account_id}: {message}", percentage)

    def is_browser_alive(self) -> bool:
        """Tarayıcının hala açık ve çalışır durumda olup olmadığını kontrol et"""
        if not self.driver:
            return False
        try:
            # Basit bir komut çalıştır - eğer tarayıcı ölmüşse hata verir
            _ = self.driver.current_url
            return True
        except:
            return False

    def _cleanup_profile_locks(self):
        """Profil kilitleri temizle - orphaned Chrome oturumları için"""
        lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
        for lock_file in lock_files:
            lock_path = os.path.join(self.profile_dir, lock_file)
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
                    logger.info(f"Kilit dosyası silindi: {lock_path}")
            except Exception as e:
                logger.warning(f"Kilit dosyası silinemedi: {lock_path} - {e}")

    def close_browser(self):
        """Tarayıcıyı güvenli şekilde kapat"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.wait = None

    def start_browser(self) -> bool:
        """Tarayıcıyı başlat"""
        try:
            # Eğer tarayıcı zaten açık ve çalışıyorsa, yeniden başlatma
            if self.is_browser_alive():
                self._update_progress("Tarayıcı zaten açık", 10)
                return True

            self._update_progress("Tarayıcı başlatılıyor...", 5)

            # Eski tarayıcı varsa kapat
            self.close_browser()

            # Profil kilitleri temizle (orphaned sessions için)
            self._cleanup_profile_locks()

            os.makedirs(self.profile_dir, exist_ok=True)

            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_dir}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1200,900")

            # Download settings
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
            }
            options.add_experimental_option("prefs", prefs)

            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.wait = WebDriverWait(self.driver, TIMEOUTS['element_wait'])

            self._update_progress("Tarayıcı başlatıldı", 10)
            return True

        except Exception as e:
            logger.error(f"Hesap {self.account_id} tarayıcı hatası: {e}")
            # Hata durumunda profil kilitleri temizle ve tekrar dene
            self._cleanup_profile_locks()
            return False

    def navigate_to_gemini(self) -> bool:
        """Gemini sayfasına git ve login kontrolü yap"""
        try:
            self._update_progress("Gemini'ye gidiliyor...", 15)
            self.driver.get(GEMINI_URL)
            time.sleep(TIMEOUTS['page_load'])

            # Login kontrolü
            if "accounts.google.com" in self.driver.current_url:
                self._update_progress("Google girişi gerekiyor!", 15)
                # Kullanıcının giriş yapmasını bekle (max 2 dakika)
                for _ in range(24):
                    time.sleep(5)
                    if "gemini.google.com" in self.driver.current_url:
                        break
                else:
                    logger.warning(f"Hesap {self.account_id}: Login timeout")
                    return False

            self._update_progress("Gemini sayfası yüklendi", 20)
            return True

        except Exception as e:
            logger.error(f"Hesap {self.account_id} navigasyon hatası: {e}")
            return False

    def _find_input_element(self):
        """Prompt input alanını bul"""
        selectors = [
            (By.CSS_SELECTOR, 'div[contenteditable="true"].ql-editor'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"][data-placeholder]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"]'),
            (By.CSS_SELECTOR, 'rich-textarea'),
            (By.CSS_SELECTOR, 'textarea'),
            (By.XPATH, "//div[@contenteditable='true']"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except:
                continue

        raise NoSuchElementException("Prompt input alanı bulunamadı")

    def _find_send_button(self):
        """Gönder butonunu bul"""
        selectors = [
            (By.CSS_SELECTOR, 'button[data-test-id="send-button"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Send"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Gönder"]'),
            (By.CSS_SELECTOR, 'button.send-button'),
            (By.XPATH, "//button[contains(@aria-label,'Send')]"),
            (By.XPATH, "//button[contains(@aria-label,'Gönder')]"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except:
                continue

        return None

    def send_prompt(self, prompt: str) -> bool:
        """Prompt gönder"""
        try:
            self._update_progress(f"Prompt gönderiliyor: {prompt[:50]}...", 30)
            time.sleep(3)

            # Input bul ve tıkla
            input_element = self._find_input_element()
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_element)
            time.sleep(0.5)

            try:
                input_element.click()
            except:
                self.driver.execute_script("arguments[0].click();", input_element)
            time.sleep(0.5)

            # Temizle
            try:
                input_element.send_keys(Keys.COMMAND + "a")
                input_element.send_keys(Keys.DELETE)
            except:
                pass
            time.sleep(0.3)

            # Prompt yaz
            input_element.send_keys(prompt)
            time.sleep(1.5)

            # Gönder butonu
            send_button = self._find_send_button()
            sent = False

            if send_button:
                try:
                    send_button.click()
                    sent = True
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", send_button)
                        sent = True
                    except:
                        pass

            if not sent:
                input_element.send_keys(Keys.RETURN)

            self._update_progress("Prompt gönderildi", 35)
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Prompt gönderme hatası: {e}")
            return False

    def upload_image(self, image_path: str) -> bool:
        """Görseli Gemini'ye upload et"""
        try:
            self._update_progress(f"Görsel upload ediliyor: {os.path.basename(image_path)}", 40)

            # File input elementini bul
            file_input = None
            selectors = [
                'input[type="file"]',
                'input[accept*="image"]',
                'input[name*="file"]',
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        file_input = el
                        break
                    if file_input:
                        break
                except:
                    continue

            if not file_input:
                # Görünür olmayan file input'u JavaScript ile bul
                try:
                    file_input = self.driver.execute_script("""
                        var inputs = document.querySelectorAll('input[type="file"]');
                        if (inputs.length > 0) return inputs[0];
                        return null;
                    """)
                except:
                    pass

            if not file_input:
                # Upload butonu arayıp tıkla, sonra file input'u bul
                upload_buttons = [
                    (By.CSS_SELECTOR, 'button[aria-label*="Upload"]'),
                    (By.CSS_SELECTOR, 'button[aria-label*="Yükle"]'),
                    (By.CSS_SELECTOR, 'button[aria-label*="Add"]'),
                    (By.CSS_SELECTOR, 'button[aria-label*="Ekle"]'),
                    (By.CSS_SELECTOR, '[data-tooltip*="Upload"]'),
                    (By.XPATH, "//button[contains(@aria-label,'upload') or contains(@aria-label,'Upload')]"),
                    (By.CSS_SELECTOR, 'button.upload-button'),
                    (By.CSS_SELECTOR, '[class*="upload"]'),
                ]

                for by, selector in upload_buttons:
                    try:
                        buttons = self.driver.find_elements(by, selector)
                        for btn in buttons:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(1)
                                # Şimdi file input'u tekrar ara
                                file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                                break
                        if file_input:
                            break
                    except:
                        continue

            if not file_input:
                logger.warning("File input elementi bulunamadı, alternatif yöntem deneniyor...")
                # Alternatif: + butonuna tıkla
                try:
                    add_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="+"], button[aria-label*="Add"], .add-button')
                    for btn in add_buttons:
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(1)
                            break
                    file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                except Exception as e:
                    logger.error(f"Alternatif upload yöntemi de başarısız: {e}")
                    return False

            # Dosya yolunu gönder
            absolute_path = os.path.abspath(image_path)
            file_input.send_keys(absolute_path)

            self._update_progress("Görsel upload edildi", 45)
            time.sleep(3)  # Upload'ın tamamlanmasını bekle

            return True

        except Exception as e:
            logger.error(f"Görsel upload hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def upload_and_prompt(self, image_path: str, prompt: str) -> bool:
        """Görsel upload et ve prompt gönder - geliştirilmiş versiyon"""
        try:
            self._update_progress(f"Görsel upload ediliyor: {os.path.basename(image_path)}", 40)
            time.sleep(2)

            absolute_path = os.path.abspath(image_path)
            logger.info(f"Upload edilecek görsel: {absolute_path}")

            if not os.path.exists(absolute_path):
                logger.error(f"Görsel dosyası bulunamadı: {absolute_path}")
                return False

            uploaded = False

            # ===== YÖNTEM 1: File input'u direkt bul ve kullan =====
            try:
                logger.info("Yöntem 1: File input aranıyor...")
                # Önce gizli input'ları görünür yap
                self.driver.execute_script("""
                    document.querySelectorAll('input[type="file"]').forEach(function(input) {
                        input.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important; position:relative !important;';
                    });
                """)
                time.sleep(0.5)

                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                logger.info(f"Bulunan file input sayısı: {len(file_inputs)}")

                for fi in file_inputs:
                    try:
                        fi.send_keys(absolute_path)
                        uploaded = True
                        logger.info("✅ Yöntem 1: File input ile upload başarılı")
                        time.sleep(2)  # Upload'ın işlenmesini bekle
                        break
                    except Exception as e:
                        logger.debug(f"File input hatası: {e}")
                        continue
            except Exception as e:
                logger.debug(f"File input denemesi: {e}")

            # ===== YÖNTEM 2: + butonuna tıkla ve Upload file seç =====
            if not uploaded:
                try:
                    logger.info("Yöntem 2: + butonu aranıyor...")
                    # Gemini'deki + veya attachment butonu
                    plus_selectors = [
                        'button[aria-label*="Add"]',
                        'button[aria-label*="Ekle"]',
                        'button[aria-label*="attachment" i]',
                        'button[aria-label*="ek" i]',
                        '[data-test-id*="add"]',
                        '[class*="attachment"]',
                        '[class*="add-file"]',
                        'button[jsname] mat-icon',  # Material icon butonları
                    ]

                    for selector in plus_selectors:
                        try:
                            btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for btn in btns:
                                if btn.is_displayed():
                                    btn.click()
                                    logger.info(f"+ butonu tıklandı: {selector}")
                                    time.sleep(1)

                                    # File input tekrar kontrol et
                                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                                    for fi in file_inputs:
                                        try:
                                            fi.send_keys(absolute_path)
                                            uploaded = True
                                            logger.info("✅ Yöntem 2: + butonu sonrası file input başarılı")
                                            time.sleep(2)
                                            break
                                        except:
                                            continue
                                    if uploaded:
                                        break
                            if uploaded:
                                break
                        except:
                            continue
                except Exception as e:
                    logger.debug(f"+ butonu denemesi: {e}")

            # ===== YÖNTEM 3: Drag & Drop simülasyonu =====
            if not uploaded:
                try:
                    # Input alanını bul
                    input_area = self._find_input_element()
                    if input_area:
                        # JavaScript ile dosya input'u oluştur ve tetikle
                        self.driver.execute_script("""
                            var input = document.createElement('input');
                            input.type = 'file';
                            input.id = 'temp-file-input-gemini';
                            input.style.cssText = 'position:fixed; top:0; left:0; z-index:99999;';
                            document.body.appendChild(input);
                        """)
                        time.sleep(0.5)

                        temp_input = self.driver.find_element(By.ID, 'temp-file-input-gemini')
                        temp_input.send_keys(absolute_path)

                        # DataTransfer ile drop eventi simüle et
                        self.driver.execute_script("""
                            var input = document.getElementById('temp-file-input-gemini');
                            var file = input.files[0];
                            if (file) {
                                var dataTransfer = new DataTransfer();
                                dataTransfer.items.add(file);

                                var dropTarget = arguments[0];
                                var dropEvent = new DragEvent('drop', {
                                    bubbles: true,
                                    cancelable: true,
                                    dataTransfer: dataTransfer
                                });
                                dropTarget.dispatchEvent(dropEvent);
                            }
                            input.remove();
                        """, input_area)

                        time.sleep(2)
                        # Upload başarılı mı kontrol et
                        uploaded = True
                        logger.info("Yöntem 3: Drag & drop simülasyonu ile upload denendi")
                except Exception as e:
                    logger.debug(f"Drag & drop denemesi: {e}")

            # ===== YÖNTEM 4: Clipboard yapıştırma (macOS) =====
            if not uploaded:
                try:
                    logger.info("Yöntem 4: Clipboard yapıştırma deneniyor...")
                    import subprocess

                    # PNG olarak clipboard'a kopyala (JPEG yerine PNG daha iyi sonuç verebilir)
                    result = subprocess.run(['osascript', '-e',
                        f'set the clipboard to (read (POSIX file "{absolute_path}") as «class PNGf»)'],
                        capture_output=True, timeout=5)

                    if result.returncode != 0:
                        # JPEG dene
                        subprocess.run(['osascript', '-e',
                            f'set the clipboard to (read (POSIX file "{absolute_path}") as JPEG picture)'],
                            capture_output=True, timeout=5)

                    # Input alanına yapıştır
                    input_area = self._find_input_element()
                    if input_area:
                        input_area.click()
                        time.sleep(0.5)
                        # Cmd+V
                        from selenium.webdriver.common.keys import Keys
                        input_area.send_keys(Keys.COMMAND, 'v')
                        time.sleep(2)
                        uploaded = True
                        logger.info("✅ Yöntem 4: Clipboard yapıştırma denendi")
                except Exception as e:
                    logger.debug(f"Clipboard denemesi: {e}")

            if uploaded:
                time.sleep(3)  # Upload'ın tamamlanmasını bekle
                self._update_progress("Görsel yüklendi", 45)
            else:
                logger.error("❌ TÜM UPLOAD YÖNTEMLERİ BAŞARISIZ!")
                return False  # Upload başarısız olursa False dön

            # Input alanını bul ve prompt yaz
            input_element = self._find_input_element()
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_element)
            time.sleep(0.5)

            try:
                input_element.click()
            except:
                self.driver.execute_script("arguments[0].click();", input_element)
            time.sleep(0.5)

            # Prompt yaz
            input_element.send_keys(prompt)
            time.sleep(1.5)

            # Gönder
            send_button = self._find_send_button()
            sent = False

            if send_button:
                try:
                    send_button.click()
                    sent = True
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", send_button)
                        sent = True
                    except:
                        pass

            if not sent:
                input_element.send_keys(Keys.RETURN)

            status_msg = "Görsel ve prompt gönderildi" if uploaded else "Prompt gönderildi (görsel yüklenemedi)"
            self._update_progress(status_msg, 50)
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Upload ve prompt gönderme hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_generated_images(self) -> List:
        """Sayfadaki oluşturulmuş görselleri bul - Gemini'ye özgü"""
        images = []
        seen_srcs = set()

        # Gemini'ye özgü seçiciler - öncelik sırasına göre
        selectors = [
            # Gemini response içindeki görseller
            'model-response img',
            'message-content img',
            '[data-message-author-role="model"] img',
            'response-container img',

            # Blob ve hosted görseller
            'img[src^="blob:"]',
            'img[src*="googleusercontent"]',
            'img[src*="gstatic"]',
            'img[src*="ggpht"]',

            # Generated image container'lar
            '.generated-image img',
            '[class*="generated"] img',
            '[class*="image-container"] img',
            '[class*="media-container"] img',

            # Alt text ile
            'img[alt*="Generated"]',
            'img[alt*="generated"]',
            'img[alt*="Image"]',

            # Data attribute'lar
            'img[data-src*="googleusercontent"]',
            'img[data-image-url]',
        ]

        for selector in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for img in found:
                    try:
                        if not img.is_displayed():
                            continue

                        # Boyut kontrolü - çok küçük görselleri atla (icon vb.)
                        width = img.size.get('width', 0)
                        height = img.size.get('height', 0)
                        if width < 100 or height < 100:
                            continue

                        src = img.get_attribute('src') or img.get_attribute('data-src') or ''

                        # Avatar ve icon'ları atla
                        if any(x in src.lower() for x in ['avatar', 'icon', 'logo', 'profile']):
                            continue

                        # Daha önce eklenmediyse ekle
                        if src and src not in seen_srcs:
                            seen_srcs.add(src)
                            images.append(img)
                            logger.debug(f"Görsel bulundu: {src[:80]}... ({width}x{height})")
                    except:
                        continue
            except:
                continue

        logger.info(f"Toplam {len(images)} görsel bulundu")
        return images

    def _count_generated_images(self) -> int:
        """Sayfadaki görsel sayısını say"""
        return len(self._find_generated_images())

    def wait_for_image_generation(self, previous_count: int = 0) -> bool:
        """Yeni görsel oluşturulmasını bekle"""
        try:
            self._update_progress("Görsel oluşturuluyor, bekleniyor...", 40)

            max_wait = TIMEOUTS['image_generation']
            start_time = time.time()

            logger.info(f"Görsel bekleniyor - önceki sayı: {previous_count}")

            while time.time() - start_time < max_wait:
                current_count = self._count_generated_images()
                elapsed = int(time.time() - start_time)

                if current_count > previous_count:
                    self._update_progress(f"Görsel oluşturuldu! ({elapsed}s)", 50)
                    time.sleep(3)  # Görselin tam yüklenmesini bekle
                    return True

                # Loading kontrolü
                try:
                    loading = self.driver.find_elements(By.CSS_SELECTOR,
                        '.loading, .generating, [class*="loading"], [class*="progress"], [class*="spinner"]')
                    if loading:
                        logger.debug(f"Görsel oluşturuluyor... ({elapsed}s)")
                except:
                    pass

                time.sleep(3)

            logger.warning("Görsel oluşturma timeout")
            return False

        except Exception as e:
            logger.error(f"Görsel bekleme hatası: {e}")
            return False

    def download_latest_image(self, save_path: str) -> Optional[str]:
        """En son oluşturulan görseli indir - Gerçek indirme (ASLA screenshot yok)"""
        try:
            self._update_progress("Görsel indiriliyor...", 55)

            images = self._find_generated_images()
            if not images:
                logger.warning("İndirilecek görsel bulunamadı")
                return None

            # En son görseli al
            latest_image = images[-1]
            img_src = latest_image.get_attribute('src') or ""
            logger.info(f"Görsel src: {img_src[:100]}...")

            # İndirme öncesi dosyaları kaydet
            downloads_dir = os.path.expanduser("~/Downloads")
            files_before = set()
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                files_before.update(glob.glob(os.path.join(downloads_dir, ext)))

            # ===== YÖNTEM 1: Canvas ile blob/data URL'den tam çözünürlük görsel çıkar =====
            try:
                logger.info("Yöntem 1: Canvas ile görsel çıkarılıyor...")
                # JavaScript ile görseli canvas'a çiz ve base64 olarak al
                canvas_script = """
                var img = arguments[0];
                var canvas = document.createElement('canvas');

                // Gerçek boyutları al (naturalWidth/Height tam çözünürlük verir)
                canvas.width = img.naturalWidth || img.width;
                canvas.height = img.naturalHeight || img.height;

                var ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                // PNG formatında base64 string olarak döndür
                return {
                    data: canvas.toDataURL('image/png'),
                    width: canvas.width,
                    height: canvas.height
                };
                """
                result = self.driver.execute_script(canvas_script, latest_image)

                if result and result.get('data') and result['data'].startswith('data:image'):
                    import base64
                    # "data:image/png;base64," kısmını kaldır
                    base64_data = result['data'].split(',')[1]
                    image_data = base64.b64decode(base64_data)

                    # Dosyayı yaz
                    with open(save_path, 'wb') as f:
                        f.write(image_data)

                    if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                        logger.info(f"✅ Canvas ile indirildi: {save_path} ({result['width']}x{result['height']})")
                        self._update_progress(f"Görsel kaydedildi: {result['width']}x{result['height']}", 60)
                        return save_path
                    else:
                        logger.warning(f"Canvas dosyası çok küçük: {os.path.getsize(save_path)} bytes")
            except Exception as e:
                logger.warning(f"Canvas yöntemi başarısız: {e}")

            # ===== YÖNTEM 2: Gemini'nin indirme butonunu bul ve tıkla =====
            download_clicked = False
            try:
                logger.info("Yöntem 2: İndirme butonu aranıyor...")
                from selenium.webdriver.common.action_chains import ActionChains

                # Görsele tıkla - büyük görüntü moduna geçebilir
                try:
                    latest_image.click()
                    time.sleep(1)
                except:
                    pass

                # Hover yap
                actions = ActionChains(self.driver)
                actions.move_to_element(latest_image).perform()
                time.sleep(1)

                # Gemini'ye özgü ve genel indirme buton seçicileri
                download_selectors = [
                    # Gemini özgü
                    'button[data-test-id="download-button"]',
                    'button[jsname*="download" i]',
                    'button[data-idom-class*="download" i]',
                    '[aria-label*="Download" i]',
                    '[aria-label*="İndir" i]',
                    '[data-tooltip*="Download" i]',
                    '[data-tooltip*="İndir" i]',
                    # Mat-icon-button tarzı
                    'button mat-icon[fonticon="download"]',
                    'button[mattooltip*="download" i]',
                    # Genel
                    'button.download-button',
                    '.download-icon',
                    '[class*="download"]',
                ]

                for selector in download_selectors:
                    try:
                        btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in btns:
                            if btn.is_displayed():
                                btn.click()
                                download_clicked = True
                                logger.info(f"✅ İndirme butonu tıklandı: {selector}")
                                time.sleep(3)
                                break
                        if download_clicked:
                            break
                    except:
                        continue

                # ESC ile modalı kapat
                if not download_clicked:
                    try:
                        self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    except:
                        pass
            except Exception as e:
                logger.warning(f"İndirme butonu yöntemi başarısız: {e}")

            # ===== YÖNTEM 3: HTTP(S) URL'den doğrudan indir =====
            if not download_clicked and img_src.startswith('http'):
                try:
                    logger.info("Yöntem 3: HTTP URL'den indiriliyor...")
                    import urllib.request

                    # Headers ekle (Gemini URL'leri için gerekli olabilir)
                    opener = urllib.request.build_opener()
                    opener.addheaders = [
                        ('User-Agent', 'Mozilla/5.0'),
                        ('Referer', 'https://gemini.google.com/')
                    ]
                    urllib.request.install_opener(opener)

                    urllib.request.urlretrieve(img_src, save_path)
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                        logger.info(f"✅ URL'den indirildi: {save_path}")
                        self._update_progress(f"Görsel kaydedildi: {os.path.basename(save_path)}", 60)
                        return save_path
                except Exception as e:
                    logger.warning(f"URL indirme başarısız: {e}")

            # ===== YÖNTEM 4: Fetch API ile blob URL'yi çöz =====
            if img_src.startswith('blob:'):
                try:
                    logger.info("Yöntem 4: Fetch API ile blob çözülüyor...")
                    fetch_script = """
                    var url = arguments[0];
                    return fetch(url)
                        .then(response => response.blob())
                        .then(blob => {
                            return new Promise((resolve, reject) => {
                                var reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.onerror = reject;
                                reader.readAsDataURL(blob);
                            });
                        });
                    """
                    # Async script çalıştır
                    data_url = self.driver.execute_async_script(f"""
                    var callback = arguments[arguments.length - 1];
                    fetch('{img_src}')
                        .then(response => response.blob())
                        .then(blob => {{
                            var reader = new FileReader();
                            reader.onloadend = () => callback(reader.result);
                            reader.readAsDataURL(blob);
                        }})
                        .catch(err => callback(null));
                    """)

                    if data_url and data_url.startswith('data:image'):
                        import base64
                        base64_data = data_url.split(',')[1]
                        image_data = base64.b64decode(base64_data)

                        with open(save_path, 'wb') as f:
                            f.write(image_data)

                        if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                            logger.info(f"✅ Blob fetch ile indirildi: {save_path}")
                            self._update_progress(f"Görsel kaydedildi", 60)
                            return save_path
                except Exception as e:
                    logger.warning(f"Fetch API yöntemi başarısız: {e}")

            # ===== YÖNTEM 5: Downloads klasöründe yeni dosya kontrol et =====
            time.sleep(3)
            files_after = set()
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                files_after.update(glob.glob(os.path.join(downloads_dir, ext)))

            new_files = files_after - files_before
            if new_files:
                newest = max(new_files, key=os.path.getmtime)
                # Dosya boyutunu kontrol et
                if os.path.getsize(newest) > 10000:
                    shutil.move(newest, save_path)
                    logger.info(f"✅ Downloads'dan taşındı: {save_path}")
                    self._update_progress(f"Görsel kaydedildi: {os.path.basename(save_path)}", 60)
                    return save_path

            # ===== SCREENSHOT ALMIYORUZ - gerçek indirme başarısız olduysa None dön =====
            logger.error("❌ GÖRSEL İNDİRİLEMEDİ - Tüm yöntemler başarısız!")
            logger.error(f"   - Görsel src: {img_src[:100] if img_src else 'YOK'}")
            return None

        except Exception as e:
            logger.error(f"Görsel indirme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_generated_videos(self) -> List:
        """Sayfadaki oluşturulmuş videoları bul"""
        videos = []
        selectors = [
            'video[src]',
            'video source[src]',
            '[data-testid*="video"] video',
            'video',
            '.video-container video',
            '[class*="video"] video',
            'model-response video',
            'message-content video',
        ]

        for selector in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for vid in found:
                    try:
                        # Video elementi veya source'tan src al
                        src = vid.get_attribute('src')
                        if not src:
                            # source elementinden al
                            sources = vid.find_elements(By.TAG_NAME, 'source')
                            for source in sources:
                                src = source.get_attribute('src')
                                if src:
                                    break

                        if src and ('blob:' in src or 'http' in src):
                            if vid not in videos:
                                videos.append(vid)
                                logger.info(f"Video bulundu: {src[:100]}...")
                    except:
                        continue
            except:
                continue

        # Alternatif: Tüm videoları bul
        if not videos:
            try:
                all_videos = self.driver.find_elements(By.TAG_NAME, 'video')
                for vid in all_videos:
                    try:
                        src = vid.get_attribute('src') or ''
                        # currentSrc'yi de kontrol et
                        if not src:
                            src = vid.get_attribute('currentSrc') or ''
                        if src:
                            videos.append(vid)
                            logger.info(f"Alternatif video bulundu: {src[:100]}...")
                    except:
                        continue
            except:
                pass

        logger.info(f"Toplam {len(videos)} video bulundu")
        return videos

    def _count_generated_videos(self) -> int:
        """Sayfadaki video sayısını say"""
        return len(self._find_generated_videos())

    def wait_for_video_generation(self, previous_count: int = 0) -> bool:
        """Video oluşturulmasını bekle"""
        try:
            self._update_progress("Video oluşturuluyor, bekleniyor...", 70)

            max_wait = TIMEOUTS['video_generation']
            start_time = time.time()

            logger.info(f"Video bekleniyor - önceki sayı: {previous_count}")

            while time.time() - start_time < max_wait:
                current_count = self._count_generated_videos()
                elapsed = int(time.time() - start_time)

                if current_count > previous_count:
                    self._update_progress(f"Video oluşturuldu! ({elapsed}s)", 80)
                    time.sleep(5)  # Videonun tam yüklenmesini bekle
                    return True

                # Loading kontrolü
                try:
                    loading = self.driver.find_elements(By.CSS_SELECTOR,
                        '.loading, .generating, [class*="loading"], [class*="progress"]')
                    if loading:
                        logger.debug(f"Video oluşturuluyor... ({elapsed}s)")
                except:
                    pass

                time.sleep(5)

            logger.warning("Video oluşturma timeout")
            return False

        except Exception as e:
            logger.error(f"Video bekleme hatası: {e}")
            return False

    def download_latest_video(self, save_path: str) -> Optional[str]:
        """En son oluşturulan videoyu indir"""
        try:
            self._update_progress("Video indiriliyor...", 85)

            videos = self._find_generated_videos()
            if not videos:
                logger.warning("İndirilecek video bulunamadı")
                return None

            latest_video = videos[-1]

            # Video src'yi al
            video_src = latest_video.get_attribute('src')
            if not video_src:
                video_src = latest_video.get_attribute('currentSrc')
            if not video_src:
                # source elementinden al
                try:
                    sources = latest_video.find_elements(By.TAG_NAME, 'source')
                    for source in sources:
                        video_src = source.get_attribute('src')
                        if video_src:
                            break
                except:
                    pass

            logger.info(f"Video src: {video_src[:100] if video_src else 'None'}...")

            # İndirme öncesi dosyaları kaydet
            downloads_dir = os.path.expanduser("~/Downloads")
            files_before = set(glob.glob(os.path.join(downloads_dir, "*.mp4")))
            files_before.update(glob.glob(os.path.join(downloads_dir, "*.webm")))

            # YÖNTEM 1: İndirme butonunu bul ve tıkla
            download_clicked = False
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(latest_video).perform()
                time.sleep(1)

                download_selectors = [
                    'button[aria-label*="download" i]',
                    'button[aria-label*="Download" i]',
                    'button[aria-label*="indir" i]',
                    '[data-tooltip*="download" i]',
                    'button[data-test-id*="download"]',
                ]

                for selector in download_selectors:
                    try:
                        btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in btns:
                            if btn.is_displayed():
                                btn.click()
                                download_clicked = True
                                logger.info(f"Video indirme butonu tıklandı: {selector}")
                                time.sleep(5)
                                break
                        if download_clicked:
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"İndirme butonu bulunamadı: {e}")

            # YÖNTEM 2: JavaScript ile indirme
            if not download_clicked and video_src and video_src.startswith('http'):
                try:
                    filename = os.path.basename(save_path)
                    self.driver.execute_script(f"""
                        var a = document.createElement('a');
                        a.href = '{video_src}';
                        a.download = '{filename}';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    """)
                    logger.info("JavaScript ile indirme tetiklendi")
                    time.sleep(5)
                except Exception as e:
                    logger.warning(f"JS indirme başarısız: {e}")

            # YÖNTEM 3: Blob URL'den indirme
            if video_src and video_src.startswith('blob:'):
                try:
                    # Blob'u base64'e çevir ve indir
                    video_data = self.driver.execute_script("""
                        var video = arguments[0];
                        var canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        // Not: Bu sadece canvas destekli videolar için çalışır
                        return null;
                    """, latest_video)
                except:
                    pass

            # İndirilen dosyayı bul
            time.sleep(5)
            files_after = set(glob.glob(os.path.join(downloads_dir, "*.mp4")))
            files_after.update(glob.glob(os.path.join(downloads_dir, "*.webm")))

            new_files = files_after - files_before
            if new_files:
                newest = max(new_files, key=os.path.getmtime)
                shutil.move(newest, save_path)
                logger.info(f"Video indirildi ve taşındı: {save_path}")
                self._update_progress(f"Video kaydedildi: {os.path.basename(save_path)}", 90)
                return save_path

            # YÖNTEM 4: Doğrudan URL'den indir (http/https için)
            if video_src and video_src.startswith('http'):
                try:
                    import urllib.request
                    urllib.request.urlretrieve(video_src, save_path)
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                        logger.info(f"URL'den indirildi: {save_path}")
                        self._update_progress(f"Video kaydedildi: {os.path.basename(save_path)}", 90)
                        return save_path
                except Exception as e:
                    logger.warning(f"URL indirme başarısız: {e}")

            logger.warning("Video indirilemedi - tüm yöntemler başarısız")
            return None

        except Exception as e:
            logger.error(f"Video indirme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_latest_download(self, pattern: str) -> Optional[str]:
        """En son indirilen dosyayı bul"""
        try:
            files = glob.glob(os.path.join(self.download_dir, pattern))
            if files:
                latest = max(files, key=os.path.getctime)
                if time.time() - os.path.getctime(latest) < 60:
                    return latest
        except:
            pass
        return None

    def new_chat(self):
        """Yeni sohbet başlat"""
        try:
            # Yeni sohbet butonu ara
            new_chat_selectors = [
                'button[aria-label*="New chat"]',
                'button[aria-label*="Yeni sohbet"]',
                '[data-test-id="new-chat"]',
                '.new-chat-button',
            ]

            for selector in new_chat_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(2)
                            return True
                except:
                    continue

            # Alternatif: Sayfayı yenile
            self.driver.get(GEMINI_URL)
            time.sleep(5)
            return True

        except Exception as e:
            logger.error(f"Yeni sohbet hatası: {e}")
            return False

    def close(self):
        """Tarayıcıyı kapat"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


class GeminiProManager:
    """3 Gemini Pro hesabını yöneten ana sınıf"""

    def __init__(self, progress_callback: Callable = None):
        self.progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))
        self.accounts: List[GeminiProAccount] = []
        self.usage_file = os.path.join(config.BASE_DIR, "gemini_pro_usage.json")
        self.projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        os.makedirs(self.projects_dir, exist_ok=True)

        # Hesapları oluştur
        for i in range(1, TOTAL_ACCOUNTS + 1):
            profile_dir = os.path.join(config.BASE_DIR, "chrome_profiles", f"gemini_pro_{i}")
            account = GeminiProAccount(i, profile_dir, progress_callback)
            self.accounts.append(account)

        self._load_usage()

    def _update_progress(self, message: str, percentage: int):
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def _load_usage(self):
        """Kullanım verilerini yükle"""
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, "r") as f:
                    data = json.load(f)

                today = date.today().isoformat()

                for account in self.accounts:
                    acc_data = data.get(f"account_{account.account_id}", {})
                    last_date = acc_data.get("last_date")

                    if last_date == today:
                        account.daily_usage = acc_data.get("usage", 0)
                    else:
                        account.daily_usage = 0

                    account.last_usage_date = today

            except Exception as e:
                logger.error(f"Kullanım verisi yükleme hatası: {e}")

    def _save_usage(self):
        """Kullanım verilerini kaydet"""
        try:
            data = {}
            today = date.today().isoformat()

            for account in self.accounts:
                data[f"account_{account.account_id}"] = {
                    "usage": account.daily_usage,
                    "last_date": today
                }

            with open(self.usage_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Kullanım verisi kaydetme hatası: {e}")

    def get_available_account(self) -> Optional[GeminiProAccount]:
        """Kullanılabilir hesap bul"""
        today = date.today().isoformat()

        for account in self.accounts:
            if account.last_usage_date != today:
                account.daily_usage = 0
                account.last_usage_date = today

            if account.daily_usage < DAILY_VIDEO_LIMIT:
                return account

        return None

    def get_daily_capacity(self) -> Dict[str, Any]:
        """Günlük kapasiteyi göster"""
        today = date.today().isoformat()
        total_remaining = 0
        account_status = []

        for account in self.accounts:
            if account.last_usage_date != today:
                remaining = DAILY_VIDEO_LIMIT
            else:
                remaining = DAILY_VIDEO_LIMIT - account.daily_usage

            total_remaining += remaining
            account_status.append({
                "account_id": account.account_id,
                "used": account.daily_usage if account.last_usage_date == today else 0,
                "remaining": remaining
            })

        return {
            "date": today,
            "total_remaining": total_remaining,
            "accounts": account_status
        }

    def setup_accounts(self) -> Dict[str, Any]:
        """Hesapları kurulum için aç"""
        results = {"success": True, "accounts": []}

        for account in self.accounts:
            self._update_progress(f"Hesap {account.account_id} açılıyor...", (account.account_id * 30))

            if not account.start_browser():
                results["accounts"].append({
                    "account_id": account.account_id,
                    "status": "error",
                    "message": "Tarayıcı başlatılamadı"
                })
                continue

            account.driver.get(GEMINI_URL)
            time.sleep(3)

            results["accounts"].append({
                "account_id": account.account_id,
                "status": "waiting_login",
                "message": "Google hesabına giriş yapın"
            })

        self._update_progress("Tüm hesaplar açıldı. Giriş yapın.", 100)
        return results

    def verify_all_accounts(self) -> Dict[str, Any]:
        """Tüm hesapların giriş durumunu kontrol et"""
        results = {"all_logged_in": True, "accounts": []}

        for account in self.accounts:
            if not account.driver:
                results["accounts"].append({
                    "account_id": account.account_id,
                    "logged_in": False,
                    "message": "Tarayıcı kapalı"
                })
                results["all_logged_in"] = False
                continue

            try:
                current_url = account.driver.current_url
                is_logged_in = "gemini.google.com" in current_url and "accounts.google" not in current_url

                results["accounts"].append({
                    "account_id": account.account_id,
                    "logged_in": is_logged_in,
                    "url": current_url
                })

                if not is_logged_in:
                    results["all_logged_in"] = False

            except Exception as e:
                results["accounts"].append({
                    "account_id": account.account_id,
                    "logged_in": False,
                    "error": str(e)
                })
                results["all_logged_in"] = False

        return results

    def close_all(self):
        """Tüm tarayıcıları kapat"""
        for account in self.accounts:
            account.close()


class DailyShortsMode:
    """Günlük Shorts modu - 9 video/gün"""

    def __init__(self, manager: GeminiProManager):
        self.manager = manager

    def _save_project_json(self, project_dir: str, project_data: Dict[str, Any]):
        """Project.json dosyasını kaydet"""
        project_data["updated_at"] = datetime.now().isoformat()
        project_json_path = os.path.join(project_dir, "project.json")
        with open(project_json_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

    def _load_project_json(self, project_dir: str) -> Optional[Dict[str, Any]]:
        """Project.json dosyasını yükle"""
        project_json_path = os.path.join(project_dir, "project.json")
        if os.path.exists(project_json_path):
            with open(project_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _update_status(self, project_dir: str, project_data: Dict[str, Any], index: int, status: str):
        """Belirli bir prompt'un durumunu güncelle"""
        project_data["status"][str(index)] = status
        self._save_project_json(project_dir, project_data)

    def create_daily_project(self, prompts: List[Dict[str, str]], voice_text: str = "", aspect_format: str = "9:16", thumbnail_prompt: str = "") -> Dict[str, Any]:
        """
        Günlük shorts projesi oluştur - ADIM ADIM

        Args:
            prompts: [{"image_prompt": "...", "video_prompt": "..."}, ...]
            voice_text: Final video için seslendirme metni
            aspect_format: Video formatı ("9:16", "16:9", "1:1")
            thumbnail_prompt: Thumbnail için prompt
        """
        self.voice_text = voice_text  # Render için sakla
        self.aspect_format = aspect_format
        self.thumbnail_prompt = thumbnail_prompt  # Thumbnail için sakla

        # Format açıklamaları
        # Görsel için format açıklaması
        image_format_descriptions = {
            "9:16": "vertical 9:16 phone size format like TikTok/Reels",
            "16:9": "horizontal 16:9 landscape format like YouTube",
            "1:1": "square 1:1 format"
        }
        # Video için format açıklaması
        video_format_descriptions = {
            "9:16": "IMPORTANT: Create a VERTICAL 9:16 video in phone size format (tall, not wide). This must be vertical like TikTok or Instagram Reels",
            "16:9": "Create a horizontal 16:9 landscape video like YouTube",
            "1:1": "Create a square 1:1 video"
        }
        self.format_desc = image_format_descriptions.get(aspect_format, image_format_descriptions["9:16"])
        self.video_format_desc = video_format_descriptions.get(aspect_format, video_format_descriptions["9:16"])

        if len(prompts) > 9:
            return {"error": "Günde maksimum 9 video oluşturulabilir"}

        capacity = self.manager.get_daily_capacity()
        if capacity["total_remaining"] < len(prompts):
            return {"error": f"Yetersiz kapasite. Kalan: {capacity['total_remaining']}, İstenen: {len(prompts)}"}

        # Proje klasörü oluştur
        project_name = f"shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = os.path.join(self.manager.projects_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)

        # Project.json oluştur (diğer sistemdeki gibi)
        project_data = {
            "type": "shorts",
            "aspect_format": aspect_format,
            "expected_count": len(prompts),
            "image_prompts": {},
            "video_prompts": {},
            "thumbnail_prompt": thumbnail_prompt,
            "thumbnail_status": "pending" if thumbnail_prompt else "none",
            "voice": {
                "text": voice_text,
                "style": "friendly"
            },
            "status": {},  # Her prompt için durum: pending, image_done, video_done, completed, failed
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Promptları kaydet
        for idx, p in enumerate(prompts, 1):
            project_data["image_prompts"][str(idx)] = p.get("image_prompt", "")
            project_data["video_prompts"][str(idx)] = p.get("video_prompt", "")
            project_data["status"][str(idx)] = "pending"

        # İlk kayıt
        self._save_project_json(project_dir, project_data)

        results = {
            "project_name": project_name,
            "project_dir": project_dir,
            "videos": [],
            "success": True
        }

        # Watermark temizleyicileri import et
        try:
            from watermark_remover import remove_watermark
        except ImportError:
            remove_watermark = None
            logger.warning("Image watermark remover bulunamadı")

        try:
            from video_watermark_remover import remove_veo_watermark
        except ImportError:
            remove_veo_watermark = None
            logger.warning("Video watermark remover bulunamadı")

        for i, prompt_data in enumerate(prompts, 1):
            self.manager._update_progress(f"Video {i}/{len(prompts)} işleniyor...", 10 + (i * 8))

            # Uygun hesabı bul
            account = self.manager.get_available_account()
            if not account:
                results["success"] = False
                results["error"] = "Tüm hesapların limiti doldu"
                break

            # Hesap tarayıcısı açık değilse aç
            if not account.driver:
                if not account.start_browser():
                    results["videos"].append({
                        "index": i,
                        "success": False,
                        "error": "Tarayıcı başlatılamadı"
                    })
                    continue

                if not account.navigate_to_gemini():
                    results["videos"].append({
                        "index": i,
                        "success": False,
                        "error": "Gemini'ye gidilemedi"
                    })
                    continue

            video_result = {
                "index": i,
                "success": False,
                "image_path": None,
                "cleaned_image_path": None,
                "video_path": None,
                "cleaned_video_path": None,
                "error": None
            }

            try:
                # ===== 1. GÖRSEL OLUŞTUR =====
                self.manager._update_progress(f"[{i}] Görsel oluşturuluyor ({self.aspect_format})...", 15 + (i * 8))

                image_prompt = prompt_data.get("image_prompt", "")
                # Seçilen formatta görsel oluştur
                full_image_prompt = f"Create a high quality image in {self.format_desc}: {image_prompt}"

                # Önceki görsel sayısını al
                prev_image_count = account._count_generated_images()

                # Prompt gönder
                if not account.send_prompt(full_image_prompt):
                    video_result["error"] = "Görsel prompt gönderilemedi"
                    results["videos"].append(video_result)
                    continue

                # Görsel oluşturulmasını bekle
                if not account.wait_for_image_generation(prev_image_count):
                    video_result["error"] = "Görsel oluşturulamadı - timeout"
                    results["videos"].append(video_result)
                    continue

                # Görseli indir
                image_path = os.path.join(project_dir, f"image_{i}.png")
                downloaded_image = account.download_latest_image(image_path)

                if not downloaded_image:
                    video_result["error"] = "Görsel indirilemedi"
                    results["videos"].append(video_result)
                    continue

                video_result["image_path"] = downloaded_image
                logger.info(f"[{i}] Görsel indirildi: {downloaded_image}")

                # Durumu güncelle: görsel tamamlandı
                self._update_status(project_dir, project_data, i, "image_done")

                # ===== 2. WATERMARK TEMİZLE =====
                self.manager._update_progress(f"[{i}] Watermark temizleniyor...", 25 + (i * 8))

                cleaned_image_path = os.path.join(project_dir, f"image_{i}_cleaned.png")

                if remove_watermark:
                    try:
                        remove_watermark(downloaded_image, cleaned_image_path)
                        video_result["cleaned_image_path"] = cleaned_image_path
                        logger.info(f"[{i}] Watermark temizlendi")
                    except Exception as e:
                        logger.warning(f"[{i}] Watermark temizleme hatası: {e}")
                        shutil.copy(downloaded_image, cleaned_image_path)
                        video_result["cleaned_image_path"] = cleaned_image_path
                else:
                    shutil.copy(downloaded_image, cleaned_image_path)
                    video_result["cleaned_image_path"] = cleaned_image_path

                # ===== 3. YENİ SOHBET + TEMİZ GÖRSELİ UPLOAD + VIDEO OLUŞTUR =====
                self.manager._update_progress(f"[{i}] Yeni sohbet başlatılıyor...", 30 + (i * 8))

                # Yeni sohbet başlat
                account.new_chat()
                time.sleep(3)

                self.manager._update_progress(f"[{i}] Temiz görsel yükleniyor...", 33 + (i * 8))

                video_prompt = prompt_data.get("video_prompt", "")
                # Video prompt'u hazırla
                full_video_prompt = f"Create a short cinematic video animation from this image. {self.video_format_desc}. {video_prompt}"

                prev_video_count = account._count_generated_videos()

                # Temizlenmiş görseli upload et ve video prompt'u gönder
                if not account.upload_and_prompt(cleaned_image_path, full_video_prompt):
                    video_result["error"] = "Görsel yüklenemedi veya video prompt gönderilemedi"
                    results["videos"].append(video_result)
                    continue

                self.manager._update_progress(f"[{i}] Video oluşturuluyor ({self.aspect_format})...", 35 + (i * 8))

                # Video oluşturulmasını bekle
                if not account.wait_for_video_generation(prev_video_count):
                    video_result["error"] = "Video oluşturulamadı - timeout"
                    results["videos"].append(video_result)
                    continue

                # Videoyu indir
                video_path = os.path.join(project_dir, f"video_{i}.mp4")
                downloaded_video = account.download_latest_video(video_path)

                if downloaded_video:
                    video_result["video_path"] = downloaded_video
                    logger.info(f"[{i}] Video indirildi: {downloaded_video}")

                    # ===== 5. VIDEO WATERMARK TEMİZLE (Veo logosu) =====
                    self.manager._update_progress(f"[{i}] Video watermark temizleniyor...", 45 + (i * 8))

                    cleaned_video_path = os.path.join(project_dir, f"video_{i}_cleaned.mp4")

                    if remove_veo_watermark:
                        try:
                            success = remove_veo_watermark(downloaded_video, cleaned_video_path)
                            if success and os.path.exists(cleaned_video_path):
                                video_result["cleaned_video_path"] = cleaned_video_path
                                # Temizlenmiş videoyu orijinal yerine kullan
                                os.replace(cleaned_video_path, downloaded_video)
                                logger.info(f"[{i}] Video watermark temizlendi")
                            else:
                                logger.warning(f"[{i}] Video watermark temizlenemedi")
                        except Exception as e:
                            logger.warning(f"[{i}] Video watermark temizleme hatası: {e}")
                    else:
                        logger.debug(f"[{i}] Video watermark remover yüklü değil")

                    video_result["success"] = True

                    # Durumu güncelle: tamamlandı
                    self._update_status(project_dir, project_data, i, "completed")

                    # Hesap kullanımını güncelle
                    account.daily_usage += 1
                    self.manager._save_usage()

                    logger.info(f"[{i}] Video tamamlandı: {downloaded_video}")
                else:
                    video_result["error"] = "Video indirilemedi"
                    self._update_status(project_dir, project_data, i, "video_failed")

                # Yeni sohbet başlat (sonraki video için)
                account.new_chat()
                time.sleep(2)

            except Exception as e:
                logger.error(f"[{i}] Hata: {e}")
                import traceback
                traceback.print_exc()
                video_result["error"] = str(e)
                self._update_status(project_dir, project_data, i, "failed")

            results["videos"].append(video_result)

        # Sonuç özeti
        success_count = sum(1 for v in results["videos"] if v.get("success"))
        self.manager._update_progress(f"Videolar tamamlandı: {success_count}/{len(prompts)}", 85)

        # ===== 5. RENDER YAP (Tüm videolar varsa) =====
        if success_count > 0:
            self.manager._update_progress("Final render başlıyor...", 90)

            try:
                from video_renderer import render_project

                # Video dosyalarını topla
                video_paths = []
                for i in range(1, len(prompts) + 1):
                    video_path = os.path.join(project_dir, f"video_{i}.mp4")
                    if os.path.exists(video_path):
                        video_paths.append(video_path)

                if video_paths:
                    # Voice text varsa kullan
                    voice_text = getattr(self, 'voice_text', '') or ''
                    if not voice_text:
                        # Varsayılan ses metni oluştur
                        voice_text = " ".join([
                            f"Scene {i}, showing stunning visual content."
                            for i in range(1, len(video_paths) + 1)
                        ])

                    render_result = render_project(
                        project_dir=project_dir,
                        video_paths=video_paths,
                        voice_text=voice_text,
                        voice_style="friendly",
                        words_per_subtitle=2,
                        progress_callback=self.manager.progress_callback
                    )

                    if render_result.get("success"):
                        results["final_video"] = render_result.get("final_video")
                        self.manager._update_progress(f"Final video hazır!", 95)
                        logger.info(f"Final video: {results['final_video']}")
                    else:
                        logger.warning(f"Render hatası: {render_result.get('error')}")

            except Exception as e:
                logger.error(f"Render hatası: {e}")
                import traceback
                traceback.print_exc()

        # ===== 6. THUMBNAIL OLUŞTUR (varsa) =====
        thumbnail_prompt = getattr(self, 'thumbnail_prompt', '') or project_data.get('thumbnail_prompt', '')
        if thumbnail_prompt and success_count > 0:
            self.manager._update_progress("Thumbnail oluşturuluyor...", 96)

            try:
                # Kullanılabilir hesap bul
                account = self.manager.get_available_account()
                if account:
                    if not account.driver:
                        account.start_browser()
                        account.navigate_to_gemini()

                    # Thumbnail için 16:9 yatay format kullan (YouTube thumbnail boyutu)
                    thumb_full_prompt = f"Create a YouTube thumbnail image in horizontal 16:9 aspect ratio (1920x1080 pixels): {thumbnail_prompt}"

                    prev_count = account._count_generated_images()
                    if account.send_prompt(thumb_full_prompt):
                        if account.wait_for_image_generation(prev_count):
                            thumbnail_path = os.path.join(project_dir, "thumbnail.png")
                            if account.download_latest_image(thumbnail_path):
                                # Watermark temizle
                                if remove_watermark:
                                    try:
                                        cleaned_thumb = os.path.join(project_dir, "thumbnail_cleaned.png")
                                        remove_watermark(thumbnail_path, cleaned_thumb)
                                        os.replace(cleaned_thumb, thumbnail_path)
                                    except:
                                        pass

                                results["thumbnail"] = thumbnail_path
                                project_data["thumbnail_status"] = "completed"
                                self._save_project_json(project_dir, project_data)
                                self.manager._update_progress("Thumbnail oluşturuldu!", 98)
                                logger.info(f"Thumbnail: {thumbnail_path}")
                            else:
                                project_data["thumbnail_status"] = "failed"
                                self._save_project_json(project_dir, project_data)
                        else:
                            project_data["thumbnail_status"] = "failed"
                            self._save_project_json(project_dir, project_data)

                    account.new_chat()

            except Exception as e:
                logger.error(f"Thumbnail oluşturma hatası: {e}")
                project_data["thumbnail_status"] = "failed"
                self._save_project_json(project_dir, project_data)

        self.manager._update_progress(f"Tamamlandı: {success_count}/{len(prompts)} başarılı", 100)
        return results

    def retry_failed(self, project_dir: str, indices: List[int] = None) -> Dict[str, Any]:
        """
        Başarısız olan prompt'ları yeniden dene

        Args:
            project_dir: Proje klasörü
            indices: Belirli indeksler (None ise tüm başarısızlar)
        """
        project_data = self._load_project_json(project_dir)
        if not project_data:
            return {"error": "project.json bulunamadı"}

        # Başarısız olanları bul
        failed_indices = []
        for idx, status in project_data["status"].items():
            if status in ["pending", "failed", "image_done", "video_failed"]:
                if indices is None or int(idx) in indices:
                    failed_indices.append(int(idx))

        if not failed_indices:
            return {"error": "Yeniden deneyecek öğe bulunamadı", "success": True}

        failed_indices.sort()
        self.manager._update_progress(f"{len(failed_indices)} öğe yeniden denenecek", 5)

        # Promptları hazırla
        prompts_to_retry = []
        for idx in failed_indices:
            prompts_to_retry.append({
                "image_prompt": project_data["image_prompts"].get(str(idx), ""),
                "video_prompt": project_data["video_prompts"].get(str(idx), ""),
                "original_index": idx
            })

        # Format ve voice bilgilerini al
        aspect_format = project_data.get("aspect_format", "9:16")
        voice_text = project_data.get("voice", {}).get("text", "")

        # Watermark temizleyicileri import et
        try:
            from watermark_remover import remove_watermark
        except ImportError:
            remove_watermark = None

        try:
            from video_watermark_remover import remove_veo_watermark
        except ImportError:
            remove_veo_watermark = None

        image_format_descriptions = {
            "9:16": "vertical 9:16 phone size format like TikTok/Reels",
            "16:9": "horizontal 16:9 landscape format like YouTube",
            "1:1": "square 1:1 format"
        }
        video_format_descriptions = {
            "9:16": "IMPORTANT: Create a VERTICAL 9:16 video in phone size format (tall, not wide). This must be vertical like TikTok or Instagram Reels",
            "16:9": "Create a horizontal 16:9 landscape video like YouTube",
            "1:1": "Create a square 1:1 video"
        }
        format_desc = image_format_descriptions.get(aspect_format, image_format_descriptions["9:16"])
        video_format_desc = video_format_descriptions.get(aspect_format, video_format_descriptions["9:16"])

        results = {"retried": [], "success": True}

        for prompt_data in prompts_to_retry:
            i = prompt_data["original_index"]
            current_status = project_data["status"].get(str(i), "pending")

            self.manager._update_progress(f"[{i}] Yeniden deneniyor (durum: {current_status})...", 20)

            account = self.manager.get_available_account()
            if not account:
                results["error"] = "Tüm hesapların limiti doldu"
                break

            if not account.driver:
                if not account.start_browser() or not account.navigate_to_gemini():
                    results["retried"].append({"index": i, "success": False, "error": "Tarayıcı hatası"})
                    continue

            retry_result = {"index": i, "success": False}

            try:
                # Görsel oluşturulmuş mu kontrol et
                needs_image = current_status in ["pending", "failed"]
                needs_video = current_status in ["pending", "failed", "image_done", "video_failed"]

                if needs_image:
                    # Görsel oluştur
                    self.manager._update_progress(f"[{i}] Görsel oluşturuluyor...", 30)
                    image_prompt = prompt_data["image_prompt"]
                    full_prompt = f"Create a high quality image in {format_desc}: {image_prompt}"

                    prev_count = account._count_generated_images()
                    if not account.send_prompt(full_prompt):
                        retry_result["error"] = "Prompt gönderilemedi"
                        results["retried"].append(retry_result)
                        continue

                    if not account.wait_for_image_generation(prev_count):
                        retry_result["error"] = "Görsel oluşturulamadı"
                        self._update_status(project_dir, project_data, i, "failed")
                        results["retried"].append(retry_result)
                        continue

                    image_path = os.path.join(project_dir, f"image_{i}.png")
                    if not account.download_latest_image(image_path):
                        retry_result["error"] = "Görsel indirilemedi"
                        self._update_status(project_dir, project_data, i, "failed")
                        results["retried"].append(retry_result)
                        continue

                    # Watermark temizle
                    cleaned_path = os.path.join(project_dir, f"image_{i}_cleaned.png")
                    if remove_watermark:
                        try:
                            remove_watermark(image_path, cleaned_path)
                        except:
                            shutil.copy(image_path, cleaned_path)
                    else:
                        shutil.copy(image_path, cleaned_path)

                    self._update_status(project_dir, project_data, i, "image_done")
                    # Video da gerekiyorsa yeni sohbet başlatma - aynı sohbette devam et
                    if not needs_video:
                        account.new_chat()
                        time.sleep(2)

                if needs_video:
                    # Video oluştur
                    self.manager._update_progress(f"[{i}] Video oluşturuluyor...", 60)
                    video_prompt = prompt_data["video_prompt"]

                    # Eğer görsel yeni oluşturulduysa (needs_image True idi), aynı sohbette devam et
                    # Eğer görsel zaten vardıysa (image_done), temizlenmiş görseli upload et
                    if needs_image:
                        # Görsel yeni oluşturuldu, aynı sohbette video iste
                        full_prompt = f"Now create a short cinematic video animation from this image you just generated. {video_format_desc}. {video_prompt}"
                        prev_count = account._count_generated_videos()

                        if not account.send_prompt(full_prompt):
                            retry_result["error"] = "Video prompt gönderilemedi"
                            results["retried"].append(retry_result)
                            continue
                    else:
                        # Görsel zaten var, temizlenmiş görseli upload et
                        cleaned_image_path = os.path.join(project_dir, f"image_{i}_cleaned.png")
                        if not os.path.exists(cleaned_image_path):
                            cleaned_image_path = os.path.join(project_dir, f"image_{i}.png")

                        full_prompt = f"Using this image, create a short cinematic video animation. {video_format_desc}. {video_prompt}"
                        prev_count = account._count_generated_videos()

                        # Görseli upload et ve prompt gönder
                        if not account.upload_and_prompt(cleaned_image_path, full_prompt):
                            retry_result["error"] = "Görsel upload veya video prompt gönderilemedi"
                            results["retried"].append(retry_result)
                            continue

                    if not account.wait_for_video_generation(prev_count):
                        retry_result["error"] = "Video oluşturulamadı"
                        self._update_status(project_dir, project_data, i, "video_failed")
                        results["retried"].append(retry_result)
                        continue

                    video_path = os.path.join(project_dir, f"video_{i}.mp4")
                    if not account.download_latest_video(video_path):
                        retry_result["error"] = "Video indirilemedi"
                        self._update_status(project_dir, project_data, i, "video_failed")
                        results["retried"].append(retry_result)
                        continue

                    # Video watermark temizle
                    if remove_veo_watermark:
                        try:
                            cleaned_video = os.path.join(project_dir, f"video_{i}_cleaned.mp4")
                            if remove_veo_watermark(video_path, cleaned_video):
                                os.replace(cleaned_video, video_path)
                        except:
                            pass

                    self._update_status(project_dir, project_data, i, "completed")
                    account.daily_usage += 1
                    self.manager._save_usage()
                    account.new_chat()
                    time.sleep(2)

                retry_result["success"] = True

            except Exception as e:
                retry_result["error"] = str(e)
                self._update_status(project_dir, project_data, i, "failed")

            results["retried"].append(retry_result)

        success_count = sum(1 for r in results["retried"] if r.get("success"))
        self.manager._update_progress(f"Yeniden deneme tamamlandı: {success_count}/{len(failed_indices)}", 85)

        # Tüm videolar tamamlandıysa render yap
        all_completed = all(
            project_data["status"].get(str(idx)) == "completed"
            for idx in range(1, project_data.get("expected_count", 0) + 1)
        )

        if all_completed and voice_text:
            self.manager._update_progress("Final render başlıyor...", 90)

            try:
                from video_renderer import render_project

                video_paths = []
                for idx in range(1, project_data.get("expected_count", 0) + 1):
                    video_path = os.path.join(project_dir, f"video_{idx}.mp4")
                    if os.path.exists(video_path):
                        video_paths.append(video_path)

                if video_paths:
                    render_result = render_project(
                        project_dir=project_dir,
                        video_paths=video_paths,
                        voice_text=voice_text,
                        voice_style="friendly",
                        words_per_subtitle=2,
                        progress_callback=self.manager.progress_callback
                    )

                    if render_result.get("success"):
                        results["final_video"] = render_result.get("final_video")
                        self.manager._update_progress("Final video hazır!", 100)
                        logger.info(f"Final video: {results['final_video']}")
                    else:
                        logger.warning(f"Render hatası: {render_result.get('error')}")

            except Exception as e:
                logger.error(f"Render hatası: {e}")
                import traceback
                traceback.print_exc()

        return results

    def update_prompt(self, project_dir: str, index: int, image_prompt: str = None, video_prompt: str = None) -> Dict[str, Any]:
        """
        Belirli bir prompt'u güncelle

        Args:
            project_dir: Proje klasörü
            index: Prompt indeksi
            image_prompt: Yeni görsel prompt'u (None ise değiştirme)
            video_prompt: Yeni video prompt'u (None ise değiştirme)
        """
        project_data = self._load_project_json(project_dir)
        if not project_data:
            return {"error": "project.json bulunamadı"}

        idx_str = str(index)
        if idx_str not in project_data["image_prompts"]:
            return {"error": f"Index {index} bulunamadı"}

        updated = []
        if image_prompt is not None:
            project_data["image_prompts"][idx_str] = image_prompt
            updated.append("image_prompt")
            # Görsel değiştiyse durumu pending yap
            if project_data["status"].get(idx_str) not in ["pending"]:
                project_data["status"][idx_str] = "pending"

        if video_prompt is not None:
            project_data["video_prompts"][idx_str] = video_prompt
            updated.append("video_prompt")
            # Video prompt değiştiyse ve görsel tamamsa, image_done yap
            if project_data["status"].get(idx_str) == "completed":
                project_data["status"][idx_str] = "image_done"

        self._save_project_json(project_dir, project_data)

        return {
            "success": True,
            "updated": updated,
            "new_status": project_data["status"].get(idx_str)
        }

    def update_voice(self, project_dir: str, voice_text: str) -> Dict[str, Any]:
        """Ses metnini güncelle"""
        project_data = self._load_project_json(project_dir)
        if not project_data:
            return {"error": "project.json bulunamadı"}

        project_data["voice"]["text"] = voice_text
        self._save_project_json(project_dir, project_data)

        return {"success": True}


class LongVideoMode:
    """Uzun Video modu - 63 prompt / 7 gün"""

    def __init__(self, manager: GeminiProManager):
        self.manager = manager

    def create_weekly_project(self, prompts: List[Dict[str, str]], voice_text: str = "") -> Dict[str, Any]:
        """Haftalık uzun video projesi oluştur"""
        if len(prompts) > 63:
            return {"error": "Maksimum 63 prompt (7 gün x 9 video)"}

        project_name = f"longvideo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = os.path.join(self.manager.projects_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)

        # Promptları 7 güne böl
        daily_prompts = []
        for i in range(0, len(prompts), 9):
            daily_prompts.append(prompts[i:i+9])

        schedule = {
            "project_name": project_name,
            "project_dir": project_dir,
            "total_prompts": len(prompts),
            "days": len(daily_prompts),
            "voice_text": voice_text,
            "created_at": datetime.now().isoformat(),
            "daily_schedule": [],
            "status": "pending"
        }

        start_date = date.today()
        for day_index, day_prompts in enumerate(daily_prompts):
            from datetime import timedelta
            day_date = start_date + timedelta(days=day_index)
            schedule["daily_schedule"].append({
                "day": day_index + 1,
                "date": day_date.isoformat(),
                "prompts": day_prompts,
                "completed": False,
                "videos_created": 0
            })

        with open(os.path.join(project_dir, "schedule.json"), "w") as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "project_name": project_name,
            "project_dir": project_dir,
            "schedule": schedule,
            "message": f"{len(prompts)} prompt {len(daily_prompts)} güne bölündü."
        }

    def run_daily_batch(self, project_dir: str) -> Dict[str, Any]:
        """Bugünkü batch'i çalıştır"""
        schedule_path = os.path.join(project_dir, "schedule.json")

        if not os.path.exists(schedule_path):
            return {"error": "Schedule bulunamadı"}

        with open(schedule_path, "r") as f:
            schedule = json.load(f)

        today = date.today().isoformat()

        today_batch = None
        for day_schedule in schedule["daily_schedule"]:
            if day_schedule["date"] == today and not day_schedule["completed"]:
                today_batch = day_schedule
                break

        if not today_batch:
            return {"error": "Bugün için bekleyen batch yok"}

        shorts_mode = DailyShortsMode(self.manager)
        result = shorts_mode.create_daily_project(today_batch["prompts"])

        if result.get("success"):
            today_batch["completed"] = True
            today_batch["videos_created"] = len([v for v in result.get("videos", []) if v.get("success")])

            with open(schedule_path, "w") as f:
                json.dump(schedule, f, indent=2, ensure_ascii=False)

        return result


if __name__ == "__main__":
    print("=== Gemini Pro Manager ===")
    print("Adım adım çalışan görsel + video oluşturma sistemi")
