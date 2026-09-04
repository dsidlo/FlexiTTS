/**
 * Minimal, dependency-free MD5 (hex digest) implementation.
 *
 * Node/Electron provide MD5 via `crypto`, but the renderer runs in jsdom during
 * tests where `crypto.subtle` is unavailable and synchronous hashing is simplest.
 * This operates on a UTF-8 byte array and returns the lowercase hex digest, which
 * exactly matches Python's `hashlib.md5(s.encode("utf-8")).hexdigest()`.
 */

const S: number[] = [
  7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
  5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
  4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
  6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];

// K[i] = floor(abs(sin(i + 1)) * 2^32), precomputed per RFC 1321.
const K: number[] = (() => {
  const table = new Array<number>(64);
  for (let i = 0; i < 64; i += 1) {
    table[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296);
  }
  return table;
})();

/** Rotate-left a 32-bit integer. */
const rotl = (x: number, c: number): number => ((x << c) | (x >>> (32 - c))) | 0;

/** Encode a JS string as UTF-8 bytes. */
export const utf8Bytes = (input: string): Uint8Array => {
  if (typeof TextEncoder !== 'undefined') {
    return new TextEncoder().encode(input);
  }
  // Fallback (unescape/encodeURI trick) for very old environments.
  const encoded = unescape(encodeURIComponent(input));
  const bytes = new Uint8Array(encoded.length);
  for (let i = 0; i < encoded.length; i += 1) {
    bytes[i] = encoded.charCodeAt(i);
  }
  return bytes;
};

const toHexLE = (value: number): string => {
  let out = '';
  for (let i = 0; i < 4; i += 1) {
    const byte = (value >>> (i * 8)) & 0xff;
    out += byte.toString(16).padStart(2, '0');
  }
  return out;
};

/**
 * Compute the MD5 hex digest of a string (UTF-8), matching
 * Python's `hashlib.md5(s.encode('utf-8')).hexdigest()`.
 */
export const md5 = (input: string): string => {
  const message = utf8Bytes(input);
  const origLenBits = message.length * 8;

  // Padding: 0x80 then zeros until length ≡ 56 (mod 64), then 64-bit length.
  const withOne = message.length + 1;
  const paddedLen = ((withOne + 8 + 63) >> 6) << 6; // multiple of 64 with room for length
  const padded = new Uint8Array(paddedLen);
  padded.set(message);
  padded[message.length] = 0x80;

  // 64-bit little-endian bit length (JS safe up to 2^53 bits, plenty for dialog text).
  let remaining = origLenBits;
  for (let i = 0; i < 8; i += 1) {
    padded[paddedLen - 8 + i] = remaining & 0xff;
    remaining = Math.floor(remaining / 256);
  }

  let a0 = 0x67452301;
  let b0 = 0xefcdab89;
  let c0 = 0x98badcfe;
  let d0 = 0x10325476;

  const M = new Int32Array(16);
  for (let offset = 0; offset < paddedLen; offset += 64) {
    for (let i = 0; i < 16; i += 1) {
      const j = offset + i * 4;
      M[i] =
        padded[j] |
        (padded[j + 1] << 8) |
        (padded[j + 2] << 16) |
        (padded[j + 3] << 24);
    }

    let A = a0;
    let B = b0;
    let C = c0;
    let D = d0;

    for (let i = 0; i < 64; i += 1) {
      let F: number;
      let g: number;
      if (i < 16) {
        F = (B & C) | (~B & D);
        g = i;
      } else if (i < 32) {
        F = (D & B) | (~D & C);
        g = (5 * i + 1) % 16;
      } else if (i < 48) {
        F = B ^ C ^ D;
        g = (3 * i + 5) % 16;
      } else {
        F = C ^ (B | ~D);
        g = (7 * i) % 16;
      }
      const tmp = D;
      D = C;
      C = B;
      B = (B + rotl((A + F + K[i] + M[g]) | 0, S[i])) | 0;
      A = tmp;
    }

    a0 = (a0 + A) | 0;
    b0 = (b0 + B) | 0;
    c0 = (c0 + C) | 0;
    d0 = (d0 + D) | 0;
  }

  return toHexLE(a0) + toHexLE(b0) + toHexLE(c0) + toHexLE(d0);
};
