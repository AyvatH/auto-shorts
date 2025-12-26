"""
Eksik videoları oluştur - Video 5 ve 6
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from grok_video_generator import GrokVideoGenerator

PROJECT_DIR = "/Users/hasan/Desktop/auto/projects/project_20251223_211054"

# Video 5 ve 6 için görsel ve prompt
videos_to_create = [
    {
        "index": 5,
        "image_path": os.path.join(PROJECT_DIR, "image_5_cleaned.png"),
        "prompt": "Person enjoying music with noise-cancelling headphones, peaceful expression, subtle head movement, cinematic lighting"
    },
    {
        "index": 6,
        "image_path": os.path.join(PROJECT_DIR, "image_6_cleaned.png"),
        "prompt": "Close-up of premium headphones with ambient light reflections, slow camera movement, product showcase style"
    }
]

def progress_callback(msg, pct):
    print(f"[{pct}%] {msg}")

def main():
    print("=" * 50)
    print("Video 5 ve 6 oluşturuluyor...")
    print("=" * 50)

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

    for video_info in videos_to_create:
        idx = video_info["index"]
        image_path = video_info["image_path"]
        prompt = video_info["prompt"]
        output_filename = f"video_{idx}.mp4"

        print(f"\n--- Video {idx} oluşturuluyor ---")
        print(f"Görsel: {image_path}")
        print(f"Prompt: {prompt}")

        result = generator.generate_video_from_image(
            image_path=image_path,
            video_prompt=prompt,
            output_filename=output_filename
        )

        if result.get("success"):
            print(f"Video {idx} başarılı: {result.get('video_path')}")
        else:
            print(f"Video {idx} HATA: {result.get('error')}")

    generator.close()
    print("\n" + "=" * 50)
    print("Tamamlandı!")

if __name__ == "__main__":
    main()
