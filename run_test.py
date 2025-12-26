#!/usr/bin/env python3
"""
Auto Shorts Image Generator - Test Script
Bu script sistemi test eder ve sonuçları gösterir.
"""
import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generator import run_test
from datetime import datetime

def main():
    print("\n" + "="*60)
    print("  AUTO SHORTS IMAGE GENERATOR - TEST")
    print("="*60)
    print(f"  Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    print("[*] Test başlatılıyor...")
    print("[*] Chrome tarayıcı açılacak, lütfen bekleyin...")
    print("[*] İlk çalıştırmada Google hesabına giriş yapmanız gerekebilir.\n")

    # Progress callback
    def progress_callback(message, percentage):
        bar_length = 30
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r[{bar}] {percentage:3d}% | {message:<50}", end='', flush=True)

    try:
        results = run_test(progress_callback=progress_callback)

        print("\n\n" + "="*60)
        print("  TEST SONUÇLARI")
        print("="*60)

        print(f"\n  Proje: {results['project_name']}")
        print(f"  Klasör: {results['project_dir']}")
        print(f"  Durum: {'✓ Başarılı' if results['success'] else '✗ Başarısız'}")

        if results.get('error'):
            print(f"  Hata: {results['error']}")

        if results.get('images'):
            print(f"\n  Oluşturulan Görseller ({len(results['images'])} adet):")
            for i, img in enumerate(results['images'], 1):
                status = '✓' if img['success'] else '✗'
                print(f"    {status} Görsel {i}:")
                print(f"      - Prompt: {img['prompt'][:50]}...")
                if img.get('original_path'):
                    print(f"      - Original: {img['original_path']}")
                if img.get('cleaned_path'):
                    print(f"      - Temiz: {img['cleaned_path']}")
                if img.get('error'):
                    print(f"      - Hata: {img['error']}")

        if results.get('voice'):
            print(f"\n  Seslendirme:")
            print(f"    - Metin: \"{results['voice'].get('text', 'N/A')}\"")
            print(f"    - Stil: {results['voice'].get('style', 'N/A')}")

        print("\n" + "="*60)
        print("  TARAYICI KONTROL İÇİN AÇIK BIRAKILDI")
        print("="*60 + "\n")

    except KeyboardInterrupt:
        print("\n\n[!] Test kullanıcı tarafından iptal edildi.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[!] Test hatası: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
