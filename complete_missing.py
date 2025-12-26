"""
Eksik görsel ve video tamamla - project_20251224_145653
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from generator import GeminiImageGenerator
from grok_video_generator import GrokVideoGenerator
from video_renderer import render_project

PROJECT_DIR = "/Users/hasan/Desktop/auto/projects/project_20251224_145653"

IMAGE_PROMPT = "3D exploded diagram of a neuron, dendrites, axon, and synapse separated, ambient blue lighting, clean scientific visualization"
VIDEO_PROMPT = "exploded 3D animation of a neuron, camera orbiting around dendrites and axon, clean educational style"

def progress_callback(msg, pct):
    print(f"[{pct}%] {msg}")

def main():
    print("=" * 60)
    print("Eksik görsel ve video tamamlanıyor...")
    print("=" * 60)

    # 1. Image 2 oluştur (Gemini)
    print("\n--- ADIM 1: Image 2 oluşturuluyor (Gemini) ---")

    gemini = GeminiImageGenerator(
        project_name="project_20251224_145653",
        progress_callback=progress_callback
    )
    gemini.project_dir = PROJECT_DIR  # Mevcut projeyi kullan

    if not gemini.start_browser():
        print("Gemini tarayıcı başlatılamadı!")
        return

    if not gemini.navigate_to_gemini():
        print("Gemini'ye gidilemedi!")
        gemini.close()
        return

    # Image 2 oluştur (oturumdaki ilk görsel, yeni chat başlatma)
    result = gemini.generate_single_image(IMAGE_PROMPT, image_index=2, start_new_chat=False)
    gemini.close()

    if result.get("success"):
        print(f"Image 2 başarılı: {result.get('cleaned_path')}")
    else:
        print(f"Image 2 HATA: {result.get('error')}")
        return

    # 2. Video 2 oluştur (Grok)
    print("\n--- ADIM 2: Video 2 oluşturuluyor (Grok) ---")

    grok = GrokVideoGenerator(
        project_dir=PROJECT_DIR,
        progress_callback=progress_callback
    )

    if not grok.start_browser():
        print("Grok tarayıcı başlatılamadı!")
        return

    if not grok.navigate_to_grok_imagine():
        print("Grok Imagine'e gidilemedi!")
        grok.close()
        return

    video_result = grok.generate_video_from_image(
        image_path=os.path.join(PROJECT_DIR, "image_2_cleaned.png"),
        video_prompt=VIDEO_PROMPT,
        output_filename="video_2.mp4"
    )
    grok.close()

    if video_result.get("success"):
        print(f"Video 2 başarılı: {video_result.get('video_path')}")
    else:
        print(f"Video 2 HATA: {video_result.get('error')}")
        return

    # 3. Final render
    print("\n--- ADIM 3: Final render ---")

    video_paths = [os.path.join(PROJECT_DIR, f"video_{i}.mp4") for i in range(1, 7)]

    # Eksik video kontrolü
    for vp in video_paths:
        if not os.path.exists(vp):
            print(f"HATA: Video bulunamadı: {vp}")
            return

    # Seslendirme metni
    voice_text = """
    Your brain contains billions of neurons, the building blocks of thought.
    Each neuron is a complex machine with dendrites that receive signals.
    The axon carries electrical impulses at incredible speeds.
    Synapses form connections, creating networks of memory and learning.
    This intricate dance of electricity and chemistry makes you who you are.
    Understanding the brain unlocks the secrets of human consciousness.
    """

    result = render_project(
        project_dir=PROJECT_DIR,
        video_paths=video_paths,
        voice_text=voice_text.strip(),
        voice_style="friendly",
        words_per_subtitle=2,
        progress_callback=progress_callback
    )

    if result["success"]:
        print(f"\nFinal video: {result['final_video']}")
        print("TAMAMLANDI!")
    else:
        print(f"\nRender HATA: {result['error']}")

if __name__ == "__main__":
    main()
