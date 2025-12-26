"""
Video 6 oluştur
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from grok_video_generator import GrokVideoGenerator

PROJECT_DIR = "/Users/hasan/Desktop/auto/projects/project_20251223_211054"

def progress_callback(msg, pct):
    print(f"[{pct}%] {msg}")

def main():
    print("Video 6 oluşturuluyor...")

    generator = GrokVideoGenerator(
        project_dir=PROJECT_DIR,
        progress_callback=progress_callback
    )

    if not generator.start_browser():
        print("Tarayıcı başlatılamadı!")
        return

    if not generator.navigate_to_grok_imagine():
        print("Grok Imagine sayfasına gidilemedi!")
        generator.close()
        return

    result = generator.generate_video_from_image(
        image_path=os.path.join(PROJECT_DIR, "image_6_cleaned.png"),
        video_prompt="Close-up of premium headphones with ambient light reflections, slow camera movement, product showcase style",
        output_filename="video_6.mp4"
    )

    if result.get("success"):
        print(f"Video 6 başarılı: {result.get('video_path')}")
    else:
        print(f"Video 6 HATA: {result.get('error')}")

    generator.close()

if __name__ == "__main__":
    main()
