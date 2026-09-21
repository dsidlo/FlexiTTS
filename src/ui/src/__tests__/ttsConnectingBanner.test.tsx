import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

const mockConnectivity = {
  online: false,
  retrying: false,
  nextRetryInMs: null,
  attempt: 0,
  retryNow: vi.fn(),
  connecting: true,
};

vi.mock('./hooks', async () => {
  const actual = await vi.importActual('./hooks');
  return { ...actual, useTtsConnectivity: () => mockUseTtsConnectivity() };
});

let connectivityState = { ...mockConnectivity };
function mockUseTtsConnectivity() {
  return connectivityState;
}

// Minimal harness: renders the banner logic extracted as in App
import { TtsConnectingBanner } from '../components/TtsConnectingBanner';

describe('TTS connecting banner (startup grace phase)', () => {
  beforeEach(() => {
    connectivityState = { ...mockConnectivity };
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('shows green connecting bar during connecting phase', () => {
    render(<TtsConnectingBanner connecting={true} online={false} />);
    expect(screen.getByTestId('tts-connecting-banner')).toBeTruthy();
    expect(screen.getByText(/Connecting to TTS service/)).toBeTruthy();
  });

  it('hides connecting bar once online', () => {
    render(<TtsConnectingBanner connecting={false} online={true} />);
    expect(screen.queryByTestId('tts-connecting-banner')).toBeNull();
  });

  it('hides connecting bar after grace expires (banner handover)', () => {
    render(<TtsConnectingBanner connecting={false} online={false} />);
    expect(screen.queryByTestId('tts-connecting-banner')).toBeNull();
    expect(screen.queryByTestId('tts-offline-banner')).toBeNull();
  });
});
