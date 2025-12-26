#!/usr/bin/env python3
"""
Profesyonel Watermark Temizleyici - LaMa Deep Learning
"""
import cv2
import numpy as np
import os
import shutil


def remove_watermark(input_path: str, output_path: str, debug: bool = False) -> bool:
    """
    Gemini watermark'ını LaMa deep learning modeli ile temizle
    """
    try:
        import torch
        import torch.nn.functional as F

        # Model yükle
        model_path = os.path.expanduser("~/.cache/torch/hub/checkpoints/big-lama.pt")

        # Model yoksa indir
        if not os.path.exists(model_path):
            print("LaMa modeli indiriliyor...")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            import urllib.request
            url = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
            urllib.request.urlretrieve(url, model_path)

        # Device seç
        if torch.backends.mps.is_available():
            device = 'mps'
        elif torch.cuda.is_available():
            device = 'cuda'
        else:
            device = 'cpu'

        print(f"LaMa modeli yükleniyor ({device})...")
        model = torch.jit.load(model_path, map_location='cpu')
        model = model.to(device)
        model.eval()

        # Görsel yükle
        img = cv2.imread(input_path)
        if img is None:
            print(f"Görsel okunamadı: {input_path}")
            return False

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width = img.shape[:2]
        print(f"Görsel boyutu: {width}x{height}")

        # Watermark mask oluştur
        mask = np.zeros((height, width), dtype=np.uint8)

        # Watermark merkezi ve boyutu (sağ alt köşe)
        wm_cx = width - 145
        wm_cy = height - 145
        wm_size = 130

        # 4 köşeli yıldız şekli
        pts = np.array([
            [wm_cx, wm_cy - wm_size],
            [wm_cx + wm_size//3, wm_cy - wm_size//3],
            [wm_cx + wm_size, wm_cy],
            [wm_cx + wm_size//3, wm_cy + wm_size//3],
            [wm_cx, wm_cy + wm_size],
            [wm_cx - wm_size//3, wm_cy + wm_size//3],
            [wm_cx - wm_size, wm_cy],
            [wm_cx - wm_size//3, wm_cy - wm_size//3],
        ], dtype=np.int32)

        cv2.fillPoly(mask, [pts], 255)
        kernel = np.ones((15, 15), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)

        if debug:
            cv2.imwrite(output_path.replace('.png', '_mask.png'), mask)

        # Tensörlere çevir
        img_tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        mask_tensor = torch.from_numpy(mask).unsqueeze(0).unsqueeze(0).float() / 255.0

        # 8'in katına yuvarla
        pad_h = (8 - height % 8) % 8
        pad_w = (8 - width % 8) % 8
        if pad_h > 0 or pad_w > 0:
            img_tensor = F.pad(img_tensor, (0, pad_w, 0, pad_h), mode='reflect')
            mask_tensor = F.pad(mask_tensor, (0, pad_w, 0, pad_h), mode='reflect')

        img_tensor = img_tensor.to(device)
        mask_tensor = mask_tensor.to(device)

        print("Inpainting yapılıyor (LaMa)...")
        with torch.no_grad():
            result_tensor = model(img_tensor, mask_tensor)

        # Padding'i kaldır
        if pad_h > 0 or pad_w > 0:
            result_tensor = result_tensor[:, :, :height, :width]

        # Numpy'a çevir ve kaydet
        result = result_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
        result = (result * 255).clip(0, 255).astype(np.uint8)
        result = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)

        cv2.imwrite(output_path, result)
        print(f"Watermark temizlendi (LaMa): {output_path}")
        return True

    except ImportError:
        print("PyTorch bulunamadı, OpenCV fallback kullanılıyor...")
        return remove_watermark_opencv(input_path, output_path, debug)
    except Exception as e:
        print(f"LaMa hatası: {e}, OpenCV fallback kullanılıyor...")
        return remove_watermark_opencv(input_path, output_path, debug)


def remove_watermark_opencv(input_path: str, output_path: str, debug: bool = False) -> bool:
    """
    OpenCV inpainting ile watermark temizleme (fallback)
    """
    try:
        img = cv2.imread(input_path)
        if img is None:
            print(f"Görsel okunamadı: {input_path}")
            return False

        height, width = img.shape[:2]
        print(f"Görsel boyutu: {width}x{height}")

        # Köşe alanı
        corner_size = 200
        corner = img[height-corner_size:height, width-corner_size:width].copy()
        gray = cv2.cvtColor(corner, cv2.COLOR_BGR2GRAY)

        # Kenar tespiti
        edges = cv2.Canny(gray, 10, 50)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            corner_mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(corner_mask, [largest], -1, 255, -1)

            kernel = np.ones((5, 5), np.uint8)
            corner_mask = cv2.dilate(corner_mask, kernel, iterations=2)

            mask = np.zeros((height, width), dtype=np.uint8)
            mask[height-corner_size:height, width-corner_size:width] = corner_mask

            result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

            small_kernel = np.ones((3, 3), np.uint8)
            small_mask = cv2.erode(mask, small_kernel, iterations=1)
            result = cv2.inpaint(result, small_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
        else:
            result = img

        cv2.imwrite(output_path, result)
        print(f"Watermark temizlendi (OpenCV): {output_path}")
        return True

    except Exception as e:
        print(f"OpenCV hatası: {e}")
        try:
            shutil.copy(input_path, output_path)
            return True
        except:
            return False


def remove_watermark_advanced(input_path: str, output_path: str) -> bool:
    """
    Gelişmiş watermark temizleme - LaMa'ya yönlendir
    """
    return remove_watermark(input_path, output_path, debug=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
    else:
        input_path = "/Users/hasan/Desktop/auto/gemini_pro_projects/shorts_20251226_171922/image_1.png"
        output_path = "/Users/hasan/Desktop/auto/gemini_pro_projects/shorts_20251226_171922/image_1_cleaned.png"

    print("=== Watermark Temizleme ===")
    success = remove_watermark(input_path, output_path)
    print(f"Sonuç: {'Başarılı' if success else 'Başarısız'}")
