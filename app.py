"""
Auto Shorts Image Generator - Flask Web Application
"""
import os
import json
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

import config

logger = logging.getLogger(__name__)
from generator import GeminiImageGenerator, run_test

app = Flask(__name__)

# Global state for tracking progress
current_task = {
    "running": False,
    "progress": 0,
    "message": "",
    "results": None,
    "error": None
}
task_lock = threading.Lock()


def update_progress(message: str, percentage: int):
    """İlerleme durumunu güncelle"""
    global current_task
    with task_lock:
        current_task["message"] = message
        current_task["progress"] = percentage


@app.route("/")
def index():
    """Ana sayfa"""
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    """Görsel oluşturma endpoint'i"""
    global current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Başlatılıyor..."
        current_task["results"] = None
        current_task["error"] = None

    data = request.get_json()
    script = data.get("script", "")

    def run_generation():
        global current_task
        try:
            generator = GeminiImageGenerator(
                project_name=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                progress_callback=update_progress
            )

            results = generator.process_video_script(script)
            generator.close(keep_open=True)

            with task_lock:
                current_task["results"] = results
                current_task["running"] = False

        except Exception as e:
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_generation)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/test", methods=["POST"])
def test_system():
    """Test sistemini çalıştır"""
    global current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Test başlatılıyor..."
        current_task["results"] = None
        current_task["error"] = None

    def run_test_task():
        global current_task
        try:
            results = run_test(progress_callback=update_progress)

            with task_lock:
                current_task["results"] = results
                current_task["running"] = False

        except Exception as e:
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_test_task)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/progress")
def get_progress():
    """İlerleme durumunu döndür"""
    global current_task
    with task_lock:
        return jsonify({
            "running": current_task["running"],
            "progress": current_task["progress"],
            "message": current_task["message"],
            "results": current_task["results"],
            "error": current_task["error"]
        })


@app.route("/api/projects")
def list_projects():
    """Projeleri listele"""
    projects = []
    if os.path.exists(config.PROJECTS_DIR):
        for name in os.listdir(config.PROJECTS_DIR):
            path = os.path.join(config.PROJECTS_DIR, name)
            if os.path.isdir(path):
                images = [f for f in os.listdir(path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                videos = [f for f in os.listdir(path) if f.endswith(('.mp4', '.webm', '.mov'))]
                projects.append({
                    "name": name,
                    "path": path,
                    "images": images,
                    "videos": videos,
                    "created": datetime.fromtimestamp(os.path.getctime(path)).isoformat()
                })
    return jsonify(sorted(projects, key=lambda x: x["created"], reverse=True))


@app.route("/projects/<project_name>/<filename>")
def serve_project_file(project_name, filename):
    """Proje dosyalarını sun (görsel ve video)"""
    return send_from_directory(
        os.path.join(config.PROJECTS_DIR, project_name),
        filename
    )


@app.route("/projects/<project_name>/output/<filename>")
def serve_output_file(project_name, filename):
    """Output klasöründeki dosyaları sun (final video, ses)"""
    return send_from_directory(
        os.path.join(config.PROJECTS_DIR, project_name, "output"),
        filename
    )


@app.route("/api/project/<project_name>/check")
def check_project(project_name):
    """Projedeki eksikleri kontrol et"""
    try:
        import re
        project_dir = os.path.join(config.PROJECTS_DIR, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        # Proje metadata'sını oku (beklenen sayılar)
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

        # Dosyaları listele
        files = os.listdir(project_dir)

        # Görsel, video ve thumbnail numaralarını bul
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

        # Beklenen sayıları belirle (metadata varsa onu kullan, yoksa mevcut max'ı)
        if expected_images == 0:
            expected_images = max(image_numbers) if image_numbers else 0
        if expected_videos == 0:
            expected_videos = max(video_numbers) if video_numbers else 0
        if expected_thumbnails == 0:
            expected_thumbnails = max(thumbnail_numbers) if thumbnail_numbers else 0

        # Eksikleri bul
        expected_image_set = set(range(1, expected_images + 1))
        expected_video_set = set(range(1, expected_videos + 1))
        expected_thumb_set = set(range(1, expected_thumbnails + 1))

        missing_images = sorted(expected_image_set - image_numbers)
        missing_videos = sorted(expected_video_set - video_numbers)
        missing_thumbnails = sorted(expected_thumb_set - thumbnail_numbers)

        # Output kontrolü
        output_dir = os.path.join(project_dir, "output")
        has_final = False
        if os.path.exists(output_dir):
            has_final = any(f.startswith("final_video") for f in os.listdir(output_dir))

        is_complete = (len(missing_images) == 0 and
                       len(missing_videos) == 0 and
                       len(missing_thumbnails) == 0)

        return jsonify({
            "project_name": project_name,
            "expected_images": expected_images,
            "expected_videos": expected_videos,
            "expected_thumbnails": expected_thumbnails,
            "existing_images": sorted(image_numbers),
            "existing_videos": sorted(video_numbers),
            "existing_thumbnails": sorted(thumbnail_numbers),
            "missing_images": missing_images,
            "missing_videos": missing_videos,
            "missing_thumbnails": missing_thumbnails,
            "has_final_video": has_final,
            "is_complete": is_complete
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/project/<project_name>/complete", methods=["POST"])
def complete_project(project_name):
    """Eksik görsel ve videoları tamamla, render yap"""
    global current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Eksikler kontrol ediliyor..."
        current_task["results"] = None
        current_task["error"] = None

    data = request.get_json() or {}
    # Eksik görseller için promptlar (opsiyonel)
    image_prompts = data.get("image_prompts", {})  # {2: "prompt for image 2", ...}
    video_prompts = data.get("video_prompts", {})  # {2: "prompt for video 2", ...}
    voice_text = data.get("voice_text", "")

    def run_completion():
        global current_task
        try:
            from complete_project import complete_missing_items

            results = complete_missing_items(
                project_name=project_name,
                image_prompts=image_prompts,
                video_prompts=video_prompts,
                voice_text=voice_text,
                progress_callback=update_progress
            )

            with task_lock:
                current_task["results"] = results
                current_task["running"] = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_completion)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/project/<project_name>/details")
def get_project_details(project_name):
    """Proje detaylarını getir (promptlar dahil)"""
    try:
        project_dir = os.path.join(config.PROJECTS_DIR, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        # Proje metadata'sını oku
        meta_path = os.path.join(project_dir, "project.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        # Dosyaları listele
        files = os.listdir(project_dir)
        import re

        # Mevcut dosyaları bul
        existing_images = {}
        existing_videos = {}
        existing_thumbnails = {}

        for f in files:
            match = re.match(r'image_(\d+)_cleaned\.png', f)
            if match:
                idx = int(match.group(1))
                existing_images[str(idx)] = f"/projects/{project_name}/{f}"

            match = re.match(r'video_(\d+)\.mp4', f)
            if match:
                idx = int(match.group(1))
                existing_videos[str(idx)] = f"/projects/{project_name}/{f}"

            match = re.match(r'thumbnail_(\d+)_cleaned\.png', f)
            if match:
                idx = int(match.group(1))
                existing_thumbnails[str(idx)] = f"/projects/{project_name}/{f}"

        # Output kontrolü
        output_dir = os.path.join(project_dir, "output")
        final_video = None
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.startswith("final_video"):
                    final_video = f"/projects/{project_name}/output/{f}"
                    break

        return jsonify({
            "project_name": project_name,
            "created_at": meta.get("created_at", ""),
            "expected_images": meta.get("expected_images", 0),
            "expected_videos": meta.get("expected_videos", 0),
            "expected_thumbnails": meta.get("expected_thumbnails", 0),
            "image_prompts": meta.get("image_prompts", {}),
            "video_prompts": meta.get("video_prompts", {}),
            "thumbnail_prompts": meta.get("thumbnail_prompts", {}),
            "voice": meta.get("voice", {}),
            "existing_images": existing_images,
            "existing_videos": existing_videos,
            "existing_thumbnails": existing_thumbnails,
            "final_video": final_video
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/project/<project_name>/update-prompts", methods=["POST"])
def update_project_prompts(project_name):
    """Proje promptlarını güncelle"""
    try:
        project_dir = os.path.join(config.PROJECTS_DIR, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        # Mevcut metadata'yı oku
        meta_path = os.path.join(project_dir, "project.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        data = request.get_json() or {}

        # Önceki promptları kaydet (değişiklik tespiti için)
        old_image_prompts = meta.get("image_prompts", {}).copy()
        old_video_prompts = meta.get("video_prompts", {}).copy()
        old_thumbnail_prompts = meta.get("thumbnail_prompts", {}).copy()

        # Yeni promptları güncelle
        if "image_prompts" in data:
            meta["image_prompts"] = data["image_prompts"]
        if "video_prompts" in data:
            meta["video_prompts"] = data["video_prompts"]
        if "thumbnail_prompts" in data:
            meta["thumbnail_prompts"] = data["thumbnail_prompts"]
        if "voice" in data:
            meta["voice"] = data["voice"]

        # Değişiklikleri tespit et
        changed_images = []
        changed_videos = []
        changed_thumbnails = []

        for idx, prompt in meta.get("image_prompts", {}).items():
            if old_image_prompts.get(idx) != prompt:
                changed_images.append(int(idx))

        for idx, prompt in meta.get("video_prompts", {}).items():
            if old_video_prompts.get(idx) != prompt:
                changed_videos.append(int(idx))

        for idx, prompt in meta.get("thumbnail_prompts", {}).items():
            if old_thumbnail_prompts.get(idx) != prompt:
                changed_thumbnails.append(int(idx))

        # Kaydet
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "changed_images": sorted(changed_images),
            "changed_videos": sorted(changed_videos),
            "changed_thumbnails": sorted(changed_thumbnails)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/project/<project_name>/regenerate", methods=["POST"])
def regenerate_items(project_name):
    """Belirli görsel/video/thumbnail'leri yeniden oluştur"""
    global current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Yeniden oluşturma başlıyor..."
        current_task["results"] = None
        current_task["error"] = None

    data = request.get_json() or {}
    regenerate_images = data.get("images", [])  # [1, 3, 5]
    regenerate_videos = data.get("videos", [])  # [2, 4]
    regenerate_thumbnails = data.get("thumbnails", [])

    def run_regeneration():
        global current_task
        try:
            project_dir = os.path.join(config.PROJECTS_DIR, project_name)
            meta_path = os.path.join(project_dir, "project.json")

            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            image_prompts = {idx: meta.get("image_prompts", {}).get(str(idx), "") for idx in regenerate_images}
            video_prompts = {idx: meta.get("video_prompts", {}).get(str(idx), "") for idx in regenerate_videos}

            # Mevcut dosyaları sil (yeniden oluşturulacaklar)
            for idx in regenerate_images:
                for pattern in [f"image_{idx}_original.png", f"image_{idx}_cleaned.png"]:
                    path = os.path.join(project_dir, pattern)
                    if os.path.exists(path):
                        os.remove(path)

            for idx in regenerate_videos:
                path = os.path.join(project_dir, f"video_{idx}.mp4")
                if os.path.exists(path):
                    os.remove(path)

            from complete_project import complete_missing_items

            results = complete_missing_items(
                project_name=project_name,
                image_prompts=image_prompts,
                video_prompts=video_prompts,
                voice_text=meta.get("voice", {}).get("text", ""),
                progress_callback=update_progress
            )

            with task_lock:
                current_task["results"] = results
                current_task["running"] = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_regeneration)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/project/<project_name>/render", methods=["POST"])
def render_project_video(project_name):
    """Projeyi render et (final video oluştur)"""
    global current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Render başlıyor..."
        current_task["results"] = None
        current_task["error"] = None

    data = request.get_json() or {}
    voice_text = data.get("voice_text", "")
    voice_style = data.get("voice_style", "friendly")

    def run_render():
        global current_task
        try:
            from video_renderer import render_project
            import glob

            project_dir = os.path.join(config.PROJECTS_DIR, project_name)

            # Video dosyalarını bul - sayısal sıralama ile
            video_files = glob.glob(os.path.join(project_dir, "video_*.mp4"))
            video_files = [v for v in video_files if "final" not in v]

            # Sayısal sıralama (video_1, video_2, ... video_10)
            import re
            def extract_number(path):
                match = re.search(r'video_(\d+)\.mp4', path)
                return int(match.group(1)) if match else 0

            video_files = sorted(video_files, key=extract_number)

            logger.info(f"Render için bulunan videolar: {[os.path.basename(v) for v in video_files]}")

            if not video_files:
                raise Exception("Video dosyası bulunamadı")

            result = render_project(
                project_dir=project_dir,
                video_paths=video_files,
                voice_text=voice_text,
                voice_style=voice_style,
                words_per_subtitle=2,
                progress_callback=update_progress
            )

            with task_lock:
                current_task["results"] = {
                    "success": result.get("success", False),
                    "project_name": project_name,
                    "final_video": result.get("final_video")
                }
                current_task["running"] = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_render)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/project/<project_name>/generate-voice", methods=["POST"])
def generate_voice(project_name):
    """Ses dosyası oluştur"""
    try:
        import edge_tts
        import asyncio

        data = request.get_json() or {}
        text = data.get("text", "")
        style = data.get("style", "friendly")

        if not text:
            return jsonify({"error": "Metin gerekli"}), 400

        project_dir = os.path.join(config.PROJECTS_DIR, project_name)
        output_dir = os.path.join(project_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "narration.mp3")

        # Voice mapping
        voice_map = {
            "friendly": "en-US-ChristopherNeural",
            "professional": "en-US-GuyNeural",
            "dramatic": "en-US-AriaNeural",
            "calm": "en-US-JennyNeural"
        }
        voice = voice_map.get(style, "en-US-ChristopherNeural")

        async def generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)

        asyncio.run(generate())

        return jsonify({"success": True, "path": output_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/claude/chat", methods=["POST"])
def claude_chat():
    """Claude CLI ile iletişim"""
    try:
        import subprocess

        data = request.get_json() or {}
        message = data.get("message", "")
        project = data.get("project", None)

        if not message:
            return jsonify({"error": "Mesaj gerekli"}), 400

        # Proje context'i ekle
        context = ""
        if project:
            project_dir = os.path.join(config.PROJECTS_DIR, project)
            meta_path = os.path.join(project_dir, "project.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                context = f"""Sen bir video prodüksiyon asistanısın. Bu proje hakkında yardım et.

Proje: {project}
Beklenen görsel sayısı: {meta.get('expected_images', 0)}
Beklenen video sayısı: {meta.get('expected_videos', 0)}
Görsel promptları: {json.dumps(meta.get('image_prompts', {}), ensure_ascii=False)}
Video promptları: {json.dumps(meta.get('video_prompts', {}), ensure_ascii=False)}
Ses metni: {meta.get('voice', {}).get('text', 'Yok')}

Kullanıcı isteği: """

        full_message = context + message if context else message

        # Claude CLI çağır (--print ile daha hızlı)
        result = subprocess.run(
            ["claude", "-p", full_message, "--no-markdown"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(__file__)
        )

        response = result.stdout.strip() or result.stderr.strip() or "Yanıt alınamadı"

        return jsonify({"response": response})

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Claude zaman aşımı (2 dakika)"}), 500
    except FileNotFoundError:
        return jsonify({"error": "Claude CLI bulunamadı. Terminalde 'claude' komutunun çalıştığından emin olun."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/switch-grok-account", methods=["POST"])
def switch_grok_account():
    """Grok hesabını değiştir - Chrome profilini temizle"""
    try:
        import shutil
        grok_profile = os.path.join(os.path.dirname(__file__), "chrome_profiles", "grok_profile")

        if os.path.exists(grok_profile):
            # Profili sil (yeni giriş için)
            shutil.rmtree(grok_profile)
            os.makedirs(grok_profile, exist_ok=True)
            return jsonify({"success": True, "message": "Grok oturumu temizlendi"})
        else:
            return jsonify({"success": True, "message": "Grok profili zaten temiz"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/switch-gemini-account", methods=["POST"])
def switch_gemini_account():
    """Gemini hesabını değiştir - Chrome profilini temizle"""
    try:
        import shutil
        gemini_profile = os.path.join(os.path.dirname(__file__), "chrome_profiles", "gemini_profile")

        if os.path.exists(gemini_profile):
            # Profili sil (yeni giriş için)
            shutil.rmtree(gemini_profile)
            os.makedirs(gemini_profile, exist_ok=True)
            return jsonify({"success": True, "message": "Gemini oturumu temizlendi"})
        else:
            return jsonify({"success": True, "message": "Gemini profili zaten temiz"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== GEMINI PRO API ====================

# Global Gemini Pro manager instance
gemini_pro_manager = None


@app.route("/api/gemini-pro/status")
def gemini_pro_status():
    """Gemini Pro hesap durumlarını göster"""
    try:
        from gemini_pro_manager import GeminiProManager

        global gemini_pro_manager
        if not gemini_pro_manager:
            gemini_pro_manager = GeminiProManager()

        capacity = gemini_pro_manager.get_daily_capacity()
        return jsonify(capacity)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/setup", methods=["POST"])
def gemini_pro_setup():
    """Gemini Pro hesaplarını kurulum için aç"""
    global gemini_pro_manager, current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

    try:
        from gemini_pro_manager import GeminiProManager

        # Mevcut manager varsa yeniden kullan, yoksa yeni oluştur
        if not gemini_pro_manager:
            gemini_pro_manager = GeminiProManager(progress_callback=update_progress)
        else:
            # Progress callback'i güncelle
            gemini_pro_manager.progress_callback = update_progress

        result = gemini_pro_manager.setup_accounts()
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/verify", methods=["POST"])
def gemini_pro_verify():
    """Gemini Pro hesaplarının giriş durumunu kontrol et"""
    global gemini_pro_manager

    if not gemini_pro_manager:
        return jsonify({"error": "Önce setup yapın"}), 400

    try:
        result = gemini_pro_manager.verify_all_accounts()
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/close", methods=["POST"])
def gemini_pro_close():
    """Tüm Gemini Pro tarayıcılarını kapat"""
    global gemini_pro_manager

    if gemini_pro_manager:
        gemini_pro_manager.close_all()
        gemini_pro_manager = None

    return jsonify({"success": True, "message": "Tüm tarayıcılar kapatıldı"})


@app.route("/api/gemini-pro/stop", methods=["POST"])
def gemini_pro_stop():
    """Devam eden işlemi durdur"""
    global gemini_pro_manager, current_task

    with task_lock:
        if current_task["running"]:
            current_task["running"] = False
            current_task["error"] = "Kullanıcı tarafından durduruldu"

    # Tarayıcıları kapat
    if gemini_pro_manager:
        gemini_pro_manager.close_all()

    return jsonify({"success": True, "message": "İşlem durduruldu"})


@app.route("/api/gemini-pro/daily-shorts", methods=["POST"])
def gemini_pro_daily_shorts():
    """Günlük shorts projesi başlat (9 video/gün)"""
    global gemini_pro_manager, current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Günlük shorts başlıyor..."
        current_task["results"] = None
        current_task["error"] = None

    data = request.get_json() or {}
    prompts = data.get("prompts", [])  # [{"image_prompt": "...", "video_prompt": "..."}, ...]
    voice_text = data.get("voice_text", "")  # Seslendirme metni
    aspect_format = data.get("format", "9:16")  # Video formatı
    thumbnail_prompt = data.get("thumbnail_prompt", "")  # Thumbnail prompt

    if not prompts:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": "Prompt listesi gerekli"}), 400

    if len(prompts) > 9:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": "Günde maksimum 9 video"}), 400

    def run_shorts():
        global gemini_pro_manager, current_task
        try:
            logger.info("=== run_shorts thread başladı ===")
            from gemini_pro_manager import GeminiProManager, DailyShortsMode

            if not gemini_pro_manager:
                logger.info("gemini_pro_manager None - yeni oluşturuluyor")
                gemini_pro_manager = GeminiProManager(progress_callback=update_progress)
            else:
                logger.info(f"gemini_pro_manager mevcut - hesap sayısı: {len(gemini_pro_manager.accounts)}")
                # Her hesabın driver durumunu logla
                for acc in gemini_pro_manager.accounts:
                    logger.info(f"  Hesap {acc.account_id}: driver={acc.driver is not None}, alive={acc.is_browser_alive()}")
                # Progress callback'i güncelle
                gemini_pro_manager.progress_callback = update_progress

            logger.info(f"DailyShortsMode oluşturuluyor, prompts={len(prompts)}")
            shorts_mode = DailyShortsMode(gemini_pro_manager)

            logger.info("create_daily_project çağrılıyor...")
            result = shorts_mode.create_daily_project(prompts, voice_text, aspect_format, thumbnail_prompt)
            logger.info(f"create_daily_project sonuç: {result}")

            with task_lock:
                current_task["results"] = result
                current_task["running"] = False

        except Exception as e:
            import traceback
            logger.error(f"=== run_shorts HATA: {e} ===")
            traceback.print_exc()
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_shorts)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/gemini-pro/long-video", methods=["POST"])
def gemini_pro_long_video():
    """Uzun video projesi oluştur (63 prompt / 7 gün)"""
    global gemini_pro_manager

    data = request.get_json() or {}
    prompts = data.get("prompts", [])
    voice_text = data.get("voice_text", "")

    if not prompts:
        return jsonify({"error": "Prompt listesi gerekli"}), 400

    if len(prompts) > 63:
        return jsonify({"error": "Maksimum 63 prompt (7 gün x 9 video)"}), 400

    try:
        from gemini_pro_manager import GeminiProManager, LongVideoMode

        if not gemini_pro_manager:
            gemini_pro_manager = GeminiProManager()

        long_mode = LongVideoMode(gemini_pro_manager)
        result = long_mode.create_weekly_project(prompts, voice_text)
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/run-daily-batch", methods=["POST"])
def gemini_pro_run_daily_batch():
    """Uzun video projesinin bugünkü batch'ini çalıştır"""
    global gemini_pro_manager, current_task

    with task_lock:
        if current_task["running"]:
            return jsonify({"error": "Bir işlem zaten devam ediyor"}), 400

        current_task["running"] = True
        current_task["progress"] = 0
        current_task["message"] = "Günlük batch başlıyor..."

    data = request.get_json() or {}
    project_dir = data.get("project_dir", "")

    if not project_dir:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": "project_dir gerekli"}), 400

    def run_batch():
        global gemini_pro_manager, current_task
        try:
            from gemini_pro_manager import GeminiProManager, LongVideoMode

            if not gemini_pro_manager:
                gemini_pro_manager = GeminiProManager(progress_callback=update_progress)

            long_mode = LongVideoMode(gemini_pro_manager)
            result = long_mode.run_daily_batch(project_dir)

            with task_lock:
                current_task["results"] = result
                current_task["running"] = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            with task_lock:
                current_task["error"] = str(e)
                current_task["running"] = False

    thread = threading.Thread(target=run_batch)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/gemini-pro/projects")
def gemini_pro_projects():
    """Gemini Pro projelerini listele"""
    try:
        from gemini_pro_manager import GeminiProManager
        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")

        if not os.path.exists(projects_dir):
            return jsonify({"projects": []})

        projects = []
        for name in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, name)
            if os.path.isdir(project_path):
                schedule_path = os.path.join(project_path, "schedule.json")
                if os.path.exists(schedule_path):
                    with open(schedule_path, "r") as f:
                        schedule = json.load(f)
                    projects.append({
                        "name": name,
                        "type": "long_video" if "longvideo" in name else "shorts",
                        "created_at": schedule.get("created_at"),
                        "total_prompts": schedule.get("total_prompts"),
                        "days": schedule.get("days"),
                        "status": schedule.get("status")
                    })
                else:
                    projects.append({
                        "name": name,
                        "type": "shorts",
                        "created_at": None
                    })

        return jsonify({"projects": projects})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/projects/<project_name>")
def gemini_pro_project_detail(project_name):
    """Gemini Pro proje detayı"""
    try:
        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_path = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_path):
            return jsonify({"error": "Proje bulunamadı"}), 404

        project_data = {
            "name": project_name,
            "path": project_path,
            "images": [],
            "videos": [],
            "final_video": None,
            "schedule": None,
            "project_json": None
        }

        # Dosyaları listele
        for f in os.listdir(project_path):
            file_path = os.path.join(project_path, f)
            if f.endswith(".png") or f.endswith(".jpg"):
                project_data["images"].append({
                    "name": f,
                    "path": file_path,
                    "url": f"/projects/gemini/{project_name}/{f}"
                })
            elif f.endswith(".mp4"):
                if "final" in f.lower():
                    project_data["final_video"] = {
                        "name": f,
                        "path": file_path,
                        "url": f"/projects/gemini/{project_name}/{f}"
                    }
                else:
                    project_data["videos"].append({
                        "name": f,
                        "path": file_path,
                        "url": f"/projects/gemini/{project_name}/{f}"
                    })
            elif f == "schedule.json":
                with open(file_path, "r", encoding="utf-8") as sf:
                    project_data["schedule"] = json.load(sf)
            elif f == "project.json":
                with open(file_path, "r", encoding="utf-8") as pf:
                    project_data["project_json"] = json.load(pf)

        # Sırala
        project_data["images"].sort(key=lambda x: x["name"])
        project_data["videos"].sort(key=lambda x: x["name"])

        return jsonify(project_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/projects/gemini/<project_name>/<filename>")
def serve_gemini_project_file(project_name, filename):
    """Gemini proje dosyalarını serve et"""
    projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
    project_path = os.path.join(projects_dir, project_name)
    return send_from_directory(project_path, filename)


@app.route("/api/gemini-pro/retry-failed", methods=["POST"])
def gemini_pro_retry_failed():
    """Başarısız olanları yeniden dene"""
    global gemini_pro_manager, current_task

    try:
        data = request.get_json()
        project_name = data.get("project_name")
        indices = data.get("indices")  # Belirli indeksler veya None (tümü)

        if not project_name:
            return jsonify({"error": "project_name gerekli"}), 400

        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_dir = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        with task_lock:
            if current_task["running"]:
                return jsonify({"error": "Başka bir işlem devam ediyor"}), 400
            current_task["running"] = True
            current_task["type"] = "gemini_pro_retry"
            current_task["progress"] = 0
            current_task["message"] = "Yeniden deneme başlıyor..."
            current_task["error"] = None

        def run_retry():
            global gemini_pro_manager, current_task
            try:
                from gemini_pro_manager import GeminiProManager, DailyShortsMode

                if not gemini_pro_manager:
                    gemini_pro_manager = GeminiProManager(progress_callback=update_progress)
                else:
                    gemini_pro_manager.progress_callback = update_progress

                shorts_mode = DailyShortsMode(gemini_pro_manager)
                result = shorts_mode.retry_failed(project_dir, indices)

                with task_lock:
                    current_task["result"] = result
                    current_task["running"] = False

            except Exception as e:
                logger.error(f"Retry hatası: {e}")
                import traceback
                traceback.print_exc()
                with task_lock:
                    current_task["error"] = str(e)
                    current_task["running"] = False

        import threading
        thread = threading.Thread(target=run_retry)
        thread.start()

        return jsonify({"success": True, "message": "Yeniden deneme başlatıldı"})

    except Exception as e:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/update-prompt", methods=["POST"])
def gemini_pro_update_prompt():
    """Prompt güncelle"""
    try:
        data = request.get_json()
        project_name = data.get("project_name")
        index = data.get("index")
        image_prompt = data.get("image_prompt")
        video_prompt = data.get("video_prompt")

        if not project_name or not index:
            return jsonify({"error": "project_name ve index gerekli"}), 400

        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_dir = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        from gemini_pro_manager import GeminiProManager, DailyShortsMode
        manager = GeminiProManager()
        shorts_mode = DailyShortsMode(manager)

        result = shorts_mode.update_prompt(project_dir, index, image_prompt, video_prompt)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/update-voice", methods=["POST"])
def gemini_pro_update_voice():
    """Ses metni güncelle"""
    try:
        data = request.get_json()
        project_name = data.get("project_name")
        voice_text = data.get("voice_text")

        if not project_name:
            return jsonify({"error": "project_name gerekli"}), 400

        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_dir = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        from gemini_pro_manager import GeminiProManager, DailyShortsMode
        manager = GeminiProManager()
        shorts_mode = DailyShortsMode(manager)

        result = shorts_mode.update_voice(project_dir, voice_text)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/create-thumbnail", methods=["POST"])
def gemini_pro_create_thumbnail():
    """Thumbnail oluştur"""
    global gemini_pro_manager, current_task

    try:
        data = request.get_json()
        project_name = data.get("project_name")

        if not project_name:
            return jsonify({"error": "project_name gerekli"}), 400

        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_dir = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        # project.json'dan thumbnail prompt'u al
        project_json_path = os.path.join(project_dir, "project.json")
        if not os.path.exists(project_json_path):
            return jsonify({"error": "project.json bulunamadı"}), 404

        with open(project_json_path, "r", encoding="utf-8") as f:
            project_data = json.load(f)

        thumbnail_prompt = project_data.get("thumbnail_prompt", "")
        if not thumbnail_prompt:
            return jsonify({"error": "Thumbnail prompt bulunamadı"}), 400

        with task_lock:
            if current_task["running"]:
                return jsonify({"error": "Başka bir işlem devam ediyor"}), 400
            current_task["running"] = True
            current_task["type"] = "gemini_pro_thumbnail"
            current_task["progress"] = 0
            current_task["message"] = "Thumbnail oluşturuluyor..."
            current_task["error"] = None

        def run_thumbnail():
            global gemini_pro_manager, current_task
            try:
                from gemini_pro_manager import GeminiProManager

                if not gemini_pro_manager:
                    gemini_pro_manager = GeminiProManager(progress_callback=update_progress)
                else:
                    gemini_pro_manager.progress_callback = update_progress

                account = gemini_pro_manager.get_available_account()
                if not account:
                    with task_lock:
                        current_task["error"] = "Kullanılabilir hesap yok"
                        current_task["running"] = False
                    return

                if not account.driver:
                    account.start_browser()
                    account.navigate_to_gemini()

                update_progress("Thumbnail oluşturuluyor...", 30)

                # Thumbnail için 16:9 format
                thumb_full_prompt = f"Create a YouTube thumbnail image in horizontal 16:9 aspect ratio (1920x1080 pixels): {thumbnail_prompt}"

                prev_count = account._count_generated_images()
                if account.send_prompt(thumb_full_prompt):
                    if account.wait_for_image_generation(prev_count):
                        thumbnail_path = os.path.join(project_dir, "thumbnail.png")
                        if account.download_latest_image(thumbnail_path):
                            # Watermark temizle
                            try:
                                from watermark_remover import remove_watermark
                                cleaned_thumb = os.path.join(project_dir, "thumbnail_cleaned.png")
                                remove_watermark(thumbnail_path, cleaned_thumb)
                                os.replace(cleaned_thumb, thumbnail_path)
                            except:
                                pass

                            project_data["thumbnail_status"] = "completed"
                            with open(project_json_path, "w", encoding="utf-8") as f:
                                json.dump(project_data, f, indent=2, ensure_ascii=False)

                            update_progress("Thumbnail oluşturuldu!", 100)

                            with task_lock:
                                current_task["result"] = {"thumbnail": thumbnail_path}
                                current_task["running"] = False
                            return

                project_data["thumbnail_status"] = "failed"
                with open(project_json_path, "w", encoding="utf-8") as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)

                with task_lock:
                    current_task["error"] = "Thumbnail oluşturulamadı"
                    current_task["running"] = False

            except Exception as e:
                logger.error(f"Thumbnail hatası: {e}")
                with task_lock:
                    current_task["error"] = str(e)
                    current_task["running"] = False

        import threading
        thread = threading.Thread(target=run_thumbnail)
        thread.start()

        return jsonify({"success": True, "message": "Thumbnail oluşturma başlatıldı"})

    except Exception as e:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": str(e)}), 500


@app.route("/api/gemini-pro/render-project", methods=["POST"])
def gemini_pro_render_project():
    """Projeyi renderla"""
    global current_task

    try:
        data = request.get_json()
        project_name = data.get("project_name")

        if not project_name:
            return jsonify({"error": "project_name gerekli"}), 400

        projects_dir = os.path.join(config.BASE_DIR, "gemini_pro_projects")
        project_dir = os.path.join(projects_dir, project_name)

        if not os.path.exists(project_dir):
            return jsonify({"error": "Proje bulunamadı"}), 404

        # project.json'dan bilgileri al
        project_json_path = os.path.join(project_dir, "project.json")
        if not os.path.exists(project_json_path):
            return jsonify({"error": "project.json bulunamadı"}), 404

        with open(project_json_path, "r", encoding="utf-8") as f:
            project_data = json.load(f)

        with task_lock:
            if current_task["running"]:
                return jsonify({"error": "Başka bir işlem devam ediyor"}), 400
            current_task["running"] = True
            current_task["type"] = "gemini_pro_render"
            current_task["progress"] = 0
            current_task["message"] = "Render başlıyor..."
            current_task["error"] = None

        def run_render():
            global current_task
            try:
                from video_renderer import render_project

                # Video dosyalarını topla
                video_paths = []
                expected_count = project_data.get("expected_count", 9)
                for i in range(1, expected_count + 1):
                    video_path = os.path.join(project_dir, f"video_{i}.mp4")
                    if os.path.exists(video_path):
                        video_paths.append(video_path)

                if not video_paths:
                    with task_lock:
                        current_task["error"] = "Video bulunamadı"
                        current_task["running"] = False
                    return

                voice_text = project_data.get("voice", {}).get("text", "")

                result = render_project(
                    project_dir=project_dir,
                    video_paths=video_paths,
                    voice_text=voice_text,
                    voice_style="friendly",
                    words_per_subtitle=2,
                    progress_callback=update_progress
                )

                with task_lock:
                    current_task["result"] = result
                    current_task["running"] = False

            except Exception as e:
                logger.error(f"Render hatası: {e}")
                import traceback
                traceback.print_exc()
                with task_lock:
                    current_task["error"] = str(e)
                    current_task["running"] = False

        import threading
        thread = threading.Thread(target=run_render)
        thread.start()

        return jsonify({"success": True, "message": "Render başlatıldı"})

    except Exception as e:
        with task_lock:
            current_task["running"] = False
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    os.makedirs(config.LOGS_DIR, exist_ok=True)

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║          AUTO SHORTS IMAGE GENERATOR                       ║
║                                                           ║
║  Web arayüzü: http://localhost:{config.FLASK_PORT}                     ║
║  Projeler: {config.PROJECTS_DIR}
╚═══════════════════════════════════════════════════════════╝
    """)

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True
    )
