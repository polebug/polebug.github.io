#!/bin/zsh
# Rebuild companion-house.blend from scratch, stage by stage. Usage: scripts/build_all.sh
# build_character.py (old in-scene owner) is retired: the owner now lives in characters/owner-character-v*.blend.
set -e
cd "${0:A:h}/.."
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
$B -b --factory-startup --python scripts/build_whitebox.py      2>&1 | grep -E "SAVED|Error|Traceback" || true
for s in build_architecture build_interior_f1 build_interior_f2 build_interior_f3 build_environment cull_far_hidden build_materials build_materials_real; do
  $B -b companion-house.blend --python scripts/$s.py 2>&1 | grep -E "SAVED|MTN_|FOREST|FOOTHILLS|CULL|Error|Traceback|line [0-9]" || true
done
