#!/usr/bin/env bash
# Renders wasc/brand/icon.svg into the 1024x1024 app icons used by the iOS app and watch app.
# Requires ImageMagick 7 (`magick`). Output is opaque RGB (App Store rejects alpha in app icons).
set -euo pipefail
cd "$(dirname "$0")/../.."
for out in \
  Bitwarden/Application/Support/Assets.xcassets/AppIcon.appiconset/Icon-1024.png \
  BitwardenWatchApp/Assets.xcassets/AppIcon.appiconset/Icon-1024.png; do
  magick -background '#111111' wasc/brand/icon.svg -resize 1024x1024 -flatten -alpha off \
    -define png:color-type=2 -strip "$out"
  echo "wrote $out"
done
