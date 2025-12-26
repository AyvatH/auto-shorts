"""
Eksik görsel ve videoları tamamla, render yap
"""
import os
import re
import logging
from typing import Dict, Any, Callable, List

import config
from generator import GeminiImageGenerator
from grok_video_generator import GrokVideoGenerator
from video_renderer import render_project

logger = logging.getLogger(__name__)


def find_missing_items(project_dir: str) -> Dict[str, Any]:
    """Projedeki eksik görsel, video ve thumbnail'ları bul"""
    import json

    files = os.listdir(project_dir)

    # Proje metadata'sını oku
    meta_path = os.path.join(project_dir, "project.json")
    expected_images = 0
    expected_videos = 0
    expected_thumbnails = 0

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            expected_images = meta.get("expected_images", 0)
            expected_videos = meta.get("expected_videos", 0)
            expected_thumbnails = meta.get("expected_thumbnails", 0)

    image_numbers = set()
    video_numbers = set()
    thumbnail_numbers = set()

    for f in files:
        match = re.match(r'image_(\d+)_cleaned\.png', f)
        if match:
            image_numbers.add(int(match.group(1)))
        match = re.match(r'video_(\d+)\.mp4', f)
        if match:
            video_numbers.add(int(match.group(1)))
        match = re.match(r'thumbnail_(\d+)_cleaned\.png', f)
        if match:
            thumbnail_numbers.add(int(match.group(1)))

    # Beklenen sayı yoksa mevcut max'ı kullan
    if expected_images == 0:
        expected_images = max(image_numbers) if image_numbers else 0
    if expected_videos == 0:
        expected_videos = max(video_numbers) if video_numbers else 0

    if expected_images == 0 and expected_videos == 0:
        return {"error": "Projede görsel/video bulunamadı"}

    expected_image_set = set(range(1, expected_images + 1))
    expected_video_set = set(range(1, expected_videos + 1))

    return {
        "total": max(expected_images, expected_videos),
        "expected_images": expected_images,
        "expected_videos": expected_videos,
        "existing_images": sorted(image_numbers),
        "existing_videos": sorted(video_numbers),
        "existing_thumbnails": sorted(thumbnail_numbers),
        "missing_images": sorted(expected_image_set - image_numbers),
        "missing_videos": sorted(expected_video_set - video_numbers)
    }


def complete_missing_items(
    project_name: str,
    image_prompts: Dict[int, str] = None,
    video_prompts: Dict[int, str] = None,
    voice_text: str = "",
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """
    Eksik görsel ve videoları tamamla, render yap

    Args:
        project_name: Proje adı
        image_prompts: Eksik görseller için promptlar {index: prompt}
        video_prompts: Eksik videolar için promptlar {index: prompt}
        voice_text: Seslendirme metni (render için)
        progress_callback: İlerleme callback'i

    Returns:
        Sonuç dict'i
    """
    image_prompts = image_prompts or {}
    video_prompts = video_prompts or {}
    progress_callback = progress_callback or (lambda msg, pct: logger.info(f"[{pct}%] {msg}"))

    project_dir = os.path.join(config.PROJECTS_DIR, project_name)

    if not os.path.exists(project_dir):
        return {"success": False, "error": "Proje bulunamadı"}

    # project.json'dan promptları oku (parametre olarak gelmemişse)
    meta_path = os.path.join(project_dir, "project.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Parametre olarak gelen promptları öncelikli kullan, yoksa project.json'dan al
        saved_image_prompts = meta.get("image_prompts", {})
        saved_video_prompts = meta.get("video_prompts", {})

        # Merge: parametre > saved
        for k, v in saved_image_prompts.items():
            if k not in image_prompts and str(k) not in image_prompts and v:
                image_prompts[k] = v

        for k, v in saved_video_prompts.items():
            if k not in video_prompts and str(k) not in video_prompts and v:
                video_prompts[k] = v

        # Voice text de project.json'dan alınabilir
        if not voice_text:
            voice_text = meta.get("voice", {}).get("text", "")

    logger.info(f"Kullanılacak image_prompts: {image_prompts}")
    logger.info(f"Kullanılacak video_prompts: {video_prompts}")

    result = {
        "success": False,
        "project_name": project_name,
        "completed_images": [],
        "completed_videos": [],
        "final_video": None,
        "error": None
    }

    try:
        # 1. Eksikleri bul
        progress_callback("Eksikler kontrol ediliyor...", 5)
        missing = find_missing_items(project_dir)

        if "error" in missing:
            result["error"] = missing["error"]
            return result

        missing_images = missing["missing_images"]
        missing_videos = missing["missing_videos"]
        total = missing["total"]

        logger.info(f"========================================")
        logger.info(f"EKSİKLER TESPİT EDİLDİ:")
        logger.info(f"  Toplam beklenen: {total}")
        logger.info(f"  Eksik görseller ({len(missing_images)} adet): {missing_images}")
        logger.info(f"  Eksik videolar ({len(missing_videos)} adet): {missing_videos}")
        logger.info(f"  Mevcut görseller: {missing['existing_images']}")
        logger.info(f"  Mevcut videolar: {missing['existing_videos']}")
        logger.info(f"========================================")

        # 2. Eksik görselleri oluştur (Gemini)
        if missing_images:
            progress_callback(f"Eksik görseller oluşturuluyor ({len(missing_images)} adet)...", 10)

            gemini = GeminiImageGenerator(
                project_name=project_name,
                progress_callback=progress_callback
            )
            gemini.project_dir = project_dir

            if not gemini.start_browser():
                result["error"] = "Gemini tarayıcı başlatılamadı"
                return result

            if not gemini.navigate_to_gemini():
                gemini.close()
                result["error"] = "Gemini'ye gidilemedi"
                return result

            for loop_idx, idx in enumerate(missing_images):
                logger.info(f"=== GÖRSEL DÖNGÜSÜ: {loop_idx + 1}/{len(missing_images)}, index={idx} ===")

                # Prompt varsa kullan, yoksa varsayılan
                prompt = image_prompts.get(idx) or image_prompts.get(str(idx)) or f"Beautiful visual scene {idx}, high quality, detailed"
                logger.info(f"Kullanılacak prompt: {prompt[:100]}...")

                progress_callback(f"Görsel {idx}/{len(missing_images)} oluşturuluyor...", 15 + (loop_idx * 10))

                try:
                    # İlk görsel için yeni chat başlatma (zaten Gemini'deyiz)
                    # Sonrakiler için yeni chat başlat
                    should_start_new_chat = (loop_idx > 0)
                    img_result = gemini.generate_single_image(prompt, image_index=idx, start_new_chat=should_start_new_chat)

                    if img_result.get("success"):
                        result["completed_images"].append(idx)
                        logger.info(f"✓ Görsel {idx} tamamlandı")
                    else:
                        logger.warning(f"✗ Görsel {idx} oluşturulamadı: {img_result.get('error')}")
                except Exception as e:
                    logger.error(f"✗ Görsel {idx} exception: {e}")
                    import traceback
                    traceback.print_exc()

                # Her görsel arasında kısa bekleme
                import time
                time.sleep(2)

            gemini.close()

        # 3. Eksik videoları oluştur (Grok)
        # Önce hangi videoların oluşturulabileceğini kontrol et (görseli olan)
        existing_images = set(missing["existing_images"]) | set(result["completed_images"])
        videos_to_create = [v for v in missing_videos if v in existing_images]

        if videos_to_create:
            progress_callback(f"Eksik videolar oluşturuluyor ({len(videos_to_create)} adet)...", 50)

            grok = GrokVideoGenerator(
                project_dir=project_dir,
                progress_callback=progress_callback
            )

            if not grok.start_browser():
                result["error"] = "Grok tarayıcı başlatılamadı"
                return result

            if not grok.navigate_to_grok_imagine():
                grok.close()
                result["error"] = "Grok Imagine'e gidilemedi"
                return result

            for loop_idx, idx in enumerate(videos_to_create):
                logger.info(f"=== VIDEO DÖNGÜSÜ: {loop_idx + 1}/{len(videos_to_create)}, index={idx} ===")

                # İlk video değilse yeni chat başlat (önceki video sonrası sayfa durumu değişmiş olabilir)
                if loop_idx > 0:
                    logger.info("Bir sonraki video için yeni chat başlatılıyor...")
                    grok.start_new_chat()

                image_path = os.path.join(project_dir, f"image_{idx}_cleaned.png")
                if not os.path.exists(image_path):
                    logger.warning(f"Video {idx} için görsel bulunamadı: {image_path}")
                    continue

                # Prompt varsa kullan, yoksa varsayılan
                prompt = video_prompts.get(idx) or video_prompts.get(str(idx)) or "Smooth cinematic motion, gentle camera movement"
                logger.info(f"Kullanılacak video prompt: {prompt[:100]}...")

                progress_callback(f"Video {idx}/{len(videos_to_create)} oluşturuluyor...", 55 + (loop_idx * 10))

                try:
                    vid_result = grok.generate_video_from_image(
                        image_path=image_path,
                        video_prompt=prompt,
                        output_filename=f"video_{idx}.mp4"
                    )

                    if vid_result.get("success"):
                        result["completed_videos"].append(idx)
                        logger.info(f"✓ Video {idx} tamamlandı")
                    else:
                        logger.warning(f"✗ Video {idx} oluşturulamadı: {vid_result.get('error')}")
                except Exception as e:
                    logger.error(f"✗ Video {idx} exception: {e}")
                    import traceback
                    traceback.print_exc()

                # Her video arasında kısa bekleme
                import time
                time.sleep(2)

            grok.close()

        # 4. Render yap (tüm videolar varsa)
        progress_callback("Render kontrol ediliyor...", 85)

        # Mevcut videoları kontrol et
        video_paths = []
        all_videos_exist = True
        for i in range(1, total + 1):
            vp = os.path.join(project_dir, f"video_{i}.mp4")
            if os.path.exists(vp):
                video_paths.append(vp)
            else:
                all_videos_exist = False
                logger.warning(f"Video {i} hala eksik")

        if all_videos_exist and video_paths:
            progress_callback("Final render yapılıyor...", 90)

            # Ses metni yoksa varsayılan oluştur
            if not voice_text:
                voice_text = " ".join([
                    f"Scene {i}, showing beautiful visually stunning content."
                    for i in range(1, total + 1)
                ])

            render_result = render_project(
                project_dir=project_dir,
                video_paths=video_paths,
                voice_text=voice_text,
                voice_style="friendly",
                words_per_subtitle=2,
                progress_callback=progress_callback
            )

            if render_result.get("success"):
                result["final_video"] = render_result.get("final_video")
                logger.info(f"Final video: {result['final_video']}")

        result["success"] = True
        progress_callback("Tamamlandı!", 100)

    except Exception as e:
        import traceback
        traceback.print_exc()
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        project = sys.argv[1]
        result = complete_missing_items(project)
        print(f"Sonuç: {result}")
