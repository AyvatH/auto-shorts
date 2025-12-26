"""
Grok Video Generator - Undetected Chrome
Grok.com/imagine ile görsellerden video oluşturma
Cloudflare bypass için undetected-chromedriver kullanır
"""
import os
import time
import glob
import shutil
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)

import config

logger = logging.getLogger(__name__)


class GrokVideoGenerator:
    """Grok ile görsellerden video oluşturma sınıfı"""

    def __init__(self, project_dir: str = None, progress_callback: Callable = None):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.project_dir = project_dir
        self.progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))
        self.download_dir = os.path.join(self.project_dir, "videos") if project_dir else None

        if self.download_dir:
            os.makedirs(self.download_dir, exist_ok=True)

    def _update_progress(self, message: str, percentage: int):
        """İlerleme durumunu güncelle"""
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def start_browser(self) -> bool:
        """Tarayıcıyı başlat - Undetected Chrome ile Cloudflare bypass"""
        try:
            self._update_progress("Tarayıcı başlatılıyor (Grok Video - Stealth Mode)...", 5)

            # Grok için ayrı profil
            grok_profile = os.path.join(config.BASE_DIR, "chrome_profiles", "grok_profile")
            os.makedirs(grok_profile, exist_ok=True)

            # Undetected Chrome options
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={grok_profile}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"--window-size={config.CHROME_OPTIONS['window_size'][0]},{config.CHROME_OPTIONS['window_size'][1]}")

            # Download settings
            if self.download_dir:
                prefs = {
                    "download.default_directory": self.download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                }
                options.add_experimental_option("prefs", prefs)

            # Undetected Chrome başlat - Cloudflare'ı bypass eder
            self.driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                version_main=None  # Otomatik versiyon algılama
            )

            self.wait = WebDriverWait(self.driver, config.TIMEOUTS['element_wait'])
            self._update_progress("Tarayıcı başlatıldı (Stealth Mode)", 10)
            return True

        except Exception as e:
            logger.error(f"Tarayıcı başlatma hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def navigate_to_grok_imagine(self) -> bool:
        """Grok Imagine sayfasına git"""
        try:
            self._update_progress("Grok Imagine'e gidiliyor...", 15)

            # Önce ana sayfaya git (Cloudflare challenge için)
            self.driver.get("https://grok.com")
            time.sleep(8)  # Cloudflare challenge için bekle

            # Şimdi imagine sayfasına git
            self.driver.get("https://grok.com/imagine")
            time.sleep(5)

            # Login kontrolü
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()

            # Cloudflare challenge kontrolü
            if "checking your browser" in page_source or "just a moment" in page_source:
                self._update_progress("Cloudflare doğrulaması bekleniyor...", 15)
                time.sleep(10)

            if "login" in current_url.lower() or "x.com" in current_url or "sign in" in page_source:
                self._update_progress("X hesabına giriş yapmanız gerekiyor. Lütfen tarayıcıda giriş yapın.", 15)
                # Kullanıcının giriş yapmasını bekle
                for _ in range(36):  # 3 dakika
                    time.sleep(5)
                    current_url = self.driver.current_url
                    if "grok.com" in current_url:
                        # imagine sayfasına yönlendir
                        if "imagine" not in current_url:
                            self.driver.get("https://grok.com/imagine")
                            time.sleep(3)
                        break
                else:
                    logger.warning("Login timeout")
                    return False

            time.sleep(3)
            self._update_progress("Grok Imagine sayfası yüklendi", 20)
            return True

        except Exception as e:
            logger.error(f"Grok navigasyon hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start_new_chat(self) -> bool:
        """Yeni chat başlat - bir sonraki video için sayfa hazırla"""
        try:
            logger.info("Yeni chat başlatılıyor...")

            # Yöntem 1: New chat butonu ara
            new_chat_selectors = [
                'button[aria-label*="New" i]',
                'button[aria-label*="new chat" i]',
                'a[href*="/imagine"]',
                '[data-testid="new-chat"]',
            ]

            for selector in new_chat_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            logger.info(f"Yeni chat butonu tıklandı: {selector}")
                            time.sleep(3)
                            return True
                except:
                    continue

            # Yöntem 2: Sayfayı yenile
            logger.info("Yeni chat butonu bulunamadı, sayfa yenileniyor...")
            self.driver.get("https://grok.com/imagine")
            time.sleep(5)

            # Sayfanın yüklenmesini bekle
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"], textarea'))
            )

            logger.info("Sayfa yenilendi, hazır")
            return True

        except Exception as e:
            logger.error(f"Yeni chat başlatma hatası: {e}")
            return False

    def upload_image(self, image_path: str) -> bool:
        """Görseli Grok'a yükle"""
        try:
            self._update_progress(f"Görsel yükleniyor: {os.path.basename(image_path)}", 30)

            # Dosya yükleme input'unu bul
            upload_selectors = [
                'input[type="file"]',
                'input[accept*="image"]',
                '[data-testid="file-input"]',
            ]

            file_input = None
            for selector in upload_selectors:
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for inp in inputs:
                        if inp.get_attribute('type') == 'file':
                            file_input = inp
                            break
                    if file_input:
                        break
                except:
                    continue

            if not file_input:
                # Yükleme butonu ile aç
                upload_btn_selectors = [
                    'button[aria-label*="upload" i]',
                    'button[aria-label*="image" i]',
                    'button[aria-label*="Add" i]',
                    '[data-testid*="upload"]',
                    '.upload-button',
                ]

                for selector in upload_btn_selectors:
                    try:
                        btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in btns:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(1)
                                break
                    except:
                        continue

                # Tekrar file input ara
                for selector in upload_selectors:
                    try:
                        inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for inp in inputs:
                            file_input = inp
                            break
                        if file_input:
                            break
                    except:
                        continue

            if file_input:
                # Dosyayı yükle
                file_input.send_keys(os.path.abspath(image_path))
                time.sleep(3)
                self._update_progress("Görsel yüklendi", 40)
                return True
            else:
                logger.error("Dosya yükleme input'u bulunamadı")
                return False

        except Exception as e:
            logger.error(f"Görsel yükleme hatası: {e}")
            return False

    def _save_debug_screenshot(self, name: str):
        """Debug için screenshot kaydet"""
        try:
            screenshot_path = os.path.join(self.project_dir or "/tmp", f"debug_{name}_{int(time.time())}.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Debug screenshot kaydedildi: {screenshot_path}")
        except Exception as e:
            logger.error(f"Screenshot kaydetme hatası: {e}")

    def _find_prompt_input(self):
        """Prompt input alanını bul"""
        # Görsel yüklendikten sonra biraz bekle
        time.sleep(2)

        selectors = [
            # Grok specific
            (By.CSS_SELECTOR, 'textarea[placeholder*="Describe" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="motion" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="animate" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="video" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="prompt" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="what" i]'),
            (By.CSS_SELECTOR, 'textarea[placeholder*="how" i]'),
            # Generic
            (By.CSS_SELECTOR, 'textarea[data-testid]'),
            (By.CSS_SELECTOR, 'div[role="textbox"]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"]'),
            (By.CSS_SELECTOR, 'textarea'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
            # XPath
            (By.XPATH, "//textarea"),
            (By.XPATH, "//div[@contenteditable='true']"),
            (By.XPATH, "//div[@role='textbox']"),
            (By.XPATH, "//input[@type='text']"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        # Element boyutunu kontrol et - çok küçük olmasın
                        size = element.size
                        if size.get('width', 0) > 50 and size.get('height', 0) > 20:
                            logger.info(f"Prompt input bulundu: {selector} (size: {size})")
                            return element
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue

        # Hata ayıklama için sayfadaki tüm textarea ve input'ları listele
        logger.error("Prompt input bulunamadı! Sayfadaki elementler:")
        self._save_debug_screenshot("prompt_input_not_found")
        try:
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for ta in textareas:
                logger.error(f"  textarea: placeholder='{ta.get_attribute('placeholder')}' visible={ta.is_displayed()} size={ta.size}")
            divs = self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable]")
            for div in divs:
                logger.error(f"  contenteditable div: class='{div.get_attribute('class')}' visible={div.is_displayed()}")
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
            for inp in inputs:
                logger.error(f"  input: placeholder='{inp.get_attribute('placeholder')}' visible={inp.is_displayed()}")
        except:
            pass

        raise NoSuchElementException("Prompt input alanı bulunamadı")

    def send_video_prompt(self, prompt: str) -> bool:
        """Video prompt'unu gönder"""
        try:
            self._update_progress(f"Video prompt gönderiliyor: {prompt[:50]}...", 50)
            time.sleep(2)

            # Input bul
            input_element = self._find_prompt_input()
            logger.info(f"Input element bulundu, prompt yazılacak: {prompt}")

            # Tıkla ve yaz
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

            # Prompt yaz - önce normal yolla dene
            input_element.send_keys(prompt)
            time.sleep(1)

            # Yazıldığını doğrula
            written_text = input_element.get_attribute('value') or input_element.text or ""
            logger.info(f"Yazılan text (send_keys): '{written_text[:50] if written_text else 'BOŞ'}'")

            # Eğer boşsa JavaScript ile dene
            if not written_text.strip():
                logger.info("send_keys çalışmadı, JavaScript ile deneniyor...")
                tag_name = input_element.tag_name.lower()
                if tag_name == 'textarea' or tag_name == 'input':
                    self.driver.execute_script(f"arguments[0].value = arguments[1];", input_element, prompt)
                    # Input event tetikle
                    self.driver.execute_script("""
                        var event = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                    """, input_element)
                else:
                    # contenteditable div
                    self.driver.execute_script(f"arguments[0].innerText = arguments[1];", input_element, prompt)
                    self.driver.execute_script("""
                        var event = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                    """, input_element)
                time.sleep(0.5)
                written_text = input_element.get_attribute('value') or input_element.text or input_element.get_attribute('innerText') or ""
                logger.info(f"Yazılan text (JS): '{written_text[:50] if written_text else 'BOŞ'}'")

            # Screenshot al - debug için
            self._save_debug_screenshot("after_prompt_write")

            # Gönder butonu bul ve tıkla
            send_selectors = [
                'button[type="submit"]',
                'button[aria-label*="Generate" i]',
                'button[aria-label*="generate" i]',
                'button[aria-label*="Create" i]',
                'button[aria-label*="create" i]',
                'button[aria-label*="Send" i]',
                'button[aria-label*="send" i]',
                'button[aria-label*="Gönder" i]',
                'button[aria-label*="Oluştur" i]',
                'button[data-testid*="submit"]',
                'button[data-testid*="generate"]',
                'button[data-testid*="send"]',
            ]

            sent = False
            for selector in send_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in btns:
                        if btn.is_displayed() and btn.is_enabled():
                            logger.info(f"Gönder butonu bulundu: {selector}, text: '{btn.text}'")
                            btn.click()
                            sent = True
                            logger.info(f"Gönder butonu tıklandı!")
                            break
                    if sent:
                        break
                except Exception as e:
                    logger.debug(f"Selector failed: {selector}: {e}")
                    continue

            # XPath ile dene
            if not sent:
                xpath_selectors = [
                    "//button[contains(text(), 'Generate')]",
                    "//button[contains(text(), 'Create')]",
                    "//button[contains(text(), 'Oluştur')]",
                    "//button[contains(text(), 'Gönder')]",
                    "//button[.//span[contains(text(), 'Generate')]]",
                    "//button[.//span[contains(text(), 'Create')]]",
                    "//button[contains(@class, 'submit')]",
                    "//button[contains(@class, 'primary')]",
                    "//button[contains(@class, 'generate')]",
                    "//button[@type='submit']",
                ]
                for xpath in xpath_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, xpath)
                        for btn in btns:
                            if btn.is_displayed() and btn.is_enabled():
                                logger.info(f"XPath ile buton bulundu: {xpath}, text: '{btn.text}'")
                                btn.click()
                                sent = True
                                break
                        if sent:
                            break
                    except:
                        continue

            # Hala bulunamadıysa tüm butonları logla
            if not sent:
                logger.warning("Gönder butonu bulunamadı! Sayfadaki butonlar:")
                self._save_debug_screenshot("generate_button_not_found")
                try:
                    all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                    for btn in all_buttons[:20]:
                        aria = btn.get_attribute('aria-label') or ''
                        text = btn.text[:30] if btn.text else ''
                        cls = btn.get_attribute('class') or ''
                        visible = btn.is_displayed()
                        enabled = btn.is_enabled()
                        logger.warning(f"  Button: aria='{aria}' text='{text}' class='{cls[:40]}' visible={visible} enabled={enabled}")
                except:
                    pass

                # Son çare: Enter ile gönder
                logger.info("Buton bulunamadı, Enter tuşuyla gönderiliyor...")
                input_element.send_keys(Keys.RETURN)

            self._update_progress("Video oluşturma başlatıldı", 55)
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Prompt gönderme hatası: {e}")
            self._save_debug_screenshot("prompt_send_error")
            import traceback
            traceback.print_exc()
            return False

    def wait_for_video_generation(self) -> bool:
        """Video oluşturulmasını bekle"""
        try:
            self._update_progress("Video oluşturuluyor...", 60)

            max_wait = config.TIMEOUTS.get('video_generation', 180)  # 3 dakika default
            start_time = time.time()

            while time.time() - start_time < max_wait:
                # Video elementi ara
                video_selectors = [
                    'video',
                    'video[src]',
                    '[data-testid*="video"]',
                    '.video-player',
                ]

                for selector in video_selectors:
                    try:
                        videos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for video in videos:
                            src = video.get_attribute('src') or ''
                            if src and video.is_displayed():
                                self._update_progress("Video oluşturuldu!", 80)
                                self._save_debug_screenshot("video_ready")
                                time.sleep(3)
                                return True
                    except:
                        continue

                # Loading indicator kontrolü
                try:
                    loading = self.driver.find_elements(By.CSS_SELECTOR,
                        '.loading, .generating, [class*="loading"], [class*="progress"], [class*="spinner"]')
                    if loading:
                        logger.info("Video oluşturuluyor, bekleniyor...")
                except:
                    pass

                time.sleep(3)

            logger.warning("Video bekleme timeout")
            return False

        except Exception as e:
            logger.error(f"Video bekleme hatası: {e}")
            return False

    def download_video(self, filename: str) -> Optional[str]:
        """Videoyu indir"""
        try:
            self._update_progress("Video indiriliyor...", 85)

            # Video elementi bul
            video_element = None
            video_selectors = ['video[src]', 'video', '[data-testid*="video"] video']

            for selector in video_selectors:
                try:
                    videos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for video in videos:
                        if video.is_displayed():
                            video_element = video
                            break
                    if video_element:
                        break
                except:
                    continue

            # ÖNCEKİ VIDEO DOSYALARINI KAYDET - indirme öncesi
            files_before = self._get_video_files_in_dirs()
            logger.info(f"İndirme öncesi video dosya sayısı: {len(files_before)}")

            # İndirme butonu ara - Grok'un yeni buton selektörleri
            download_selectors = [
                'button[aria-label="İndir"]',  # Türkçe
                'button[aria-label="Download"]',  # İngilizce
                'button[aria-label="Download video"]',
                'button[aria-label*="indir" i]',
                'button[aria-label*="download" i]',
                'button[data-testid*="download"]',
                'a[download]',
                'a[href*=".mp4"]',
                'button svg.lucide-download',  # Lucide icon parent
            ]

            logger.info("İndirme butonu aranıyor...")

            download_clicked = False
            for selector in download_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in btns:
                        if btn.is_displayed():
                            # Butona scroll yap
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(0.5)
                            btn.click()
                            download_clicked = True
                            logger.info(f"İndirme butonu tıklandı: {selector}")
                            time.sleep(config.TIMEOUTS['download_wait'])
                            break
                    if download_clicked:
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # Eğer CSS selector çalışmadıysa XPath dene
            if not download_clicked:
                logger.info("CSS selector çalışmadı, XPath deneniyor...")
                xpath_selectors = [
                    "//button[@aria-label='İndir']",
                    "//button[@aria-label='Download']",
                    "//button[@aria-label='Download video']",
                    "//button[contains(@aria-label, 'indir')]",
                    "//button[contains(@aria-label, 'İndir')]",
                    "//button[contains(@aria-label, 'download')]",
                    "//button[contains(@aria-label, 'Download')]",
                    "//button[.//svg[contains(@class, 'lucide-download')]]",
                    "//button[.//svg[contains(@class, 'download')]]",
                    "//a[contains(@href, '.mp4')]",
                    "//button[.//span[contains(text(), 'İndir')]]",
                    "//button[.//span[contains(text(), 'Download')]]",
                ]

                for xpath in xpath_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, xpath)
                        for btn in btns:
                            if btn.is_displayed():
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                                time.sleep(0.5)
                                btn.click()
                                download_clicked = True
                                logger.info(f"İndirme butonu tıklandı (XPath): {xpath}")
                                time.sleep(config.TIMEOUTS['download_wait'])
                                break
                        if download_clicked:
                            break
                    except Exception as e:
                        logger.debug(f"XPath {xpath} failed: {e}")
                        continue

            # Eğer hala bulunamadıysa, sayfadaki tüm butonları logla
            if not download_clicked:
                logger.warning("İndirme butonu bulunamadı! Sayfadaki butonlar:")
                self._save_debug_screenshot("download_button_not_found")
                try:
                    all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                    for btn in all_buttons[:20]:  # İlk 20 buton
                        aria = btn.get_attribute('aria-label') or ''
                        text = btn.text[:30] if btn.text else ''
                        cls = btn.get_attribute('class') or ''
                        visible = btn.is_displayed()
                        logger.warning(f"  Button: aria='{aria}' text='{text}' class='{cls[:40]}' visible={visible}")

                    # Ayrıca tüm linkleri de kontrol et
                    all_links = self.driver.find_elements(By.CSS_SELECTOR, "a")
                    for link in all_links[:10]:
                        href = link.get_attribute('href') or ''
                        download = link.get_attribute('download') or ''
                        text = link.text[:30] if link.text else ''
                        if '.mp4' in href or download:
                            logger.warning(f"  Link: href='{href[:50]}' download='{download}' text='{text}'")
                except:
                    pass

            # İndirilen dosyayı kontrol et - önceki dosyalarla karşılaştır
            time.sleep(5)
            downloaded_file = self._get_latest_download(files_before=files_before)

            if downloaded_file:
                new_path = os.path.join(self.project_dir, filename)
                shutil.move(downloaded_file, new_path)
                self._update_progress(f"Video kaydedildi: {filename}", 95)
                return new_path

            # Alternatif: Video src'den indir
            if video_element:
                video_src = video_element.get_attribute('src')
                if video_src and video_src.startswith('http'):
                    logger.info(f"Video src'den indiriliyor: {video_src[:50]}...")
                    # JavaScript ile indirme tetikle
                    self.driver.execute_script(f"""
                        var a = document.createElement('a');
                        a.href = '{video_src}';
                        a.download = '{filename}';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    """)
                    time.sleep(5)
                    downloaded_file = self._get_latest_download(files_before=files_before)
                    if downloaded_file:
                        new_path = os.path.join(self.project_dir, filename)
                        shutil.move(downloaded_file, new_path)
                        self._update_progress(f"Video kaydedildi: {filename}", 95)
                        return new_path

            logger.warning("Video indirilemedi")
            return None

        except Exception as e:
            logger.error(f"Video indirme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_video_files_in_dirs(self) -> set:
        """Tüm video klasörlerindeki dosyaları al"""
        files = set()
        extensions = ["*.mp4", "*.webm", "*.mov"]

        search_dirs = []
        if self.download_dir and os.path.exists(self.download_dir):
            search_dirs.append(self.download_dir)
        search_dirs.append(os.path.expanduser("~/Downloads"))

        for search_dir in search_dirs:
            for ext in extensions:
                files.update(glob.glob(os.path.join(search_dir, ext)))

        return files

    def _get_latest_download(self, files_before: set = None) -> Optional[str]:
        """En son indirilen video dosyasını bul - önceki dosya listesiyle karşılaştır"""
        try:
            # Eğer önceki dosya listesi verilmişse, yeni dosyayı bul
            if files_before is not None:
                current_files = self._get_video_files_in_dirs()
                new_files = current_files - files_before

                if new_files:
                    newest = max(new_files, key=os.path.getctime)
                    logger.info(f"YENİ VIDEO DOSYASI BULUNDU: {newest}")
                    return newest
                else:
                    logger.info("Yeni video dosyası yok, yaşa göre kontrol ediliyor...")

            # Fallback: yaşa göre kontrol
            search_dirs = []
            if self.download_dir and os.path.exists(self.download_dir):
                search_dirs.append(self.download_dir)
            search_dirs.append(os.path.expanduser("~/Downloads"))

            extensions = ["*.mp4", "*.webm", "*.mov"]

            for search_dir in search_dirs:
                dir_files = []
                for ext in extensions:
                    dir_files.extend(glob.glob(os.path.join(search_dir, ext)))

                if dir_files:
                    latest = max(dir_files, key=os.path.getctime)
                    file_age = time.time() - os.path.getctime(latest)
                    logger.info(f"Klasör {search_dir}: En yeni video: {latest} (yaş: {file_age:.1f}s)")

                    if file_age < 120:  # Son 2 dakika
                        logger.info(f"VIDEO DOSYASI BULUNDU (yaşa göre): {latest}")
                        return latest

            logger.warning("Yeni video dosyası bulunamadı")
            return None
        except Exception as e:
            logger.error(f"Download dosyası bulma hatası: {e}")
            return None

    def generate_video_from_image(self, image_path: str, video_prompt: str, output_filename: str) -> Dict[str, Any]:
        """Görsel ve prompt'tan video oluştur - RETRY YOK, tek deneme"""
        result = {
            "image_path": image_path,
            "video_prompt": video_prompt,
            "video_path": None,
            "success": False,
            "error": None
        }

        logger.info(f"=== Video oluşturma: {output_filename} ===")

        try:
            # 1. Görseli yükle
            if not self.upload_image(image_path):
                result["error"] = "Görsel yüklenemedi"
                return result

            # 2. Video prompt gönder
            if not self.send_video_prompt(video_prompt):
                result["error"] = "Video prompt gönderilemedi"
                return result

            # 3. Video oluşturulmasını bekle
            if not self.wait_for_video_generation():
                result["error"] = "Video oluşturulamadı - timeout"
                return result

            # 4. Videoyu indir
            video_path = self.download_video(output_filename)

            # 5. Başarı kontrolü
            if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                result["video_path"] = video_path
                result["success"] = True
                logger.info(f"BAŞARILI! Video: {video_path}")
            else:
                result["error"] = "Video indirilemedi"
                logger.warning(f"Video indirilemedi: {output_filename}")

        except Exception as e:
            logger.error(f"Hata: {e}")
            result["error"] = str(e)

        return result

    def close(self, keep_open: bool = True):
        """Tarayıcıyı kapat"""
        if not keep_open and self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Tarayıcı kapatıldı")
        elif keep_open:
            logger.info("Tarayıcı kontrol için açık bırakıldı")


def create_videos_from_images(
    image_paths: List[str],
    video_prompts: List[str],
    project_dir: str,
    progress_callback: Callable = None
) -> List[Dict[str, Any]]:
    """
    Temizlenmiş görsellerden videolar oluştur
    Her video için başarısız olursa 3 kez yeniden dener

    Args:
        image_paths: Temizlenmiş görsel dosya yolları
        video_prompts: Her görsel için video prompt'ları
        project_dir: Proje klasörü
        progress_callback: İlerleme callback fonksiyonu

    Returns:
        Video sonuçları listesi
    """
    results = []

    generator = GrokVideoGenerator(
        project_dir=project_dir,
        progress_callback=progress_callback
    )

    try:
        if not generator.start_browser():
            raise Exception("Tarayıcı başlatılamadı")

        if not generator.navigate_to_grok_imagine():
            raise Exception("Grok Imagine'e gidilemedi")

        for i, (image_path, video_prompt) in enumerate(zip(image_paths, video_prompts), 1):
            if progress_callback:
                progress_callback(f"Video {i}/{len(image_paths)} oluşturuluyor...", 50 + (i * 10))

            output_filename = f"video_{i}.mp4"

            # Her video için 3 deneme hakkı var (generate_video_from_image içinde)
            result = generator.generate_video_from_image(image_path, video_prompt, output_filename)
            results.append(result)

            if result.get("success"):
                logger.info(f"Video {i} başarılı")
            else:
                logger.warning(f"Video {i} başarısız: {result.get('error')}")

            # Yeni video için yeni chat başlat
            if i < len(image_paths):
                logger.info(f"Video {i} tamamlandı, bir sonraki için yeni chat başlatılıyor...")
                generator.start_new_chat()

        # Sonuç özeti
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Video oluşturma tamamlandı: {success_count}/{len(image_paths)} başarılı")

    except Exception as e:
        logger.error(f"Video oluşturma genel hatası: {e}")
        results.append({"error": str(e), "success": False})

    finally:
        generator.close(keep_open=True)

    return results


def create_videos_from_images_indexed(
    image_video_pairs: List[Dict[str, Any]],
    project_dir: str,
    progress_callback: Callable = None
) -> List[Dict[str, Any]]:
    """
    Index bazlı video oluşturma - video_i her zaman image_i'yi kullanır

    Args:
        image_video_pairs: [{"index": 1, "image_path": "...", "video_prompt": "..."}, ...]
        project_dir: Proje klasörü
        progress_callback: İlerleme callback fonksiyonu

    Returns:
        Video sonuçları listesi
    """
    results = []

    generator = GrokVideoGenerator(
        project_dir=project_dir,
        progress_callback=progress_callback
    )

    try:
        if not generator.start_browser():
            raise Exception("Tarayıcı başlatılamadı")

        if not generator.navigate_to_grok_imagine():
            raise Exception("Grok Imagine'e gidilemedi")

        for i, pair in enumerate(image_video_pairs):
            idx = pair["index"]
            image_path = pair["image_path"]
            video_prompt = pair["video_prompt"]

            if progress_callback:
                progress_callback(f"Video {idx} oluşturuluyor...", 50 + (i * 10))

            # Video dosya adı index'e göre
            output_filename = f"video_{idx}.mp4"

            result = generator.generate_video_from_image(image_path, video_prompt, output_filename)
            result["index"] = idx
            results.append(result)

            if result.get("success"):
                logger.info(f"Video {idx} başarılı")
            else:
                logger.warning(f"Video {idx} başarısız: {result.get('error')}")

            # Yeni video için yeni chat başlat
            if i < len(image_video_pairs) - 1:
                logger.info(f"Video {idx} tamamlandı, bir sonraki için yeni chat başlatılıyor...")
                generator.start_new_chat()

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Video oluşturma tamamlandı: {success_count}/{len(image_video_pairs)} başarılı")

    except Exception as e:
        logger.error(f"Video oluşturma genel hatası: {e}")
        results.append({"error": str(e), "success": False})

    finally:
        generator.close(keep_open=True)

    return results


if __name__ == "__main__":
    # Test
    print("Grok Video Generator Test")
    print("Bu modül görsellerden video oluşturmak için kullanılır.")
    print("Kullanım: create_videos_from_images(image_paths, video_prompts, project_dir)")
