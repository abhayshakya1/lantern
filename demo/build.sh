#!/usr/bin/env bash
# Mux each scene's video with its narration (padding whichever is shorter), then concat to the final HD mp4.
# Run from demo/: bash build.sh
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p out/seg
LIST=out/concat.txt
: > "$LIST"

probe() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
# puppeteer's webm has no duration header: take the last packet timestamp
probe_webm() { ffprobe -v error -select_streams v -show_entries packet=pts_time -of csv=p=0 "$1" | tail -1; }

for webm in out/raw/*.webm; do
  id=$(basename "$webm" .webm)
  mp3="out/audio/$id.mp3"
  seg="out/seg/$id.mp4"
  if [ ! -f "$mp3" ]; then echo "missing narration for $id"; exit 1; fi
  vd=$(probe_webm "$webm"); ad=$(probe "$mp3")
  # hold the last frame or pad silence so narration and footage end together, plus a 0.7s breath
  max=$(python3 -c "print(max($vd,$ad)+0.7)")
  vpad=$(python3 -c "print(max(0.0,$ad-$vd)+0.7)")
  ffmpeg -y -v error -i "$webm" -i "$mp3" \
    -filter_complex "[0:v]fps=30,scale=1920:1080:flags=lanczos,tpad=stop_mode=clone:stop_duration=$vpad,format=yuv420p[v];[1:a]apad[a]" \
    -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -t "$max" "$seg" || exit 1
  echo "file 'seg/$id.mp4'" >> "$LIST"
  echo "$id: video ${vd%s}s audio ${ad}s -> ${max}s"
done

ffmpeg -y -v error -f concat -safe 0 -i "$LIST" -c copy out/lantern-demo.mp4 || exit 1
echo "final: $(probe out/lantern-demo.mp4)s -> $(cd out && pwd)/lantern-demo.mp4"
