import { describe, it, expect } from 'vitest';
import { md5 } from '../utils/md5';

describe('md5', () => {
  it('matches RFC 1321 test vectors', () => {
    expect(md5('')).toBe('d41d8cd98f00b204e9800998ecf8427e');
    expect(md5('a')).toBe('0cc175b9c0f1b6a831c399e269772661');
    expect(md5('abc')).toBe('900150983cd24fb0d6963f7d28e17f72');
    expect(md5('message digest')).toBe('f96b697d7cb7938d525a2f31aaf161d0');
    expect(md5('abcdefghijklmnopqrstuvwxyz')).toBe('c3fcd3d76192e4007dfb496cca67e13b');
    expect(md5('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')).toBe(
      'd174ab98d277d9f5a5611c2c9f419d9f'
    );
    expect(
      md5('12345678901234567890123456789012345678901234567890123456789012345678901234567890')
    ).toBe('57edf4a22be3c955ac49da2e2107b67a');
  });

  it('handles multi-block input and unicode', () => {
    expect(md5('a'.repeat(55))).toBe('ef1772b6dff9a122358552954ad0df65');
    expect(md5('a'.repeat(56))).toBe('3b0c8ac703f828b04c6c197006d17218');
    expect(md5('a'.repeat(64))).toBe('014842d480b571495a4a0363793f7367');
    // UTF-8 bytes must match Python's hashlib.md5(s.encode('utf-8')).
    expect(md5('naïve café ☕')).toBe('ead149e8ab3ebc8c0dfbac046470cae6');
  });
});
