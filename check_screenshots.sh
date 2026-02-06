#!/bin/bash
# check_screenshots.sh

echo "📊 Revisando screenshots generados..."
echo "======================================"

DEBUG_DIR="./debug"
if [ -d "$DEBUG_DIR/screenshots" ]; then
    echo "Screenshots encontrados:"
    ls -lh "$DEBUG_DIR/screenshots/" | head -20

    echo ""
    echo "Último screenshot:"
    LATEST=$(ls -t "$DEBUG_DIR/screenshots/" | head -1)
    echo "  $LATEST"

    # Si tienes display, puedes abrirlo:
    # xdg-open "$DEBUG_DIR/screenshots/$LATEST" 2>/dev/null || true
else
    echo "❌ No hay screenshots en $DEBUG_DIR/screenshots/"
fi

echo ""
echo "HTML guardados:"
ls -lh "$DEBUG_DIR/html/" 2>/dev/null | head -10 || echo "No hay HTML"