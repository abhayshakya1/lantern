// Generate the voiceover: one ElevenLabs mp3 per scene. Run from demo/: node tts.mjs
// Reads ELEVENLABS_API_KEY from ../.env (git-ignored); skips scenes whose mp3 already exists.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { VOICE_ID, scenes } from './scenes.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(DIR, 'out', 'audio');
fs.mkdirSync(OUT, { recursive: true });

const env = fs.readFileSync(path.join(DIR, '..', '.env'), 'utf8');
const key = env.match(/^ELEVENLABS_API_KEY=(.+)$/m)?.[1]?.trim();
if (!key) { console.error('no ELEVENLABS_API_KEY in .env'); process.exit(1); }

for (const s of scenes) {
  const dest = path.join(OUT, `${s.id}.mp3`);
  if (fs.existsSync(dest)) { console.log(`${s.id}: exists`); continue; }
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}?output_format=mp3_44100_128`, {
    method: 'POST',
    headers: { 'xi-api-key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: s.narration,
      model_id: 'eleven_multilingual_v2',
      voice_settings: { stability: 0.55, similarity_boost: 0.75, style: 0.25 },
    }),
  });
  if (!r.ok) { console.error(`${s.id}: HTTP ${r.status} ${await r.text()}`); process.exit(1); }
  fs.writeFileSync(dest, Buffer.from(await r.arrayBuffer()));
  console.log(`${s.id}: ${(fs.statSync(dest).size / 1024).toFixed(0)} KB`);
}
