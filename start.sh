#!/bin/bash
# Auto Shorts Image Generator - Başlatıcı Script

cd "$(dirname "$0")"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          AUTO SHORTS IMAGE GENERATOR                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ Python bulunamadı!"
    exit 1
fi

# Check dependencies
echo "📦 Bağımlılıklar kontrol ediliyor..."
$PYTHON -c "import flask, selenium" 2>/dev/null || {
    echo "📦 Bağımlılıklar yükleniyor..."
    pip install -q flask selenium webdriver-manager
}

echo ""
echo "🌐 Web sunucusu başlatılıyor..."
echo "   URL: http://localhost:5000"
echo ""
echo "   Durdurmak için Ctrl+C"
echo ""

$PYTHON app.py
