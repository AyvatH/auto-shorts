"""
Grok Login Browser - Tarayıcıyı açık tutar, kullanıcı giriş yapabilir
"""
import os
import time
import undetected_chromedriver as uc

def open_grok_for_login():
    """Grok sayfasını aç ve tarayıcıyı açık tut"""

    # Chrome profile yolu
    profile_dir = os.path.join(os.path.dirname(__file__), "chrome_profiles", "grok_profile")
    os.makedirs(profile_dir, exist_ok=True)

    print("Chrome tarayıcı açılıyor...")
    print("Grok sayfasına giriş yapın, sonra bu terminali kapatın.")
    print("-" * 50)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    driver = uc.Chrome(options=options)

    # Grok sayfasına git
    driver.get("https://grok.com/")

    print("\nTarayıcı açıldı!")
    print("1. Grok hesabınıza giriş yapın")
    print("2. Giriş tamamlandıktan sonra bu pencereyi kapatın (Ctrl+C)")
    print("\nOturum otomatik olarak kaydedilecek.")

    # Tarayıcıyı açık tut
    try:
        while True:
            time.sleep(5)
            # Tarayıcı hala açık mı kontrol et
            try:
                _ = driver.current_url
            except:
                print("\nTarayıcı kapatıldı. Oturum kaydedildi.")
                break
    except KeyboardInterrupt:
        print("\nKapatılıyor...")
    finally:
        try:
            driver.quit()
        except:
            pass

    print("Grok oturumu kaydedildi!")

if __name__ == "__main__":
    open_grok_for_login()
