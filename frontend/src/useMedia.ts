import { useCallback, useRef, useState } from "react";

// Inbound binary media tags (must match app/main.py).
const MEDIA_AUDIO = 0x01;
const MEDIA_VIDEO = 0x02;

const MIC_TARGET_RATE = 16000; // Live API expects 16 kHz PCM16 in
const AGENT_AUDIO_RATE = 24000; // Live API sends 24 kHz PCM16 out
const FRAME_INTERVAL_MS = 500; // ~2 fps camera frames — snappier document reads

/**
 * Device pipeline (venue-verified, not unit-tested — needs a real mic/camera):
 * - captures mic audio, downsamples to 16 kHz PCM16, sends as tagged binary
 * - grabs one camera JPEG per second, sends as tagged binary
 * - plays agent audio chunks (24 kHz PCM16) back through Web Audio, gap-free
 */
export function useMedia(sendBinary: (b: Uint8Array) => void) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cleanup = useRef<() => void>(() => {});
  const playCtxRef = useRef<AudioContext | null>(null);
  const nextStartRef = useRef(0);
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());

  // Turn-taking lives on the proxy: it runs an energy VAD over this mic stream and
  // brackets each utterance with activity_start/end (Live auto-VAD is off). So the
  // client streams the mic CONTINUOUSLY and never gates it — gating would hide the
  // user's barge-in onset from the proxy VAD and the agent could never be paused.

  // Playback context MUST be created/resumed from a user gesture (the Start tap),
  // or Chrome's autoplay policy leaves it "suspended": currentTime stays 0, every
  // scheduled chunk lands in the past, and the agent is silent. Resume defensively.
  //
  // Create it at the DEVICE's default rate (no forced sampleRate). Forcing
  // sampleRate:24000 throws on some browsers/OS, and that throw is swallowed by
  // the socket's onmessage catch → all agent audio silently dies. Each 24 kHz
  // AudioBuffer carries its own rate and Web Audio resamples it on playback.
  const ensurePlayCtx = useCallback((): AudioContext => {
    if (!playCtxRef.current) {
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      playCtxRef.current = new Ctor();
      nextStartRef.current = playCtxRef.current.currentTime;
    }
    if (playCtxRef.current.state === "suspended") void playCtxRef.current.resume();
    return playCtxRef.current;
  }, []);

  const tagged = (tag: number, payload: Uint8Array): Uint8Array => {
    const out = new Uint8Array(payload.length + 1);
    out[0] = tag;
    out.set(payload, 1);
    return out;
  };

  const downsampleToPCM16 = (input: Float32Array, inRate: number): Uint8Array => {
    const ratio = inRate / MIC_TARGET_RATE;
    const outLen = Math.floor(input.length / ratio);
    const buf = new ArrayBuffer(outLen * 2);
    const view = new DataView(buf);
    for (let i = 0; i < outLen; i++) {
      // average the window to avoid aliasing on naive decimation
      const start = Math.floor(i * ratio);
      const end = Math.min(input.length, Math.floor((i + 1) * ratio));
      let sum = 0;
      for (let j = start; j < end; j++) sum += input[j];
      const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
      view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    }
    return new Uint8Array(buf);
  };

  const start = useCallback(async () => {
    if (running) return;
    setError(null);
    try {
      ensurePlayCtx(); // unlock agent audio while we still hold the Start gesture
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        video: { facingMode: "environment" },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }

      // --- mic -> 16 kHz PCM16 ---
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const proc = audioCtx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = (e) => {
        // Stream every frame; the proxy VAD segments turns and detects barge-in.
        const pcm = downsampleToPCM16(e.inputBuffer.getChannelData(0), audioCtx.sampleRate);
        sendBinary(tagged(MEDIA_AUDIO, pcm));
      };
      source.connect(proc);
      proc.connect(audioCtx.destination);

      // --- camera -> ~1 fps JPEG ---
      const canvas = document.createElement("canvas");
      const frameTimer = window.setInterval(() => {
        const v = videoRef.current;
        if (!v || !v.videoWidth) return;
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        canvas.getContext("2d")?.drawImage(v, 0, 0);
        canvas.toBlob(
          async (blob) => {
            if (!blob) return;
            const bytes = new Uint8Array(await blob.arrayBuffer());
            sendBinary(tagged(MEDIA_VIDEO, bytes));
          },
          "image/jpeg",
          0.7,
        );
      }, FRAME_INTERVAL_MS);

      setRunning(true);
      cleanup.current = () => {
        window.clearInterval(frameTimer);
        proc.disconnect();
        source.disconnect();
        audioCtx.close().catch(() => {});
        stream.getTracks().forEach((t) => t.stop());
        setRunning(false);
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "media error");
    }
  }, [running, sendBinary]);

  const stop = useCallback(() => cleanup.current(), []);

  const playChunk = useCallback(
    (base64Pcm: string) => {
      const ctx = ensurePlayCtx();
      const bin = atob(base64Pcm);
    const n = bin.length / 2;
    const buffer = ctx.createBuffer(1, n, AGENT_AUDIO_RATE);
    const ch = buffer.getChannelData(0);
    for (let i = 0; i < n; i++) {
      const lo = bin.charCodeAt(i * 2);
      const hi = bin.charCodeAt(i * 2 + 1);
      let val = (hi << 8) | lo;
      if (val >= 0x8000) val -= 0x10000;
      ch[i] = val / 0x8000;
    }
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);
      const startAt = Math.max(ctx.currentTime, nextStartRef.current);
      src.start(startAt);
      nextStartRef.current = startAt + buffer.duration;
      activeSourcesRef.current.add(src);
      src.onended = () => activeSourcesRef.current.delete(src);
    },
    [ensurePlayCtx],
  );

  // Barge-in ("interrupted" from the proxy): stop any queued agent speech at once
  // so it doesn't keep talking over the user — this is the visible "pause".
  const flushAgentAudio = useCallback(() => {
    for (const s of activeSourcesRef.current) {
      try {
        s.onended = null;
        s.stop();
      } catch {
        // already stopped
      }
    }
    activeSourcesRef.current.clear();
    if (playCtxRef.current) nextStartRef.current = playCtxRef.current.currentTime;
  }, []);

  return { videoRef, start, stop, running, error, playChunk, flushAgentAudio };
}
