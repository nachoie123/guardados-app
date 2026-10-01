#!/bin/bash
# dist/Guardados.app -> dist/Guardados.dmg: ventana con fondo (arrastrar a Applications + "Open Anyway").
# Después de ./build.sh. Mismo método que IG Cleaning: bounds dos veces o el Finder no guarda el tamaño.
set -e
cd "$(dirname "$0")/.."
ST=build/dmg_stage; VOL=Guardados
hdiutil detach "/Volumes/$VOL" -force -quiet 2>/dev/null || true
rm -rf $ST build/rw.dmg; mkdir -p $ST/.background
python3 - <<'EOF'
from PIL import Image, ImageDraw, ImageFont
W, H, S = 660, 520, 2
im = Image.new("RGB", (W*S, H*S), "#FAFAF9"); d = ImageDraw.Draw(im)
F = lambda sz, b=False: ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", sz*S, index=1 if b else 0)
d.line([(255*S, 150*S), (405*S, 150*S)], fill="#C2410C", width=6*S)
d.polygon([(405*S, 135*S), (430*S, 150*S), (405*S, 165*S)], fill="#C2410C")
d.text((W*S//2, 40*S), "1 · Drag Guardados into Applications", font=F(20, True), fill="#1C1917", anchor="mm")
y = 270
d.rounded_rectangle([(30*S, y*S), (630*S, (y+225)*S)], radius=16*S, fill="#FFF7ED", outline="#C2410C", width=2*S)
d.text((52*S, (y+22)*S), "2 · The first time, macOS stops it (that's normal)", font=F(18, True), fill="#1C1917")
lines = ["It says Apple could not verify \"Guardados\".",
         "The app isn't notarized by Apple ($99/year), like most indie apps.", "",
         "Click \"Done\", then:",
         "System Settings  ›  Privacy & Security  ›",
         "scroll to the bottom  ›  \"Open Anyway\"  ›  confirm.", "",
         "Only once. After that it opens with a double-click."]
for i, l in enumerate(lines):
    d.text((52*S, (y+58+i*20)*S), l, font=F(14, i in (4, 5)), fill="#1C1917" if i in (4, 5) else "#57534E")
im.save("build/bg@2x.png"); im.resize((W, H), Image.LANCZOS).save("build/bg.png")
EOF
tiffutil -cathidpicheck build/bg.png build/bg@2x.png -out $ST/.background/bg.tiff >/dev/null
ditto dist/Guardados.app $ST/Guardados.app
ln -s /Applications $ST/Applications
hdiutil create -srcfolder $ST -volname $VOL -fs HFS+ -format UDRW -size 200m build/rw.dmg >/dev/null
hdiutil attach build/rw.dmg -noautoopen -quiet; sleep 2
osascript <<EOF
tell application "Finder"
  tell disk "$VOL"
    open
    delay 1
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set vo to the icon view options of container window
    set arrangement of vo to not arranged
    set icon size of vo to 96
    set text size of vo to 13
    set background picture of vo to file ".background:bg.tiff"
    set position of item "Guardados.app" of container window to {170, 150}
    set position of item "Applications" of container window to {500, 150}
    set the bounds of container window to {200, 120, 860, 700}
    delay 1
    set the bounds of container window to {200, 120, 860, 700}
    update without registering applications
    delay 3
    close
  end tell
end tell
EOF
sleep 2; sync; hdiutil detach "/Volumes/$VOL" -quiet; rm -f dist/Guardados.dmg
hdiutil convert build/rw.dmg -format UDZO -imagekey zlib-level=9 -o dist/Guardados.dmg >/dev/null; rm build/rw.dmg
ls -la dist/Guardados.dmg
