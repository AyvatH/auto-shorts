#!/usr/bin/env python3
"""
Profesyonel Watermark Temizleyici - OpenCV Inpainting
"""
import cv2
import numpy as np
from PIL import Image
import os


def remove_watermark(input_path: str, output_path: str, debug: bool = False) -> bool:
    """
    Gemini watermark'ını profesyonel şekilde temizle
    OpenCV inpainting kullanır
    """
    try:
        # Görseli oku
        img = cv2.imread(input_path)
        if img is None:
            print(f"Görsel okunamadı: {input_path}")
            return False

        height, width = img.shape[:2]
        print(f"Görsel boyutu: {width}x{height}")

        # Gemini watermark konumu - sağ alt köşe
        # Watermark yaklaşık 50-60 piksel boyutunda elmas şekli
        watermark_size = 65
        margin = 15

        # Watermark bölgesi
        x1 = width - watermark_size - margin
        y1 = height - watermark_size - margin
        x2 = width - margin
        y2 = height - margin

        print(f"Watermark bölgesi: ({x1}, {y1}) - ({x2}, {y2})")

        # Mask oluştur - watermark bölgesini beyaz, geri kalanı siyah
        mask = np.zeros((height, width), dtype=np.uint8)

        # Elmas şeklinde mask (watermark elmas şeklinde)
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        size = watermark_size // 2

        # Elmas köşeleri
        diamond_pts = np.array([
            [center_x, center_y - size],  # üst
            [center_x + size, center_y],  # sağ
            [center_x, center_y + size],  # alt
            [center_x - size, center_y],  # sol
        ], dtype=np.int32)

        # Elmas şeklini mask'a çiz
        cv2.fillPoly(mask, [diamond_pts], 255)

        # Mask'ı biraz genişlet (dilation) - kenarları da kapsaması için
        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)

        if debug:
            cv2.imwrite(output_path.replace('.png', '_mask.png'), mask)
            print("Debug: Mask kaydedildi")

        # Inpainting uygula - TELEA algoritması daha iyi sonuç verir
        # inpaintRadius: Ne kadar çevreye bakılacak (3-7 arası iyi)
        result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

        # Alternatif: Navier-Stokes based inpainting
        # result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_NS)

        # Sonucu kaydet
        cv2.imwrite(output_path, result)
        print(f"Watermark temizlendi: {output_path}")

        return True

    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_watermark_advanced(input_path: str, output_path: str) -> bool:
    """
    Gelişmiş watermark temizleme - Agresif yöntem
    """
    try:
        img = cv2.imread(input_path)
        if img is None:
            return False

        height, width = img.shape[:2]

        # Watermark parametreleri - DAHA BÜYÜK ALAN
        watermark_size = 90  # Artırıldı
        margin = 5  # Köşeye daha yakın

        x1 = width - watermark_size - margin
        y1 = height - watermark_size - margin
        x2 = width - margin
        y2 = height - margin

        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        print(f"Temizlenecek alan: ({x1},{y1}) -> ({x2},{y2})")
        print(f"Merkez: ({center_x}, {center_y})")

        # Ana mask oluştur - BÜYÜK ELMAS
        mask = np.zeros((height, width), dtype=np.uint8)

        size = watermark_size // 2 + 10  # Daha büyük
        diamond_pts = np.array([
            [center_x, center_y - size],
            [center_x + size, center_y],
            [center_x, center_y + size],
            [center_x - size, center_y],
        ], dtype=np.int32)

        cv2.fillPoly(mask, [diamond_pts], 255)

        # Mask'ı DAHA FAZLA genişlet
        kernel = np.ones((9, 9), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=3)

        # 1. GEÇİŞ: TELEA inpainting (daha büyük radius)
        result = cv2.inpaint(img, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

        # 2. GEÇİŞ: NS inpainting üzerine
        result = cv2.inpaint(result, mask, inpaintRadius=5, flags=cv2.INPAINT_NS)

        # 3. GEÇİŞ: Tekrar TELEA ile pürüzsüzleştir
        small_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(small_mask, [diamond_pts], 255)
        kernel_small = np.ones((5, 5), np.uint8)
        small_mask = cv2.dilate(small_mask, kernel_small, iterations=1)

        result = cv2.inpaint(result, small_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

        cv2.imwrite(output_path, result)
        print(f"Watermark temizlendi (agresif): {output_path}")
        return True

    except Exception as e:
        print(f"Gelişmiş temizleme hatası: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys

    # Test için mevcut görseli kullan
    test_input = "/Users/hasan/Desktop/auto/projects/test_20251223_152428/image_2_original.png"
    test_output = "/Users/hasan/Desktop/auto/projects/test_20251223_152428/image_2_cleaned_v2.png"

    if len(sys.argv) > 1:
        test_input = sys.argv[1]
    if len(sys.argv) > 2:
        test_output = sys.argv[2]

    print("=== Watermark Temizleme Testi ===")
    print(f"Girdi: {test_input}")
    print(f"Çıktı: {test_output}")
    print()

    # Gelişmiş yöntemi kullan
    success = remove_watermark_advanced(test_input, test_output)

    if success:
        print("\n✓ Başarılı!")
    else:
        print("\n✗ Başarısız!")
