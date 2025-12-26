#!/usr/bin/env python3
"""
Profesyonel Video Watermark Remover - LaMa Deep Learning
Frame-by-frame inpainting with temporal consistency
"""
import cv2
import numpy as np
import os
import tempfile
import subprocess
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LamaVideoInpainter:
    def __init__(self):
        self.model = None
        self.device = None
        self._load_model()

    def _load_model(self):
        """LaMa modelini yükle"""
        import torch
        import torch.nn.functional as F

        model_path = os.path.expanduser("~/.cache/torch/hub/checkpoints/big-lama.pt")

        if not os.path.exists(model_path):
            logger.info("LaMa modeli indiriliyor...")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            import urllib.request
            url = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
            urllib.request.urlretrieve(url, model_path)

        # Device seç
        if torch.backends.mps.is_available():
            self.device = 'mps'
        elif torch.cuda.is_available():
            self.device = 'cuda'
        else:
            self.device = 'cpu'

        logger.info(f"LaMa modeli yükleniyor ({self.device})...")
        self.model = torch.jit.load(model_path, map_location='cpu')
        self.model = self.model.to(self.device)
        self.model.eval()
        logger.info("Model hazır!")

    def create_veo_mask(self, height: int, width: int, feather: bool = True) -> np.ndarray:
        """
        Veo watermark için mask oluştur
        Sağ alt köşedeki "Veo" yazısı - feathered edges ile
        """
        mask = np.zeros((height, width), dtype=np.uint8)

        # Veo watermark bölgesi (sağ alt köşe)
        # Daha geniş alan - kenarları da kapsasın
        margin_right = 5
        margin_bottom = 5
        wm_width = 85
        wm_height = 40

        x1 = width - wm_width - margin_right
        y1 = height - wm_height - margin_bottom
        x2 = width - margin_right
        y2 = height - margin_bottom

        # Daha fazla padding
        padding = 12
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(width, x2 + padding)
        y2 = min(height, y2 + padding)

        # Dikdörtgen mask
        mask[y1:y2, x1:x2] = 255

        if feather:
            # Gaussian blur ile kenarları yumuşat (feathering)
            mask = cv2.GaussianBlur(mask, (21, 21), 0)
            # Threshold ile tekrar binary yap ama soft edges kalsın
            _, mask = cv2.threshold(mask, 30, 255, cv2.THRESH_BINARY)
            # Tekrar hafif blur
            mask = cv2.GaussianBlur(mask, (5, 5), 0)

        return mask

    def get_mask_bounds(self, height: int, width: int) -> tuple:
        """Mask sınırlarını döndür (temporal smoothing için)"""
        margin_right = 5
        margin_bottom = 5
        wm_width = 85
        wm_height = 40
        padding = 15

        x1 = max(0, width - wm_width - margin_right - padding)
        y1 = max(0, height - wm_height - margin_bottom - padding)
        x2 = min(width, width - margin_right + padding)
        y2 = min(height, height - margin_bottom + padding)

        return y1, y2, x1, x2

    def inpaint_frame(self, frame: np.ndarray, mask: np.ndarray, blend_edges: bool = True) -> np.ndarray:
        """Tek bir frame'i inpaint et - edge blending ile"""
        import torch
        import torch.nn.functional as F

        # BGR -> RGB
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = img.shape[:2]
        original = frame.copy()

        # Binary mask (inpainting için)
        binary_mask = (mask > 127).astype(np.uint8) * 255

        # Tensörlere çevir
        img_tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        mask_tensor = torch.from_numpy(binary_mask).unsqueeze(0).unsqueeze(0).float() / 255.0

        # 8'in katına yuvarla (model gereksinimi)
        pad_h = (8 - height % 8) % 8
        pad_w = (8 - width % 8) % 8

        if pad_h > 0 or pad_w > 0:
            img_tensor = F.pad(img_tensor, (0, pad_w, 0, pad_h), mode='reflect')
            mask_tensor = F.pad(mask_tensor, (0, pad_w, 0, pad_h), mode='reflect')

        img_tensor = img_tensor.to(self.device)
        mask_tensor = mask_tensor.to(self.device)

        # Inpaint
        with torch.no_grad():
            result_tensor = self.model(img_tensor, mask_tensor)

        # Padding'i kaldır
        if pad_h > 0 or pad_w > 0:
            result_tensor = result_tensor[:, :, :height, :width]

        # Numpy'a çevir
        result = result_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
        result = (result * 255).clip(0, 255).astype(np.uint8)
        result = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)

        if blend_edges:
            # Soft blending mask oluştur
            blend_mask = cv2.GaussianBlur(binary_mask, (31, 31), 0)
            blend_mask = blend_mask.astype(np.float32) / 255.0
            blend_mask = np.stack([blend_mask] * 3, axis=-1)

            # Orijinal ve inpaint sonucunu blend et
            result = (result.astype(np.float32) * blend_mask +
                     original.astype(np.float32) * (1 - blend_mask))
            result = result.astype(np.uint8)

        return result

    def process_video(
        self,
        input_path: str,
        output_path: str,
        temporal_smooth: bool = True,
        smooth_window: int = 3
    ) -> bool:
        """
        Video watermark'ını kaldır

        Args:
            input_path: Girdi video yolu
            output_path: Çıktı video yolu
            temporal_smooth: Temporal smoothing uygula
            smooth_window: Smoothing pencere boyutu
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

            logger.info(f"Video: {width}x{height}, {fps}fps, {total_frames} frame")

            # Mask oluştur (tüm frameler için aynı)
            mask = self.create_veo_mask(height, width, feather=True)

            # Watermark bölgesinin koordinatları (smoothing için)
            wm_y1, wm_y2, wm_x1, wm_x2 = self.get_mask_bounds(height, width)

            # Temp video dosyası
            temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

            # Tüm frameleri oku ve işle
            frames = []
            inpainted_regions = []

            logger.info("Frameler işleniyor...")
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Frame'i inpaint et
                result = self.inpaint_frame(frame, mask)
                frames.append(result)

                # Watermark bölgesini sakla (temporal smoothing için)
                region = result[wm_y1:wm_y2, wm_x1:wm_x2].copy()
                inpainted_regions.append(region)

                frame_idx += 1
                if frame_idx % 10 == 0:
                    logger.info(f"İşlenen: {frame_idx}/{total_frames}")

            cap.release()

            # Temporal smoothing (opsiyonel - flickering azaltır)
            if temporal_smooth and len(frames) > smooth_window:
                logger.info("Gelişmiş temporal smoothing uygulanıyor...")

                # İlk geçiş - weighted average
                for i in range(len(frames)):
                    start_idx = max(0, i - smooth_window // 2)
                    end_idx = min(len(frames), i + smooth_window // 2 + 1)

                    window_regions = inpainted_regions[start_idx:end_idx]

                    if len(window_regions) > 1:
                        # Gaussian weighted average
                        weights = []
                        center = i - start_idx
                        for j in range(len(window_regions)):
                            dist = abs(j - center)
                            # Gaussian weight
                            weight = np.exp(-0.5 * (dist / 1.5) ** 2)
                            weights.append(weight)

                        weights = np.array(weights) / sum(weights)

                        smoothed_region = np.zeros_like(window_regions[0], dtype=np.float32)
                        for region, w in zip(window_regions, weights):
                            smoothed_region += region.astype(np.float32) * w

                        smoothed_region = smoothed_region.astype(np.uint8)

                        # Bilateral filter - edge-aware smoothing
                        smoothed_region = cv2.bilateralFilter(smoothed_region, 5, 50, 50)

                        frames[i][wm_y1:wm_y2, wm_x1:wm_x2] = smoothed_region

                # İkinci geçiş - forward-backward consistency
                logger.info("Forward-backward consistency kontrolü...")
                for i in range(1, len(frames) - 1):
                    prev_region = frames[i-1][wm_y1:wm_y2, wm_x1:wm_x2].astype(np.float32)
                    curr_region = frames[i][wm_y1:wm_y2, wm_x1:wm_x2].astype(np.float32)
                    next_region = frames[i+1][wm_y1:wm_y2, wm_x1:wm_x2].astype(np.float32)

                    # Önceki ve sonraki frame ortalaması ile karşılaştır
                    expected = (prev_region + next_region) / 2

                    # Fark çok büyükse düzelt (flickering)
                    diff = np.abs(curr_region - expected)
                    threshold = 30

                    # Sadece büyük farkları düzelt
                    correction_mask = (diff > threshold).astype(np.float32)
                    correction_mask = cv2.GaussianBlur(correction_mask, (5, 5), 0)

                    # Blend
                    corrected = curr_region * (1 - correction_mask * 0.5) + expected * (correction_mask * 0.5)
                    frames[i][wm_y1:wm_y2, wm_x1:wm_x2] = corrected.astype(np.uint8)

            # Frameleri yaz
            logger.info("Video yazılıyor...")
            for frame in frames:
                out.write(frame)

            out.release()

            # FFmpeg ile ses ekle ve finalize et
            self._finalize_video(input_path, temp_video, output_path)

            logger.info(f"Tamamlandı: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Video işleme hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _finalize_video(self, original_path: str, temp_video: str, output_path: str):
        """FFmpeg ile ses ekle ve H.264 encode et"""
        try:
            # Orijinalden ses çıkar
            temp_audio = tempfile.NamedTemporaryFile(suffix='.aac', delete=False).name

            result = subprocess.run([
                'ffmpeg', '-y', '-i', original_path,
                '-vn', '-acodec', 'aac', '-b:a', '192k', temp_audio
            ], capture_output=True, timeout=60)

            has_audio = os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000

            if has_audio:
                # Video + Audio birleştir
                subprocess.run([
                    'ffmpeg', '-y',
                    '-i', temp_video,
                    '-i', temp_audio,
                    '-c:v', 'libx264',
                    '-preset', 'slow',  # Daha iyi kalite
                    '-crf', '17',  # Yüksek kalite
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest',
                    '-movflags', '+faststart',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ], capture_output=True, timeout=300)

                os.unlink(temp_audio)
            else:
                # Sadece video
                subprocess.run([
                    'ffmpeg', '-y',
                    '-i', temp_video,
                    '-c:v', 'libx264',
                    '-preset', 'slow',
                    '-crf', '17',
                    '-movflags', '+faststart',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ], capture_output=True, timeout=300)

            os.unlink(temp_video)

        except Exception as e:
            logger.warning(f"FFmpeg hatası: {e}")
            import shutil
            shutil.move(temp_video, output_path)


def remove_video_watermark_lama(input_path: str, output_path: str) -> bool:
    """
    Ana fonksiyon - Video watermark kaldır
    """
    inpainter = LamaVideoInpainter()
    return inpainter.process_video(input_path, output_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.mp4', '_lama.mp4')
    else:
        # Default test
        input_file = "/Users/hasan/Desktop/auto/gemini_pro_projects/shorts_20251226_183916/video_1.mp4"
        output_file = "/Users/hasan/Desktop/auto/gemini_pro_projects/shorts_20251226_183916/video_1_lama.mp4"

    print("=" * 50)
    print("LaMa Video Watermark Remover")
    print("=" * 50)

    success = remove_video_watermark_lama(input_file, output_file)

    if success:
        print(f"\n✓ Başarılı: {output_file}")
    else:
        print("\n✗ Başarısız!")
