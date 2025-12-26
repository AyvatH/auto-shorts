"""
Auto Shorts Image Generator - Selenium Generator Module
"""
import os
import time
import glob
import shutil
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, Callable

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GeminiImageGenerator:
    """Gemini AI ile görsel oluşturma sınıfı"""

    def __init__(self, project_name: str = None, progress_callback: Callable = None):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.project_name = project_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.project_dir = os.path.join(config.PROJECTS_DIR, self.project_name)
        self.progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))
        self.download_dir = os.path.join(self.project_dir, "downloads")

        # Create directories
        os.makedirs(self.project_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

    def _update_progress(self, message: str, percentage: int):
        """İlerleme durumunu güncelle"""
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def _setup_chrome_options(self) -> Options:
        """Chrome seçeneklerini yapılandır"""
        options = Options()

        # User data directory for persistent session
        options.add_argument(f"--user-data-dir={config.CHROME_OPTIONS['user_data_dir']}")

        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Performance options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={config.CHROME_OPTIONS['window_size'][0]},{config.CHROME_OPTIONS['window_size'][1]}")

        # Download settings
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        return options

    def start_browser(self) -> bool:
        """Tarayıcıyı başlat"""
        try:
            self._update_progress("Tarayıcı başlatılıyor...", 5)

            options = self._setup_chrome_options()
            self.driver = webdriver.Chrome(options=options)

            # Anti-detection script
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """
            })

            self.wait = WebDriverWait(self.driver, config.TIMEOUTS['element_wait'])
            self._update_progress("Tarayıcı başlatıldı", 10)
            return True

        except Exception as e:
            logger.error(f"Tarayıcı başlatma hatası: {e}")
            return False

    def navigate_to_gemini(self) -> bool:
        """Gemini sayfasına git"""
        try:
            self._update_progress("Gemini'ye gidiliyor...", 15)
            self.driver.get(config.GEMINI_URL)
            time.sleep(8)  # Sayfanın tam yüklenmesini bekle

            # Login kontrolü - eğer login sayfasındaysak kullanıcıya bilgi ver
            if "accounts.google" in self.driver.current_url:
                self._update_progress("Google hesabına giriş yapmanız gerekiyor. Lütfen tarayıcıda giriş yapın.", 15)
                # Kullanıcının giriş yapmasını bekle (max 2 dakika)
                for _ in range(24):  # 24 * 5 = 120 saniye
                    time.sleep(5)
                    if "gemini.google.com" in self.driver.current_url:
                        break
                else:
                    logger.warning("Login timeout - kullanıcı giriş yapmadı")
                    return False

            self._update_progress("Gemini sayfası yüklendi", 20)
            return True

        except Exception as e:
            logger.error(f"Gemini navigasyon hatası: {e}")
            return False

    def _find_input_element(self):
        """Prompt input alanını bul"""
        selectors = [
            (By.CSS_SELECTOR, 'div[contenteditable="true"].ql-editor'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"][data-placeholder]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"]'),
            (By.CSS_SELECTOR, 'p[data-placeholder]'),
            (By.CSS_SELECTOR, '.input-area textarea'),
            (By.CSS_SELECTOR, 'textarea'),
            (By.TAG_NAME, 'rich-textarea'),
            (By.XPATH, "//div[@contenteditable='true']"),
            (By.XPATH, "//div[contains(@class,'ql-editor')]"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except:
                continue

        # Son çare: herhangi bir contenteditable element
        try:
            elements = self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']")
            for el in elements:
                if el.is_displayed():
                    return el
        except:
            pass

        raise NoSuchElementException("Prompt input alanı bulunamadı")

    def _find_send_button(self):
        """Gönder butonunu bul"""
        selectors = [
            (By.CSS_SELECTOR, 'button[data-test-id="send-button"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Send"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Gönder"]'),
            (By.CSS_SELECTOR, 'button.send-button'),
            (By.CSS_SELECTOR, 'button[mattooltip*="Send"]'),
            (By.CSS_SELECTOR, 'button[mat-icon-button]'),
            (By.CSS_SELECTOR, 'button.mdc-icon-button'),
            (By.CSS_SELECTOR, '.send-button-container button'),
            (By.CSS_SELECTOR, '[data-action="send"] button'),
            (By.XPATH, "//button[contains(@aria-label,'Send')]"),
            (By.XPATH, "//button[contains(@aria-label,'Gönder')]"),
            (By.XPATH, "//button[contains(@class,'send')]"),
            (By.XPATH, "//button[@data-test-id='send-button']"),
            (By.XPATH, "//button[.//mat-icon[contains(text(),'send')]]"),
            (By.XPATH, "//button[.//span[contains(text(),'Send')]]"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        logger.info(f"Gönder butonu bulundu: {selector}")
                        return element
            except:
                continue

        # Son çare: Tüm butonları tara
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                try:
                    aria = btn.get_attribute('aria-label') or ''
                    class_name = btn.get_attribute('class') or ''
                    test_id = btn.get_attribute('data-test-id') or ''
                    inner_text = btn.text.lower() if btn.text else ''

                    if ('send' in aria.lower() or 'gönder' in aria.lower() or
                        'submit' in class_name.lower() or 'send' in class_name.lower() or
                        'send' in test_id.lower() or 'send' in inner_text):
                        if btn.is_displayed() and btn.is_enabled():
                            logger.info(f"Gönder butonu bulundu (fallback): aria={aria}, class={class_name}")
                            return btn
                except:
                    continue
        except:
            pass

        # Enter tuşuyla gönderme alternatifi - butonu None döndür, send_prompt bunu handle edecek
        logger.info("Gönder butonu bulunamadı, Enter tuşu kullanılacak")
        return None

    def send_prompt(self, prompt: str, add_image_suffix: bool = True) -> bool:
        """Prompt gönder"""
        try:
            # Add image suffix if needed
            if add_image_suffix:
                full_prompt = f"{prompt}, {config.IMAGE_SUFFIX}"
            else:
                full_prompt = prompt

            self._update_progress(f"Prompt gönderiliyor: {prompt[:50]}...", 30)

            # Sayfanın hazır olmasını bekle
            time.sleep(3)

            # Find and click input
            input_element = self._find_input_element()
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_element)
            time.sleep(0.5)

            # Click with JavaScript if regular click fails
            try:
                input_element.click()
            except:
                self.driver.execute_script("arguments[0].click();", input_element)
            time.sleep(0.5)

            # Clear existing text
            try:
                input_element.send_keys(Keys.COMMAND + "a")  # Mac
                input_element.send_keys(Keys.DELETE)
            except:
                try:
                    input_element.send_keys(Keys.CONTROL + "a")  # Windows/Linux
                    input_element.send_keys(Keys.DELETE)
                except:
                    pass
            time.sleep(0.3)

            # Type prompt
            input_element.send_keys(full_prompt)
            time.sleep(1.5)

            # Try to find and click send button
            send_button = self._find_send_button()
            sent = False

            if send_button:
                try:
                    send_button.click()
                    sent = True
                    logger.info("Prompt gönderildi (buton ile)")
                except:
                    try:
                        # JavaScript click as fallback
                        self.driver.execute_script("arguments[0].click();", send_button)
                        sent = True
                        logger.info("Prompt gönderildi (JS click ile)")
                    except:
                        pass

            # Enter tuşuyla gönderme (buton bulunamadıysa veya click başarısız olduysa)
            if not sent:
                logger.info("Enter tuşuyla gönderiliyor...")
                # Önce input alanına tekrar tıkla
                try:
                    input_element.click()
                except:
                    self.driver.execute_script("arguments[0].focus();", input_element)
                time.sleep(0.3)

                # Enter tuşu ile gönder
                input_element.send_keys(Keys.RETURN)
                time.sleep(0.5)

                # Eğer hala gönderilmediyse, alternatif Enter yöntemleri dene
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.RETURN).perform()
                logger.info("Prompt gönderildi (Enter tuşu ile)")

            self._update_progress("Prompt gönderildi, yanıt bekleniyor...", 35)
            time.sleep(3)  # Wait for request to be sent
            return True

        except Exception as e:
            logger.error(f"Prompt gönderme hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _count_generated_images(self) -> int:
        """Sayfadaki mevcut görsel sayısını say"""
        count = 0
        try:
            images = self._find_generated_images()
            count = len(images)
        except:
            pass
        return count

    def wait_for_image_generation(self, previous_count: int = 0) -> bool:
        """Yeni görsel oluşturulmasını bekle"""
        try:
            self._update_progress("Görsel oluşturuluyor...", 40)

            # Yeni görsel gelene kadar bekle (eski görsel sayısından fazla olmalı)
            max_wait = config.TIMEOUTS['image_generation']
            start_time = time.time()
            check_count = 0

            logger.info(f"Görsel bekleniyor - önceki sayı: {previous_count}, max bekleme: {max_wait}s")

            while time.time() - start_time < max_wait:
                current_count = self._count_generated_images()
                elapsed = int(time.time() - start_time)
                check_count += 1

                # Her 10 kontrolde bir log at
                if check_count % 5 == 0:
                    logger.info(f"Görsel bekleniyor... [{elapsed}s/{max_wait}s] önceki={previous_count}, şimdiki={current_count}")

                # Yeni görsel oluştuysa
                if current_count > previous_count:
                    self._update_progress("Görsel oluşturuldu!", 60)
                    logger.info(f"YENİ GÖRSEL TESPİT EDİLDİ! önceki={previous_count}, şimdiki={current_count}, süre={elapsed}s")
                    time.sleep(3)  # Görsel tamamen yüklenmesi için bekle
                    return True

                # Loading/generating indicator kontrolü
                try:
                    loading = self.driver.find_elements(By.CSS_SELECTOR,
                        '.loading, .generating, [class*="loading"], [class*="progress"], mat-spinner')
                    if loading:
                        logger.info(f"Loading indicator bulundu, bekleniyor... [{elapsed}s]")
                except:
                    pass

                time.sleep(2)  # 2 saniye bekle ve tekrar kontrol et

            logger.error(f"TIMEOUT! Görsel {max_wait}s içinde oluşturulamadı - önceki: {previous_count}, şimdiki: {self._count_generated_images()}")
            return False

        except Exception as e:
            logger.error(f"Görsel bekleme hatası: {e}")
            return False

    def download_image(self, filename: str) -> Optional[str]:
        """Görseli indir - Çoklu yöntem"""
        try:
            self._update_progress("Görsel indiriliyor...", 65)

            # Önce görseli bul
            generated_images = self._find_generated_images()
            if not generated_images:
                logger.warning("Oluşturulmuş görsel bulunamadı")
                return None

            # En son oluşturulmuş görseli al
            target_image = generated_images[-1]

            # ÖNCEKİ DOSYALARI KAYDET - indirme öncesi
            files_before = self._get_files_in_dirs()
            logger.info(f"İndirme öncesi dosya sayısı: {len(files_before)}")

            # YÖNTEM 1: Görselin üzerine gelip indirme butonunu bul
            try:
                # Hover over image
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(target_image).perform()
                time.sleep(1)

                # Download button selectors
                download_selectors = [
                    'button[data-test-id="download-generated-image-button"]',
                    'button[data-test-id="image-download-button"]',
                    'button[aria-label*="download" i]',
                    'button[aria-label*="Download" i]',
                    'button[aria-label*="indir" i]',
                    '[data-tooltip*="download" i]',
                    'button.download-button',
                    'mat-icon-button[aria-label*="download" i]',
                ]

                download_clicked = False
                for selector in download_selectors:
                    try:
                        btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        logger.info(f"Selector '{selector}': {len(btns)} buton bulundu")
                        for btn in btns:
                            if btn.is_displayed():
                                btn.click()
                                download_clicked = True
                                logger.info(f"İNDİRME BUTONU TIKLANDI: {selector}")
                                time.sleep(2)

                                # Eğer dropdown açıldıysa, asıl indirme butonunu bul
                                try:
                                    menu_items = self.driver.find_elements(By.CSS_SELECTOR,
                                        'button[role="menuitem"], [role="option"], .mat-menu-item')
                                    for item in menu_items:
                                        text = item.text.lower()
                                        if 'download' in text or 'indir' in text or 'save' in text:
                                            item.click()
                                            logger.info("Dropdown menüsünden indirme seçildi")
                                            time.sleep(config.TIMEOUTS['download_wait'])
                                            break
                                except:
                                    pass

                                break
                    except:
                        continue
                if not download_clicked:
                    logger.warning("HİÇBİR İNDİRME BUTONU TIKLANAMIYOR!")
            except Exception as e:
                logger.warning(f"Hover/click yöntemi başarısız: {e}")

            # İndirmenin tamamlanmasını bekle
            time.sleep(config.TIMEOUTS['download_wait'])

            # YENİ DOSYAYI BUL - önceki dosyalarla karşılaştır
            downloaded_file = self._get_latest_download(files_before=files_before)
            if downloaded_file:
                new_path = os.path.join(self.project_dir, filename)
                # Dosya zaten varsa sil
                if os.path.exists(new_path):
                    os.remove(new_path)
                shutil.move(downloaded_file, new_path)
                logger.info(f"Görsel kaydedildi: {new_path} ({os.path.getsize(new_path)} bytes)")
                self._update_progress(f"Görsel kaydedildi: {filename}", 70)
                return new_path

            logger.warning("İndirilen dosya bulunamadı")
            return None

        except Exception as e:
            logger.error(f"Görsel indirme hatası: {e}")
            return None

    def _find_generated_images(self):
        """Oluşturulmuş görselleri bul"""
        images = []
        selectors = [
            'img[data-test-id="generated-image"]',
            'img[alt*="Generated"]',
            'img[alt*="generated"]',
            '.generated-image img',
            'message-content img',
            'model-response img',
        ]

        for selector in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                images.extend([img for img in found if img.is_displayed()])
            except:
                continue

        # Fallback: Blob URL'li görselleri bul
        if not images:
            try:
                all_imgs = self.driver.find_elements(By.TAG_NAME, 'img')
                for img in all_imgs:
                    src = img.get_attribute('src') or ''
                    if ('blob:' in src or 'generated' in src.lower() or
                        img.get_attribute('alt') and 'generated' in img.get_attribute('alt').lower()):
                        if img.is_displayed() and img.size['width'] > 100:
                            images.append(img)
            except:
                pass

        return images

    def _get_files_in_dirs(self) -> set:
        """Tüm indirme klasörlerindeki dosyaları al"""
        files = set()
        extensions = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"]

        search_dirs = []
        if self.download_dir and os.path.exists(self.download_dir):
            search_dirs.append(self.download_dir)
        search_dirs.append(os.path.expanduser("~/Downloads"))

        for search_dir in search_dirs:
            for ext in extensions:
                files.update(glob.glob(os.path.join(search_dir, ext)))

        return files

    def _get_latest_download(self, files_before: set = None, max_wait: int = 30) -> Optional[str]:
        """En son indirilen dosyayı bul - önceki dosya listesiyle karşılaştır"""
        try:
            logger.info(f"İndirme bekleniyor... (max {max_wait}s, önceki dosya sayısı: {len(files_before) if files_before else 0})")

            # Birkaç kez dene (indirme gecikmeli olabilir)
            for attempt in range(max_wait // 2):
                # Eğer önceki dosya listesi verilmişse, yeni dosyayı bul
                if files_before is not None:
                    current_files = self._get_files_in_dirs()
                    new_files = current_files - files_before

                    # Devam eden indirmeleri kontrol et (.crdownload)
                    downloads_dir = os.path.expanduser("~/Downloads")
                    crdownloads = glob.glob(os.path.join(downloads_dir, "*.crdownload"))
                    if crdownloads and attempt < (max_wait // 2) - 1:
                        logger.info(f"İndirme devam ediyor ({len(crdownloads)} .crdownload dosyası)")
                        time.sleep(2)
                        continue

                    if new_files:
                        newest = max(new_files, key=os.path.getctime)
                        logger.info(f"YENİ DOSYA BULUNDU: {newest}")
                        return newest
                    elif attempt % 3 == 0:
                        logger.info(f"Henüz yeni dosya yok (şimdiki: {len(current_files)}, önceki: {len(files_before)})")

                # Yaşa göre kontrol
                search_dirs = []
                if self.download_dir and os.path.exists(self.download_dir):
                    search_dirs.append(self.download_dir)
                search_dirs.append(os.path.expanduser("~/Downloads"))

                extensions = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"]

                for search_dir in search_dirs:
                    dir_files = []
                    for ext in extensions:
                        dir_files.extend(glob.glob(os.path.join(search_dir, ext)))

                    if dir_files:
                        latest = max(dir_files, key=os.path.getctime)
                        file_age = time.time() - os.path.getctime(latest)

                        if file_age < 60:  # Son 60 saniye
                            logger.info(f"DOSYA BULUNDU (yaşa göre): {latest} ({file_age:.1f}s)")
                            return latest

                # Bulunamadı, bekle ve tekrar dene
                if attempt < (max_wait // 2) - 1:
                    logger.info(f"Dosya bekleniyor... ({attempt + 1})")
                    time.sleep(2)

            logger.warning("Yeni görsel dosyası bulunamadı")
            return None
        except Exception as e:
            logger.error(f"Download dosyası bulma hatası: {e}")
            return None

    def remove_watermark_locally(self, image_path: str, output_path: str) -> bool:
        """Görseldeki Gemini watermark'ını (yıldız ikonu) otomatik tespit edip temizle"""
        try:
            import cv2
            import numpy as np

            self._update_progress("Watermark temizleniyor (OpenCV inpainting)...", 75)

            # Görseli oku
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Görsel okunamadı: {image_path}")
                return False

            height, width = img.shape[:2]

            # Sağ alt köşeyi al (watermark burada)
            corner_size = 200
            corner = img[height-corner_size:height, width-corner_size:width].copy()
            gray = cv2.cvtColor(corner, cv2.COLOR_BGR2GRAY)

            # Kenar tespiti ile watermark'ı bul
            edges = cv2.Canny(gray, 10, 50)

            # Konturları bul
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # En büyük konturu al (watermark yıldızı)
                largest = max(contours, key=cv2.contourArea)

                # Bu kontur için filled mask oluştur
                corner_mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.drawContours(corner_mask, [largest], -1, 255, -1)

                # Biraz genişlet (kenarları da kapsasın)
                kernel = np.ones((5, 5), np.uint8)
                corner_mask = cv2.dilate(corner_mask, kernel, iterations=2)

                # Ana görsel için mask oluştur
                mask = np.zeros((height, width), dtype=np.uint8)
                y_start = height - corner_size
                x_start = width - corner_size
                mask[y_start:height, x_start:width] = corner_mask

                # Hassas inpainting
                result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

                # İkinci geçiş - daha ince ayar
                small_kernel = np.ones((3, 3), np.uint8)
                small_mask = cv2.erode(mask, small_kernel, iterations=1)
                result = cv2.inpaint(result, small_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)

                logger.info(f"Watermark otomatik tespit edildi ve temizlendi")
            else:
                # Kontur bulunamazsa orijinali kullan
                logger.warning("Watermark tespit edilemedi, orijinal kullanılıyor")
                result = img

            # Kaydet
            cv2.imwrite(output_path, result)
            logger.info(f"Watermark temizlendi: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Watermark temizleme hatası: {e}")
            # Hata olursa orijinali kopyala
            try:
                shutil.copy(image_path, output_path)
                logger.info("Watermark temizlenemedi, orijinal kopyalandı")
                return True
            except:
                return False

    def start_new_chat(self) -> bool:
        """Yeni chat başlat"""
        try:
            # Yeni chat butonunu bul ve tıkla
            new_chat_selectors = [
                'button[aria-label*="New chat"]',
                'button[aria-label*="Yeni sohbet"]',
                'button[aria-label*="New conversation"]',
                'a[href="/app"]',
                '[data-test-id="new-chat-button"]',
            ]

            for selector in new_chat_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            logger.info(f"Yeni chat başlatıldı: {selector}")
                            time.sleep(3)
                            return True
                except:
                    continue

            # Alternatif: Sayfayı yenile
            logger.info("Yeni chat butonu bulunamadı, sayfa yenileniyor...")
            self.driver.get(config.GEMINI_URL)
            time.sleep(5)
            return True

        except Exception as e:
            logger.error(f"Yeni chat başlatma hatası: {e}")
            return False

    def generate_single_image(self, prompt: str, image_index: int, start_new_chat: bool = True) -> Dict[str, Any]:
        """Tek bir görsel oluştur - RETRY YOK, tek deneme

        Args:
            prompt: Görsel prompt'u
            image_index: Görsel numarası
            start_new_chat: Yeni chat başlatılsın mı (varsayılan True)
        """
        result = {
            "prompt": prompt,
            "original_path": None,
            "cleaned_path": None,
            "success": False,
            "error": None
        }

        try:
            self._update_progress(f"Görsel {image_index} oluşturuluyor...", 25 + (image_index * 20))
            logger.info(f"=== Görsel {image_index} oluşturma ===")

            # Yeni chat başlat (istenirse)
            if start_new_chat:
                self.start_new_chat()

            # Mevcut görsel sayısını say
            previous_image_count = self._count_generated_images()

            # Prompt gönder
            if not self.send_prompt(prompt):
                result["error"] = "Prompt gönderilemedi"
                return result

            # Görsel oluşturulmasını bekle
            if not self.wait_for_image_generation(previous_count=previous_image_count):
                result["error"] = "Görsel oluşturulamadı"
                return result

            # Görseli indir
            original_filename = f"image_{image_index}_original.png"
            original_path = self.download_image(original_filename)

            logger.info(f"DEBUG: original_path = {original_path}")

            if original_path and os.path.exists(original_path) and os.path.getsize(original_path) > 0:
                result["original_path"] = original_path

                # Watermark temizleme
                self._update_progress(f"Görsel {image_index} watermark temizleniyor...", 75 + (image_index * 5))
                cleaned_filename = f"image_{image_index}_cleaned.png"
                cleaned_path = os.path.join(self.project_dir, cleaned_filename)

                if self.remove_watermark_locally(original_path, cleaned_path):
                    result["cleaned_path"] = cleaned_path

                result["success"] = True
                logger.info(f"BAŞARILI! Görsel {image_index}: {original_path}")
            else:
                result["error"] = "Görsel indirilemedi"
                logger.warning(f"Görsel {image_index} indirilemedi")

        except Exception as e:
            logger.error(f"Görsel {image_index} hatası: {e}")
            result["error"] = str(e)

        return result

    def process_video_script(self, script: str) -> Dict[str, Any]:
        """Video script'ini işle ve görselleri oluştur"""
        results = {
            "project_name": self.project_name,
            "project_dir": self.project_dir,
            "images": [],
            "thumbnails": [],
            "videos": [],
            "voice": None,
            "success": False,
            "error": None
        }

        try:
            # Script'i parse et
            self._update_progress("Script analiz ediliyor...", 5)
            parsed = self._parse_script(script)

            # Proje metadata'sını kaydet (beklenen sayılar + tüm promptlar)
            image_prompts = {}
            for i, prompt in enumerate(parsed.get("images", []), 1):
                image_prompts[str(i)] = prompt

            video_prompts = {}
            for i, video_data in enumerate(parsed.get("videos", []), 1):
                video_prompts[str(i)] = video_data.get("prompt", "") if isinstance(video_data, dict) else video_data

            thumbnail_prompts = {}
            for i, prompt in enumerate(parsed.get("thumbnails", []), 1):
                thumbnail_prompts[str(i)] = prompt

            project_meta = {
                "expected_images": len(parsed.get("images", [])),
                "expected_videos": len(parsed.get("videos", [])),
                "expected_thumbnails": len(parsed.get("thumbnails", [])),
                "image_prompts": image_prompts,
                "video_prompts": video_prompts,
                "thumbnail_prompts": thumbnail_prompts,
                "voice": parsed.get("voice", {}),
                "created_at": datetime.now().isoformat()
            }
            meta_path = os.path.join(self.project_dir, "project.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(project_meta, f, indent=2, ensure_ascii=False)
            logger.info(f"Proje metadata kaydedildi: {meta_path}")

            # Tarayıcıyı başlat
            if not self.start_browser():
                raise Exception("Tarayıcı başlatılamadı")

            # Gemini'ye git
            if not self.navigate_to_gemini():
                raise Exception("Gemini'ye gidilemedi")

            # Görselleri oluştur
            for i, image_prompt in enumerate(parsed.get("images", []), 1):
                self._update_progress(f"Görsel {i}/{len(parsed.get('images', []))} işleniyor...", 20 + (i * 10))
                # İlk görsel için yeni chat başlatma, sonrakiler için başlat
                should_start_new_chat = (i > 1)
                image_result = self.generate_single_image(image_prompt, i, start_new_chat=should_start_new_chat)
                results["images"].append(image_result)

            # Thumbnail'leri oluştur (16:9 aspect ratio)
            thumbnail_prompts = parsed.get("thumbnails", [])
            if thumbnail_prompts:
                self._update_progress(f"Thumbnail oluşturuluyor...", 70)
                for i, thumb_prompt in enumerate(thumbnail_prompts, 1):
                    # Thumbnail için 16:9 aspect ratio ekle
                    thumb_prompt_full = f"{thumb_prompt}, horizontal 16:9 aspect ratio, landscape orientation, 1920x1080"

                    # Yeni chat başlat
                    self.start_new_chat()

                    # Mevcut görsel sayısını say
                    previous_count = self._count_generated_images()

                    # Prompt gönder (image suffix ekleme - kendi formatı var)
                    if not self.send_prompt(thumb_prompt_full, add_image_suffix=False):
                        logger.warning(f"Thumbnail {i} prompt gönderilemedi")
                        continue

                    # Görsel oluşturulmasını bekle
                    if not self.wait_for_image_generation(previous_count=previous_count):
                        logger.warning(f"Thumbnail {i} oluşturulamadı")
                        continue

                    # İndir
                    thumb_filename = f"thumbnail_{i}_original.png"
                    thumb_path = self.download_image(thumb_filename)

                    if thumb_path and os.path.exists(thumb_path):
                        # Watermark temizle
                        cleaned_filename = f"thumbnail_{i}_cleaned.png"
                        cleaned_path = os.path.join(self.project_dir, cleaned_filename)

                        if self.remove_watermark_locally(thumb_path, cleaned_path):
                            results["thumbnails"].append({
                                "prompt": thumb_prompt,
                                "original_path": thumb_path,
                                "cleaned_path": cleaned_path,
                                "success": True
                            })
                            logger.info(f"Thumbnail {i} başarılı: {cleaned_path}")
                        else:
                            results["thumbnails"].append({
                                "prompt": thumb_prompt,
                                "original_path": thumb_path,
                                "cleaned_path": None,
                                "success": True
                            })
                    else:
                        results["thumbnails"].append({
                            "prompt": thumb_prompt,
                            "success": False,
                            "error": "İndirilemedi"
                        })

            # Video bilgilerini kaydet (gerçek video oluşturma yapılmıyor)
            results["voice"] = parsed.get("voice", {})

            # Video oluşturma - Grok ile
            video_prompts = parsed.get("videos", [])
            if video_prompts and len(results["images"]) > 0:
                # Index bazlı eşleşme: video_i -> image_i
                # Başarısız görseller için video atlanır
                image_video_pairs = []
                for i, img in enumerate(results["images"]):
                    if img.get("success") and img.get("cleaned_path"):
                        # Video prompt'u varsa kullan, yoksa son prompt'u tekrarla
                        video_prompt = video_prompts[i].get("prompt", "") if i < len(video_prompts) else video_prompts[-1].get("prompt", "")
                        image_video_pairs.append({
                            "index": i + 1,
                            "image_path": img["cleaned_path"],
                            "video_prompt": video_prompt
                        })

                if image_video_pairs:
                    self._update_progress("Video oluşturma başlıyor (Grok)...", 80)
                    try:
                        from grok_video_generator import create_videos_from_images_indexed

                        video_results = create_videos_from_images_indexed(
                            image_video_pairs=image_video_pairs,
                            project_dir=self.project_dir,
                            progress_callback=self.progress_callback
                        )
                        results["videos"] = video_results

                        # Final Render - Videoları birleştir, ses ve altyazı ekle
                        voice_info = parsed.get("voice", {})
                        if voice_info.get("text"):
                            successful_videos = [v.get("video_path") for v in video_results if v.get("success") and v.get("video_path")]

                            if successful_videos:
                                self._update_progress("Final render başlıyor...", 85)
                                try:
                                    from video_renderer import render_project

                                    render_result = render_project(
                                        project_dir=self.project_dir,
                                        video_paths=successful_videos,
                                        voice_text=voice_info.get("text", ""),
                                        voice_style=voice_info.get("style", "friendly"),
                                        words_per_subtitle=1,  # Kelime kelime altyazı
                                        progress_callback=self.progress_callback
                                    )

                                    results["final_render"] = render_result
                                    if render_result.get("success"):
                                        results["final_video"] = render_result.get("final_video")
                                        logger.info(f"Final video hazır: {results['final_video']}")
                                    else:
                                        logger.warning(f"Final render hatası: {render_result.get('error')}")

                                except Exception as e:
                                    logger.error(f"Final render hatası: {e}")
                                    results["final_render"] = {"error": str(e), "success": False}

                    except Exception as e:
                        logger.error(f"Video oluşturma hatası: {e}")
                        results["videos"] = [{"error": str(e), "success": False}]
            else:
                results["videos"] = parsed.get("videos", [])

            results["success"] = True
            self._update_progress("Tüm işlemler tamamlandı!", 100)

        except Exception as e:
            logger.error(f"İşlem hatası: {e}")
            results["error"] = str(e)
            results["success"] = False

        return results

    def _parse_script(self, script: str) -> Dict[str, Any]:
        """Video script'ini parse et"""
        result = {
            "images": [],
            "videos": [],
            "thumbnails": [],
            "voice": {}
        }

        lines = script.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()

            if "[IMAGE_" in line:
                current_section = "image"
            elif "[VIDEO_" in line:
                current_section = "video"
            elif "[THUMBNAIL" in line:
                current_section = "thumbnail"
            elif "[VOICE]" in line:
                current_section = "voice"
            elif line.startswith("prompt:"):
                prompt = line.replace("prompt:", "").strip().strip('"\'')
                if current_section == "image":
                    result["images"].append(prompt)
                elif current_section == "video":
                    result["videos"].append({"prompt": prompt})
                elif current_section == "thumbnail":
                    result["thumbnails"].append(prompt)
            elif line.startswith("text:"):
                text = line.replace("text:", "").strip().strip('"\'')
                result["voice"]["text"] = text
            elif line.startswith("style:"):
                style = line.replace("style:", "").strip().strip('"\'')
                result["voice"]["style"] = style

        return result

    def close(self, keep_open: bool = True):
        """Tarayıcıyı kapat"""
        if not keep_open and self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Tarayıcı kapatıldı")
        elif keep_open:
            logger.info("Tarayıcı kontrol için açık bırakıldı")


def run_test(progress_callback: Callable = None) -> Dict[str, Any]:
    """Test promptu ile sistemi test et"""
    test_script = """---VIDEO START---
VIDEO_COUNT: 2
IMAGE_COUNT: 2
[IMAGE_1]
prompt: "ultra-realistic macro shot, soft rim light, dark background, floating glowing particles"
[IMAGE_2]
prompt: "3D exploded diagram, layers floating in space, ambient blue lighting"
[VIDEO_1]
prompt: "cinematic macro intro, slow dolly-in"
[VIDEO_2]
prompt: "exploded 3D animation, layers separating"
[VOICE]
text: "Most people only see the result. Here is what truly happens."
style: "friendly"
---VIDEO END---"""

    generator = GeminiImageGenerator(
        project_name=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        progress_callback=progress_callback
    )

    try:
        results = generator.process_video_script(test_script)
        return results
    finally:
        generator.close(keep_open=True)


if __name__ == "__main__":
    # Direkt çalıştırılırsa test et
    results = run_test()
    print("\n" + "="*50)
    print("TEST SONUÇLARI")
    print("="*50)
    print(f"Başarılı: {results['success']}")
    print(f"Proje klasörü: {results['project_dir']}")
    print(f"Oluşturulan görseller: {len(results['images'])}")
    for i, img in enumerate(results['images'], 1):
        print(f"  Görsel {i}: {'✓' if img['success'] else '✗'} - {img.get('original_path', 'N/A')}")
