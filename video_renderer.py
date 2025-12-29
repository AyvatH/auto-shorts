"""
Video Renderer - Edge TTS + MoviePy
Videoları birleştir, ses ekle, altyazı ekle ve final render yap
"""
import os
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

import edge_tts
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips
)

import config

logger = logging.getLogger(__name__)

# Edge TTS Ses Seçenekleri - İngilizce Sesler
VOICE_OPTIONS = {
    "male_friendly": "en-US-BrianNeural",        # Erkek, samimi
    "female_friendly": "en-US-EmmaNeural",       # Kadın, samimi
    "male_casual": "en-US-ChristopherNeural",    # Erkek, casual
    "female_casual": "en-US-AriaNeural",         # Kadın, casual
    "narrator": "en-US-AndrewNeural",            # Anlatıcı erkek
    "dramatic": "en-US-BrianNeural",             # Dramatik erkek
    "friendly": "en-US-BrianNeural",             # Samimi erkek
    "female": "en-US-AvaNeural",                 # Kadın
}

DEFAULT_VOICE = "en-US-BrianNeural"  # Varsayılan: Samimi erkek ses


class VideoRenderer:
    """Video birleştirme, ses ve altyazı ekleme sınıfı"""

    def __init__(self, project_dir: str, progress_callback: Callable = None):
        self.project_dir = project_dir
        self.progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))
        self.output_dir = os.path.join(project_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _update_progress(self, message: str, percentage: int):
        """İlerleme durumunu güncelle"""
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    async def generate_tts_async(self, text: str, output_path: str, voice: str = None) -> Dict[str, Any]:
        """
        Edge TTS ile ses oluştur ve kelime zamanlamalarını al

        Returns:
            {
                "audio_path": str,
                "word_timings": [(word, start_time, end_time), ...]
            }
        """
        voice = voice or DEFAULT_VOICE

        communicate = edge_tts.Communicate(text, voice)

        sentence_timings = []
        word_timings = []

        # Ses ve zamanlama bilgilerini al
        with open(output_path, "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # Kelime sınırları varsa doğrudan kullan
                    word_timings.append({
                        "word": chunk["text"],
                        "start": chunk["offset"] / 10000000,
                        "end": (chunk["offset"] + chunk["duration"]) / 10000000
                    })
                elif chunk["type"] == "SentenceBoundary":
                    # Cümle sınırlarını kaydet
                    sentence_timings.append({
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10000000,
                        "duration": chunk["duration"] / 10000000
                    })

        # Eğer kelime zamanlamaları boşsa, cümle zamanlamalarından hesapla
        if not word_timings and sentence_timings:
            word_timings = self._calculate_word_timings_from_sentences(sentence_timings)

        return {
            "audio_path": output_path,
            "word_timings": word_timings
        }

    def _calculate_word_timings_from_sentences(self, sentence_timings: List[Dict]) -> List[Dict]:
        """Cümle zamanlamalarından kelime zamanlamalarını hesapla"""
        word_timings = []

        for sentence in sentence_timings:
            text = sentence["text"]
            start = sentence["start"]
            duration = sentence["duration"]

            # Kelimelere ayır
            words = text.split()
            if not words:
                continue

            # Her kelimenin uzunluğuna göre süre hesapla
            total_chars = sum(len(w) for w in words)
            if total_chars == 0:
                continue

            current_time = start
            for word in words:
                # Kelime uzunluğuna orantılı süre
                word_duration = (len(word) / total_chars) * duration
                word_timings.append({
                    "word": word,
                    "start": current_time,
                    "end": current_time + word_duration
                })
                current_time += word_duration

        return word_timings

    def generate_tts(self, text: str, output_path: str, voice: str = None) -> Dict[str, Any]:
        """Senkron TTS wrapper"""
        return asyncio.run(self.generate_tts_async(text, output_path, voice))

    def create_word_groups(self, word_timings: List[Dict], words_per_group: int = 2) -> List[Dict]:
        """
        Kelimeleri gruplara ayır (2'şer kelime)

        Returns:
            [{"text": "word1 word2", "start": 0.0, "end": 1.5}, ...]
        """
        groups = []

        for i in range(0, len(word_timings), words_per_group):
            group_words = word_timings[i:i + words_per_group]
            if group_words:
                text = " ".join([w["word"] for w in group_words])
                start = group_words[0]["start"]
                end = group_words[-1]["end"]
                groups.append({
                    "text": text,
                    "start": start,
                    "end": end
                })

        return groups

    def create_subtitle_clips(
        self,
        word_groups: List[Dict],
        video_size: tuple,
        font_size: int = 26,
        font_color: str = "white",
        stroke_color: str = "black",
        stroke_width: int = 1
    ) -> List[TextClip]:
        """
        Altyazı klipleri oluştur
        """
        subtitle_clips = []

        for group in word_groups:
            try:
                # Text clip oluştur - macOS için tam font yolu
                font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

                # Yazıya padding ekle (harflerin kesilmemesi için)
                padded_text = f" {group['text']} "

                txt_clip = TextClip(
                    text=padded_text,
                    font_size=font_size,
                    color=font_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    font=font_path,
                    method="caption",
                    size=(video_size[0] - 50, font_size + 20)  # Yüksekliğe margin ekle
                )

                # Pozisyon ve zamanlama ayarla - ekranın alt kısmında
                y_position = int(video_size[1] * 0.80)  # Ekranın %80'inde (aşağıda)
                txt_clip = txt_clip.with_position(("center", y_position))
                txt_clip = txt_clip.with_start(group["start"])
                txt_clip = txt_clip.with_duration(group["end"] - group["start"])

                subtitle_clips.append(txt_clip)
            except Exception as e:
                logger.warning(f"Altyazı oluşturma hatası: {e}")
                continue

        return subtitle_clips

    def combine_videos(self, video_paths: List[str], output_path: str) -> Optional[str]:
        """
        Videoları sırayla birleştir
        """
        try:
            self._update_progress("Videolar birleştiriliyor...", 60)

            clips = []
            for path in video_paths:
                if os.path.exists(path):
                    clip = VideoFileClip(path)
                    clips.append(clip)
                else:
                    logger.warning(f"Video bulunamadı: {path}")

            if not clips:
                logger.error("Birleştirilecek video bulunamadı")
                return None

            # Videoları birleştir
            final_clip = concatenate_videoclips(clips, method="compose")

            # Geçici dosyaya kaydet
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=30,
                logger=None  # MoviePy loglarını kapat
            )

            # Klipleri kapat
            for clip in clips:
                clip.close()
            final_clip.close()

            return output_path

        except Exception as e:
            logger.error(f"Video birleştirme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

    def render_final_video(
        self,
        video_paths: List[str],
        voice_text: str,
        voice_style: str = "friendly",
        words_per_subtitle: int = 2
    ) -> Dict[str, Any]:
        """
        Final video render:
        1. Videoları birleştir
        2. TTS ses oluştur
        3. Altyazı ekle
        4. Final render
        """
        result = {
            "success": False,
            "final_video": None,
            "audio_path": None,
            "error": None
        }

        try:
            # 1. Ses oluştur
            self._update_progress("Ses oluşturuluyor (Edge TTS)...", 50)

            # Ses stiline göre voice seç - Geçerli Edge TTS sesleri
            voice_map = {
                "friendly": "en-US-BrianNeural",
                "dramatic": "en-US-AndrewNeural",
                "casual": "en-US-ChristopherNeural",
                "female": "en-US-EmmaNeural",
                "narrator": "en-US-BrianNeural",
            }
            voice = voice_map.get(voice_style, DEFAULT_VOICE)

            audio_path = os.path.join(self.output_dir, "narration.mp3")
            tts_result = self.generate_tts(voice_text, audio_path, voice)
            result["audio_path"] = audio_path

            word_timings = tts_result["word_timings"]
            logger.info(f"TTS oluşturuldu: {len(word_timings)} kelime")

            # 2. Videoları birleştir
            self._update_progress("Videolar birleştiriliyor...", 60)

            combined_video_path = os.path.join(self.output_dir, "combined_temp.mp4")

            clips = []
            # Hedef boyut: 9:16 (1080x1920 veya 720x1280)
            target_width = 720
            target_height = 1280

            logger.info(f"Birleştirilecek videolar ({len(video_paths)} adet) - Hedef: {target_width}x{target_height}")
            for path in video_paths:
                if os.path.exists(path):
                    clip = VideoFileClip(path)
                    orig_w, orig_h = clip.size
                    logger.info(f"  + {os.path.basename(path)}: {orig_w}x{orig_h}, {clip.duration:.2f}s")

                    # Boyut farklıysa normalize et
                    if orig_w != target_width or orig_h != target_height:
                        # Aspect ratio hesapla
                        orig_ratio = orig_w / orig_h
                        target_ratio = target_width / target_height

                        if abs(orig_ratio - target_ratio) > 0.1:
                            # Yanlış aspect ratio - crop + scale
                            if orig_ratio > target_ratio:
                                # Video çok geniş (16:9), crop yap
                                new_width = int(orig_h * target_ratio)
                                x_center = orig_w / 2
                                clip = clip.cropped(x1=x_center - new_width/2, x2=x_center + new_width/2)
                                logger.info(f"    -> Yatay video, ortadan crop: {new_width}x{orig_h}")
                            else:
                                # Video çok dar, crop yap
                                new_height = int(orig_w / target_ratio)
                                y_center = orig_h / 2
                                clip = clip.cropped(y1=y_center - new_height/2, y2=y_center + new_height/2)
                                logger.info(f"    -> Dikey video, ortadan crop: {orig_w}x{new_height}")

                        # Hedef boyuta resize
                        clip = clip.resized((target_width, target_height))
                        logger.info(f"    -> Resize: {target_width}x{target_height}")

                    clips.append(clip)
                else:
                    logger.warning(f"  - Video bulunamadı: {path}")

            if not clips:
                raise Exception("Birleştirilecek video bulunamadı")

            # Videoları birleştir (artık hepsi aynı boyutta)
            video_clip = concatenate_videoclips(clips, method="compose")
            video_size = video_clip.size
            video_duration = video_clip.duration

            logger.info(f"Video boyutu: {video_size}, Süre: {video_duration}s")

            # 3. Ses klibini yükle ve video süresine göre ayarla
            self._update_progress("Ses ekleniyor...", 70)

            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration

            # Ses ve video süresini eşitle
            if audio_duration > video_duration:
                # Ses videodan uzunsa, sesi kırp
                audio_clip = audio_clip.subclipped(0, video_duration)
                logger.info(f"Ses kırpıldı: {audio_duration:.1f}s -> {video_duration:.1f}s")
            elif video_duration > audio_duration:
                # Video sesten uzunsa, VİDEOYU KIRPMA! Ses bitince sessiz devam et.
                # Sadece uyarı ver
                logger.warning(f"⚠️ Video ({video_duration:.1f}s) sesten ({audio_duration:.1f}s) uzun! Son {video_duration - audio_duration:.1f}s sessiz olacak.")

            # Sesi videoya ekle
            video_with_audio = video_clip.with_audio(audio_clip)

            # 4. Altyazı ekle
            self._update_progress("Altyazılar ekleniyor...", 80)

            word_groups = self.create_word_groups(word_timings, words_per_subtitle)
            subtitle_clips = self.create_subtitle_clips(word_groups, video_size)

            logger.info(f"Altyazı grupları: {len(word_groups)}")

            # Video + altyazıları birleştir
            final_clip = CompositeVideoClip([video_with_audio] + subtitle_clips)

            # 5. Final render
            self._update_progress("Final video render ediliyor...", 90)

            final_output = os.path.join(self.output_dir, f"final_video_{datetime.now().strftime('%H%M%S')}.mp4")

            final_clip.write_videofile(
                final_output,
                codec="libx264",
                audio_codec="aac",
                fps=30,
                threads=4,
                logger=None
            )

            # Temizlik
            for clip in clips:
                clip.close()
            video_clip.close()
            audio_clip.close()
            final_clip.close()

            # Geçici dosyayı sil
            if os.path.exists(combined_video_path):
                os.remove(combined_video_path)

            result["success"] = True
            result["final_video"] = final_output
            self._update_progress("Final video hazır!", 100)

        except Exception as e:
            logger.error(f"Render hatası: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)

        return result


def render_project(
    project_dir: str,
    video_paths: List[str],
    voice_text: str,
    voice_style: str = "friendly",
    words_per_subtitle: int = 1,
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """
    Proje için final video render et

    Args:
        project_dir: Proje klasörü
        video_paths: Video dosya yolları listesi
        voice_text: Seslendirme metni
        voice_style: Ses stili (friendly, dramatic, casual, female, narrator)
        words_per_subtitle: Altyazıda kaç kelime gösterilsin (varsayılan: 1)
        progress_callback: İlerleme callback fonksiyonu

    Returns:
        {
            "success": bool,
            "final_video": str (path),
            "audio_path": str (path),
            "error": str or None
        }
    """
    renderer = VideoRenderer(project_dir, progress_callback)
    return renderer.render_final_video(
        video_paths=video_paths,
        voice_text=voice_text,
        voice_style=voice_style,
        words_per_subtitle=words_per_subtitle
    )


# Test için
if __name__ == "__main__":
    import sys

    print("=== Video Renderer Test ===")
    print("Kullanım: python video_renderer.py <project_dir> <video1.mp4> <video2.mp4> ... 'Voice text here'")

    if len(sys.argv) < 4:
        print("\nEdge TTS Ses Seçenekleri:")
        for name, voice in VOICE_OPTIONS.items():
            print(f"  {name}: {voice}")
        sys.exit(0)

    project_dir = sys.argv[1]
    videos = sys.argv[2:-1]
    voice_text = sys.argv[-1]

    result = render_project(
        project_dir=project_dir,
        video_paths=videos,
        voice_text=voice_text,
        voice_style="friendly"
    )

    print(f"\nSonuç: {'Başarılı' if result['success'] else 'Hatalı'}")
    if result['final_video']:
        print(f"Final video: {result['final_video']}")
    if result['error']:
        print(f"Hata: {result['error']}")
