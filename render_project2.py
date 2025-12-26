"""
Final render - project_20251224_145653
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from video_renderer import render_project

PROJECT_DIR = "/Users/hasan/Desktop/auto/projects/project_20251224_145653"

VOICE_TEXT = """
Your brain contains over eighty billion neurons, the incredible building blocks of every single thought you have.
Each neuron has tree-like dendrites that reach out to receive electrical signals from other cells.
The axon carries these electrical impulses traveling at remarkable speeds through your entire brain.
At the synapses, chemical messengers called neurotransmitters jump across tiny gaps between neurons.
These vast networks are responsible for creating all of your memories, emotions, and thoughts.
Understanding how the brain works unlocks the greatest mysteries of human consciousness.
"""

def progress_callback(msg, pct):
    print(f"[{pct}%] {msg}")

def main():
    print("Final render başlıyor...")

    video_paths = [os.path.join(PROJECT_DIR, f"video_{i}.mp4") for i in range(1, 7)]

    for vp in video_paths:
        if not os.path.exists(vp):
            print(f"HATA: {vp} bulunamadı!")
            return

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
    else:
        print(f"\nHATA: {result['error']}")

if __name__ == "__main__":
    main()
