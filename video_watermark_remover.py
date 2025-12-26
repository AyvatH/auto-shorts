"""
Video Watermark Remover - Veo logosu temizleme
Sağ alt köşedeki "Veo" yazısını temizler
"""
import os
import cv2
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def remove_video_watermark(
    input_path: str,
    output_path: str,
    watermark_region: Tuple[float, float, float, float] = (0.85, 0.90, 1.0, 1.0),
    method: str = "inpaint"
) -> bool:
    """
    Video'dan watermark temizle

    Args:
        input_path: Giriş video yolu
        output_path: Çıkış video yolu
        watermark_region: Watermark bölgesi (x1%, y1%, x2%, y2%) - varsayılan sağ alt köşe
        method: Temizleme metodu ("inpaint", "blur", "replace")

    Returns:
        Başarılı mı
    """
    try:
        cap = cv2.VideoCapture(input_path)

        if not cap.isOpened():
            logger.error(f"Video açılamadı: {input_path}")
            return False

        # Video özellikleri
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height}, {fps}fps, {total_frames} frames")

        # Watermark bölgesi koordinatları (piksel)
        x1 = int(width * watermark_region[0])
        y1 = int(height * watermark_region[1])
        x2 = int(width * watermark_region[2])
        y2 = int(height * watermark_region[3])

        logger.info(f"Watermark bölgesi: ({x1}, {y1}) - ({x2}, {y2})")

        # Çıkış videosu
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Watermark bölgesini temizle
            if method == "inpaint":
                # Inpaint ile doldur - en temiz sonuç
                mask = np.zeros((height, width), dtype=np.uint8)
                mask[y1:y2, x1:x2] = 255
                frame = cv2.inpaint(frame, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

            elif method == "replace":
                # Üst kısımdan benzer pikseller ile değiştir
                # Watermark bölgesinin üstündeki bölgeyi kopyala
                source_y1 = max(0, y1 - (y2 - y1))
                source_y2 = y1
                if source_y2 > source_y1:
                    source_region = frame[source_y1:source_y2, x1:x2].copy()
                    # Boyut uyumu
                    target_height = y2 - y1
                    source_height = source_y2 - source_y1
                    if source_height > 0:
                        source_region = cv2.resize(source_region, (x2 - x1, target_height))
                        frame[y1:y2, x1:x2] = source_region

            elif method == "blur":
                # Blur uygula (en hızlı ama görünür)
                roi = frame[y1:y2, x1:x2]
                roi = cv2.GaussianBlur(roi, (21, 21), 0)
                frame[y1:y2, x1:x2] = roi

            out.write(frame)
            frame_count += 1

            if frame_count % 100 == 0:
                logger.debug(f"İşlenen frame: {frame_count}/{total_frames}")

        cap.release()
        out.release()

        logger.info(f"Video watermark temizlendi: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Video watermark temizleme hatası: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_veo_watermark(input_path: str, output_path: str) -> bool:
    """
    Veo watermark'ını temizle - sağ alt köşede

    Veo logosu genellikle sağ alt köşede %85-100 x, %90-100 y bölgesinde
    """
    # Önce inpaint dene (en temiz)
    return remove_video_watermark(
        input_path,
        output_path,
        watermark_region=(0.82, 0.88, 1.0, 1.0),  # Sağ alt köşe - biraz daha geniş alan
        method="inpaint"
    )


def detect_and_remove_watermark(input_path: str, output_path: str) -> bool:
    """
    Otomatik watermark tespit et ve temizle
    Beyaz/açık renkli metinleri sağ alt köşede arar
    """
    try:
        cap = cv2.VideoCapture(input_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return False

        height, width = frame.shape[:2]

        # Sağ alt köşeyi analiz et (son %20 x %15)
        roi_x1 = int(width * 0.80)
        roi_y1 = int(height * 0.85)
        roi = frame[roi_y1:height, roi_x1:width]

        # Gri tonlamaya çevir
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Beyaz/açık bölgeleri tespit et (watermark genellikle beyaz)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Beyaz piksel sayısı
        white_pixels = np.sum(thresh == 255)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        white_ratio = white_pixels / total_pixels

        logger.info(f"Sağ alt köşe beyaz piksel oranı: {white_ratio:.2%}")

        # Eğer beyaz piksel varsa watermark var demektir
        if white_ratio > 0.01:  # %1'den fazla beyaz piksel
            # Tespit edilen bölgeyi temizle
            return remove_video_watermark(
                input_path,
                output_path,
                watermark_region=(0.80, 0.85, 1.0, 1.0),
                method="inpaint"
            )
        else:
            # Watermark yok, sadece kopyala
            import shutil
            shutil.copy(input_path, output_path)
            return True

    except Exception as e:
        logger.error(f"Otomatik watermark tespit hatası: {e}")
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        success = remove_veo_watermark(input_file, output_file)
        print(f"Sonuç: {'Başarılı' if success else 'Başarısız'}")
    else:
        print("Kullanım: python video_watermark_remover.py <input.mp4> <output.mp4>")
