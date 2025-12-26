"""
Final video render - 6 video + ses + altyazı
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from video_renderer import render_project

PROJECT_DIR = "/Users/hasan/Desktop/auto/projects/project_20251223_211054"

# Seslendirme metni - noise-cancelling headphones teması (6 video için ~36 saniye)
VOICE_TEXT = """
Are you tired of the constant noise surrounding you every single day?
Introducing our premium noise-cancelling headphones, designed for perfection.
With advanced active noise cancellation technology, you can finally block out the entire world.
Experience crystal clear audio quality for your favorite music, podcasts, and important calls.
The ergonomic and comfortable design lets you wear them all day without any discomfort.
Step into a world of true silence and pure, immersive sound. Your ears deserve the best.
"""

def progress_callback(msg, pct):
    print(f"[{pct}%] {msg}")

def main():
    print("=" * 50)
    print("Final Video Render")
    print("=" * 50)

    # Video dosyaları sıralı
    video_paths = [
        os.path.join(PROJECT_DIR, f"video_{i}.mp4")
        for i in range(1, 7)
    ]

    # Eksik video kontrolü
    for vp in video_paths:
        if not os.path.exists(vp):
            print(f"HATA: Video bulunamadı: {vp}")
            return

    print(f"Videolar: {len(video_paths)} adet")
    print(f"Seslendirme: {len(VOICE_TEXT.split())} kelime")

    result = render_project(
        project_dir=PROJECT_DIR,
        video_paths=video_paths,
        voice_text=VOICE_TEXT.strip(),
        voice_style="friendly",
        words_per_subtitle=2,
        progress_callback=progress_callback
    )

    if result["success"]:
        print(f"\nFinal video: {result['final_video']}")
        print("Render tamamlandı!")
    else:
        print(f"\nHATA: {result['error']}")

if __name__ == "__main__":
    main()
