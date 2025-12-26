"""
Video Watermark Remover - Temporal Inpainting
Video hareketinden yararlanarak watermark altındaki orijinal pikselleri kurtarır
"""
import os
import cv2
import numpy as np
import logging
import tempfile
import shutil
from typing import Tuple, List
from collections import deque

logger = logging.getLogger(__name__)


def remove_video_watermark_temporal(
    input_path: str,
    output_path: str,
    watermark_region: Tuple[float, float, float, float] = (0.85, 0.88, 1.0, 1.0),
    buffer_size: int = 30
) -> bool:
    """
    Temporal Inpainting - video hareketinden yararlanarak watermark'ı kaldır

    Nasıl çalışır:
    1. Birden fazla frame'i hafızada tut
    2. Her frame için watermark bölgesindeki piksellerin ne olması gerektiğini
       diğer frame'lerden hesapla (optik akış ile)
    3. En uygun pikselleri seç ve blend et
    """
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            logger.error(f"Video açılamadı: {input_path}")
            return False

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height}, {fps}fps, {total_frames} frames")

        # Watermark bölgesi
        x1 = int(width * watermark_region[0])
        y1 = int(height * watermark_region[1])
        x2 = int(width * watermark_region[2])
        y2 = int(height * watermark_region[3])

        wm_width = x2 - x1
        wm_height = y2 - y1

        logger.info(f"Watermark: ({x1},{y1}) - ({x2},{y2})")

        # İlk geçiş: Tüm frame'leri oku ve watermark olmayan referans bölgeleri topla
        logger.info("İlk geçiş: Referans pikseller toplanıyor...")

        frames = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)

        cap.release()

        if len(frames) == 0:
            logger.error("Frame okunamadı")
            return False

        # Her piksel için en iyi değeri bul (median filter temporal)
        logger.info("Temporal median hesaplanıyor...")

        # Watermark bölgesi için temporal stack oluştur
        wm_stack = np.array([f[y1:y2, x1:x2] for f in frames])

        # Watermark genellikle açık renkli (beyaz/gri) olduğundan
        # Her piksel için en koyu değerleri tercih et
        # Bu watermark'ın etkisini minimize eder

        # Yöntem 1: Her piksel için percentile (watermark'ı atla)
        # Watermark açık renkli olduğundan düşük percentile kullan
        percentile_value = 15  # En koyu %15'lik dilim

        clean_wm_region = np.percentile(wm_stack, percentile_value, axis=0).astype(np.uint8)

        # Yöntem 2: Daha akıllı - hareket eden bölgelerde median, sabit bölgelerde percentile
        # Standart sapma hesapla - hareket var mı?
        std_map = np.std(wm_stack, axis=0).mean(axis=2)

        # Hareket olan yerlerde (std yüksek) median kullan
        # Sabit yerlerde (std düşük, muhtemelen watermark) percentile kullan
        motion_threshold = 20
        motion_mask = std_map > motion_threshold

        median_wm_region = np.median(wm_stack, axis=0).astype(np.uint8)

        # İkisini birleştir
        motion_mask_3ch = np.stack([motion_mask, motion_mask, motion_mask], axis=2)
        clean_wm_region = np.where(motion_mask_3ch, median_wm_region, clean_wm_region)

        # Kenar yumuşatma için blend mask
        blend_mask = np.ones((wm_height, wm_width), dtype=np.float32)

        # Kenarları yumuşat
        fade = 15
        for i in range(fade):
            factor = i / fade
            blend_mask[i, :] *= factor  # Üst
            blend_mask[:, i] *= factor  # Sol

        blend_mask = cv2.GaussianBlur(blend_mask, (11, 11), 0)
        blend_3ch = np.stack([blend_mask, blend_mask, blend_mask], axis=2)

        # İkinci geçiş: Temizlenmiş frame'leri yaz
        logger.info("Temizlenmiş video yazılıyor...")

        temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

        for idx, frame in enumerate(frames):
            # Orijinal watermark bölgesi
            original_wm = frame[y1:y2, x1:x2].astype(np.float32)

            # Temizlenmiş bölge ile blend
            blended = (clean_wm_region.astype(np.float32) * blend_3ch +
                      original_wm * (1 - blend_3ch))

            frame[y1:y2, x1:x2] = blended.astype(np.uint8)
            out.write(frame)

            if idx % 50 == 0:
                logger.info(f"Yazılıyor: {idx}/{len(frames)}")

        out.release()

        # FFmpeg finalize
        _finalize_video(input_path, temp_video, output_path)

        logger.info(f"Temporal inpainting tamamlandı: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Temporal inpainting hatası: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_video_watermark_frequency(
    input_path: str,
    output_path: str,
    watermark_region: Tuple[float, float, float, float] = (0.85, 0.88, 1.0, 1.0)
) -> bool:
    """
    Frekans domain yöntemi - watermark'ı frekans uzayında filtrele
    Watermark genellikle yüksek frekanslı detay olarak görünür
    """
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return False

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        x1 = int(width * watermark_region[0])
        y1 = int(height * watermark_region[1])
        x2 = int(width * watermark_region[2])
        y2 = int(height * watermark_region[3])

        temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Watermark bölgesini al
            roi = frame[y1:y2, x1:x2].copy()

            # Her kanal için frekans filtresi
            filtered_roi = np.zeros_like(roi)
            for c in range(3):
                channel = roi[:, :, c].astype(np.float32)

                # DFT
                dft = cv2.dft(channel, flags=cv2.DFT_COMPLEX_OUTPUT)
                dft_shift = np.fft.fftshift(dft)

                # Düşük geçiren filtre (watermark yüksek frekans)
                rows, cols = channel.shape
                crow, ccol = rows // 2, cols // 2

                # Gaussian low-pass filter
                mask = np.zeros((rows, cols, 2), np.float32)
                sigma = min(rows, cols) // 4
                for i in range(rows):
                    for j in range(cols):
                        dist = np.sqrt((i - crow) ** 2 + (j - ccol) ** 2)
                        mask[i, j] = np.exp(-(dist ** 2) / (2 * sigma ** 2))

                # Filtre uygula
                fshift = dft_shift * mask

                # Inverse DFT
                f_ishift = np.fft.ifftshift(fshift)
                img_back = cv2.idft(f_ishift)
                img_back = cv2.magnitude(img_back[:, :, 0], img_back[:, :, 1])

                filtered_roi[:, :, c] = np.clip(img_back, 0, 255).astype(np.uint8)

            # Yumuşak blend
            blend_mask = np.ones(roi.shape[:2], dtype=np.float32)
            fade = 10
            for i in range(fade):
                blend_mask[i, :] *= i / fade
                blend_mask[:, i] *= i / fade

            blend_mask = cv2.GaussianBlur(blend_mask, (7, 7), 0)
            blend_3ch = np.stack([blend_mask] * 3, axis=2)

            result = (filtered_roi * blend_3ch + roi * (1 - blend_3ch)).astype(np.uint8)
            frame[y1:y2, x1:x2] = result

            out.write(frame)

        cap.release()
        out.release()

        _finalize_video(input_path, temp_video, output_path)
        return True

    except Exception as e:
        logger.error(f"Frequency filter hatası: {e}")
        return False


def _finalize_video(original_path: str, temp_video: str, output_path: str):
    """FFmpeg ile finalize"""
    try:
        import subprocess

        temp_audio = tempfile.NamedTemporaryFile(suffix='.aac', delete=False).name
        subprocess.run([
            'ffmpeg', '-y', '-i', original_path,
            '-vn', '-acodec', 'aac', '-b:a', '128k', temp_audio
        ], capture_output=True, timeout=60)

        has_audio = os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000

        if has_audio:
            subprocess.run([
                'ffmpeg', '-y',
                '-i', temp_video, '-i', temp_audio,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                '-c:a', 'aac', '-b:a', '128k',
                '-shortest', '-movflags', '+faststart',
                output_path
            ], capture_output=True, timeout=180)
            os.unlink(temp_audio)
        else:
            subprocess.run([
                'ffmpeg', '-y', '-i', temp_video,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                '-movflags', '+faststart',
                output_path
            ], capture_output=True, timeout=180)

        os.unlink(temp_video)

    except Exception as e:
        logger.warning(f"FFmpeg başarısız: {e}")
        shutil.move(temp_video, output_path)


def remove_video_watermark(input_path: str, output_path: str, method: str = "temporal") -> bool:
    """Ana fonksiyon"""
    if method == "frequency":
        return remove_video_watermark_frequency(input_path, output_path)
    else:
        return remove_video_watermark_temporal(input_path, output_path)


def remove_veo_watermark(input_path: str, output_path: str, use_lama: bool = True) -> bool:
    """
    Veo/Gemini watermark - LaMa deep learning ile profesyonel temizleme

    Args:
        input_path: Girdi video yolu
        output_path: Çıktı video yolu
        use_lama: True = LaMa deep learning (önerilen), False = temporal inpainting
    """
    if use_lama:
        try:
            from lama_video_inpaint import remove_video_watermark_lama
            logger.info("LaMa deep learning ile watermark temizleniyor...")
            return remove_video_watermark_lama(input_path, output_path)
        except ImportError as e:
            logger.warning(f"LaMa modülü yüklenemedi: {e}, temporal yönteme geçiliyor...")
        except Exception as e:
            logger.warning(f"LaMa hatası: {e}, temporal yönteme geçiliyor...")

    # Fallback: temporal inpainting
    return remove_video_watermark_temporal(
        input_path, output_path,
        watermark_region=(0.84, 0.87, 1.0, 1.0)
    )


def remove_veo_watermark_lama(input_path: str, output_path: str) -> bool:
    """LaMa deep learning ile Veo watermark temizleme (direkt çağrı)"""
    try:
        from lama_video_inpaint import remove_video_watermark_lama
        return remove_video_watermark_lama(input_path, output_path)
    except Exception as e:
        logger.error(f"LaMa watermark temizleme hatası: {e}")
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        success = remove_veo_watermark(sys.argv[1], sys.argv[2])
        print(f"Sonuç: {'Başarılı' if success else 'Başarısız'}")
