/**
 * Audio utilities for PCM16 encoding/decoding at 24kHz.
 * OpenAI Realtime API expects PCM16 (signed 16-bit little-endian), 24kHz, mono.
 */

const TARGET_SAMPLE_RATE = 24000

/**
 * Convert Float32 audio samples to PCM16 Int16Array.
 */
export function float32ToPcm16(float32: Float32Array): Int16Array {
  const pcm16 = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return pcm16
}

/**
 * Convert PCM16 Int16Array back to Float32Array for playback.
 */
export function pcm16ToFloat32(pcm16: Int16Array): Float32Array {
  const float32 = new Float32Array(pcm16.length)
  for (let i = 0; i < pcm16.length; i++) {
    float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7fff)
  }
  return float32
}

/**
 * Downsample audio from sourceSampleRate to 24kHz using linear interpolation.
 */
export function downsampleTo24k(buffer: Float32Array, sourceSampleRate: number): Float32Array {
  if (sourceSampleRate === TARGET_SAMPLE_RATE) return buffer

  const ratio = sourceSampleRate / TARGET_SAMPLE_RATE
  const newLength = Math.floor(buffer.length / ratio)
  const result = new Float32Array(newLength)

  for (let i = 0; i < newLength; i++) {
    const srcIdx = i * ratio
    const low = Math.floor(srcIdx)
    const high = Math.min(low + 1, buffer.length - 1)
    const frac = srcIdx - low
    result[i] = buffer[low] * (1 - frac) + buffer[high] * frac
  }

  return result
}

/**
 * Encode PCM16 bytes to base64 string.
 */
export function pcm16ToBase64(pcm16: Int16Array): string {
  const bytes = new Uint8Array(pcm16.buffer, pcm16.byteOffset, pcm16.byteLength)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

/**
 * Decode base64 string to PCM16 Int16Array.
 */
export function base64ToPcm16(base64: string): Int16Array {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Int16Array(bytes.buffer)
}

/**
 * Create an AudioContext-based PCM16 player for streaming playback.
 */
export class Pcm16Player {
  private ctx: AudioContext
  private nextStartTime = 0
  private playing = false

  constructor() {
    this.ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE })
  }

  /** Queue a base64-encoded PCM16 chunk for gapless playback. */
  play(base64Audio: string) {
    const pcm16 = base64ToPcm16(base64Audio)
    const float32 = pcm16ToFloat32(pcm16)

    const buffer = this.ctx.createBuffer(1, float32.length, TARGET_SAMPLE_RATE)
    buffer.getChannelData(0).set(float32)

    const source = this.ctx.createBufferSource()
    source.buffer = buffer
    source.connect(this.ctx.destination)

    const now = this.ctx.currentTime
    const startTime = Math.max(now, this.nextStartTime)
    source.start(startTime)
    this.nextStartTime = startTime + buffer.duration
    this.playing = true

    source.onended = () => {
      if (this.ctx.currentTime >= this.nextStartTime - 0.01) {
        this.playing = false
      }
    }
  }

  /** Interrupt current playback (e.g., when user starts speaking). */
  interrupt() {
    this.nextStartTime = 0
    this.playing = false
    // Close and recreate context to stop all queued audio
    this.ctx.close()
    this.ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE })
  }

  get isPlaying(): boolean {
    return this.playing && this.ctx.currentTime < this.nextStartTime
  }

  /** Resume AudioContext (required after user gesture on some browsers). */
  async resume() {
    if (this.ctx.state === 'suspended') {
      await this.ctx.resume()
    }
  }

  close() {
    this.ctx.close()
  }
}
