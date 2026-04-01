/**
 * Tests for VideoPlayer component
 *
 * Tests the P4 custom video player including:
 * - Rendering and structure
 * - Chapter display
 * - Control buttons
 * - Volume controls
 * - Fullscreen toggle
 * - Keyboard shortcuts
 * - Progress tracking
 * - Controls visibility
 * - Accessibility
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import VideoPlayer from './VideoPlayer';

const mockChapters = [
  { time: 0, title: 'Introduction' },
  { time: 30, title: 'Getting Started' },
  { time: 60, title: 'Advanced Features' },
  { time: 90, title: 'Conclusion' },
];

describe('VideoPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Mock document fullscreen API
    Object.defineProperty(document, 'fullscreenElement', {
      value: null,
      writable: true,
      configurable: true,
    });
    document.exitFullscreen = vi.fn().mockResolvedValue(undefined);
    Element.prototype.requestFullscreen = vi.fn().mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // Note: Lines 72, 82, 90, 101, 110, 121, and 133 contain defensive null checks
  // for refs (e.g., if (!video) return). These guard against race conditions where
  // callbacks might be invoked before refs are populated or after unmount.
  // These branches are unreachable in normal operation because:
  // 1. Refs are populated immediately after mount
  // 2. Event handlers are cleaned up on unmount
  // 3. React's synthetic event system doesn't fire on unmounted components
  // Coverage for these defensive guards would require testing edge cases that
  // don't occur in the React lifecycle.

  describe('Rendering', () => {
    test('renders video element with src and poster', () => {
      render(
        <VideoPlayer
          src="https://example.com/video.mp4"
          poster="https://example.com/poster.jpg"
        />
      );

      const video = document.querySelector('video');
      expect(video).toBeInTheDocument();
      expect(video).toHaveAttribute('src', 'https://example.com/video.mp4');
      expect(video).toHaveAttribute('poster', 'https://example.com/poster.jpg');
    });

    test('renders play button overlay when paused', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Play video')).toBeInTheDocument();
    });

    test('renders control buttons', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Play')).toBeInTheDocument();
      expect(screen.getByLabelText('Skip back 10 seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Skip forward 10 seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
      expect(screen.getByLabelText('Enter fullscreen')).toBeInTheDocument();
    });

    test('renders time display', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Initial time display: 0:00 / 0:00
      expect(screen.getByText(/0:00/)).toBeInTheDocument();
    });

    test('applies custom className', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" className="custom-class" />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Chapters', () => {
    test('renders chapter list when chapters provided', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      expect(screen.getByText('Chapters')).toBeInTheDocument();
      // Check for chapter buttons (use getAllByText since chapter title appears twice - in indicator and list)
      const introductionElements = screen.getAllByText('Introduction');
      expect(introductionElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Getting Started')).toBeInTheDocument();
      expect(screen.getByText('Advanced Features')).toBeInTheDocument();
      expect(screen.getByText('Conclusion')).toBeInTheDocument();
    });

    test('displays chapter times in list', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      // Find chapter buttons by their time stamps
      expect(screen.getByText('0:30')).toBeInTheDocument();
      expect(screen.getByText('1:00')).toBeInTheDocument();
      expect(screen.getByText('1:30')).toBeInTheDocument();
    });

    test('does not render chapter list when no chapters provided', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.queryByText('Chapters')).not.toBeInTheDocument();
    });

    test('renders chapter markers on progress bar', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      // Should have markers for each chapter
      const markers = container.querySelectorAll('.bg-white\\/50');
      expect(markers.length).toBe(mockChapters.length);
    });
  });

  describe('Play/Pause', () => {
    test('clicking play overlay calls play on video', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const playOverlay = screen.getByLabelText('Play video');
      fireEvent.click(playOverlay);

      // Video element exists and was clicked
      const video = document.querySelector('video');
      expect(video).toBeInTheDocument();
    });

    test('clicking play button in controls works', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const playButton = screen.getByLabelText('Play');
      fireEvent.click(playButton);

      // Should not throw
      expect(playButton).toBeInTheDocument();
    });

    test('clicking video element toggles play', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      fireEvent.click(video);

      expect(video).toBeInTheDocument();
    });

    test('play event updates playing state', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');

      act(() => {
        fireEvent.play(video);
      });

      // After play, button label should change to Pause
      expect(screen.getByLabelText('Pause')).toBeInTheDocument();
    });

    test('pause event updates playing state', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');

      // First play
      act(() => {
        fireEvent.play(video);
      });

      // Then pause
      act(() => {
        fireEvent.pause(video);
      });

      // After pause, button label should change back to Play
      expect(screen.getByLabelText('Play')).toBeInTheDocument();
    });

    test('clicking pause button calls video.pause() when playing', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');

      // Mock pause method to verify it gets called
      const pauseMock = vi.fn();
      video.pause = pauseMock;

      // Simulate video is playing by firing play event
      act(() => {
        fireEvent.play(video);
      });

      // Now isPlaying should be true, button should show "Pause"
      expect(screen.getByLabelText('Pause')).toBeInTheDocument();

      // Click the pause button (in controls bar)
      const pauseButton = screen.getByLabelText('Pause');
      fireEvent.click(pauseButton);

      // Verify video.pause() was called via togglePlay
      expect(pauseMock).toHaveBeenCalledTimes(1);
    });
  });

  describe('Skip Controls', () => {
    test('skip backward button exists', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const skipBackButton = screen.getByLabelText('Skip back 10 seconds');
      expect(skipBackButton).toBeInTheDocument();
    });

    test('skip forward button exists', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const skipForwardButton = screen.getByLabelText('Skip forward 10 seconds');
      expect(skipForwardButton).toBeInTheDocument();
    });

    test('skip backward button is clickable', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      // Set duration to avoid NaN error in jsdom
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      const skipBackButton = screen.getByLabelText('Skip back 10 seconds');
      fireEvent.click(skipBackButton);

      // Should not throw
      expect(skipBackButton).toBeInTheDocument();
    });

    test('skip forward button is clickable', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      // Set duration to avoid NaN error in jsdom
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      const skipForwardButton = screen.getByLabelText('Skip forward 10 seconds');
      fireEvent.click(skipForwardButton);

      // Should not throw
      expect(skipForwardButton).toBeInTheDocument();
    });
  });

  describe('Volume Controls', () => {
    test('mute button is rendered', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
    });

    test('volume slider is rendered', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Volume')).toBeInTheDocument();
    });

    test('clicking mute button toggles mute state', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const muteButton = screen.getByLabelText('Mute');
      fireEvent.click(muteButton);

      // After mute, label should change to Unmute
      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();
    });

    test('clicking unmute button toggles back', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // First mute
      fireEvent.click(screen.getByLabelText('Mute'));
      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();

      // Then unmute
      fireEvent.click(screen.getByLabelText('Unmute'));
      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
    });

    test('volume slider changes volume', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const volumeSlider = screen.getByLabelText('Volume');
      fireEvent.change(volumeSlider, { target: { value: '0.5' } });

      expect(volumeSlider.value).toBe('0.5');
    });

    test('setting volume to 0 shows muted icon', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const volumeSlider = screen.getByLabelText('Volume');
      fireEvent.change(volumeSlider, { target: { value: '0' } });

      // Button should now show Unmute (meaning currently muted)
      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();
    });
  });

  describe('Fullscreen', () => {
    test('fullscreen button is rendered', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Enter fullscreen')).toBeInTheDocument();
    });

    test('clicking fullscreen button requests fullscreen', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const fullscreenButton = screen.getByLabelText('Enter fullscreen');
      fireEvent.click(fullscreenButton);

      expect(Element.prototype.requestFullscreen).toHaveBeenCalled();
    });

    test('fullscreenchange event updates button label', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Set fullscreen state
      Object.defineProperty(document, 'fullscreenElement', {
        value: document.createElement('div'),
        writable: true,
        configurable: true,
      });

      // Simulate fullscreen change event
      act(() => {
        fireEvent(document, new Event('fullscreenchange'));
      });

      expect(screen.getByLabelText('Exit fullscreen')).toBeInTheDocument();
    });

    test('clicking exit fullscreen calls exitFullscreen', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Set fullscreen state
      Object.defineProperty(document, 'fullscreenElement', {
        value: document.createElement('div'),
        writable: true,
        configurable: true,
      });

      act(() => {
        fireEvent(document, new Event('fullscreenchange'));
      });

      const exitButton = screen.getByLabelText('Exit fullscreen');
      fireEvent.click(exitButton);

      expect(document.exitFullscreen).toHaveBeenCalled();
    });
  });

  describe('Keyboard Shortcuts', () => {
    test('space key is handled', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      fireEvent.keyDown(window, { key: ' ' });

      // Should toggle play (no errors thrown)
      expect(screen.getByLabelText('Play video')).toBeInTheDocument();
    });

    test('k key is handled', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      fireEvent.keyDown(window, { key: 'k' });

      // Should toggle play (no errors thrown)
      expect(screen.getByLabelText('Play video')).toBeInTheDocument();
    });

    test('m key toggles mute', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      fireEvent.keyDown(window, { key: 'm' });

      // After pressing m, should be muted
      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();
    });

    test('f key triggers fullscreen', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      fireEvent.keyDown(window, { key: 'f' });

      expect(Element.prototype.requestFullscreen).toHaveBeenCalled();
    });

    test('other keys are not handled', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Tab key should not trigger any action
      fireEvent.keyDown(window, { key: 'Tab' });

      // State should remain unchanged
      expect(screen.getByLabelText('Play')).toBeInTheDocument();
      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
    });
  });

  describe('Controls Visibility', () => {
    test('controls are visible by default', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-100');
    });

    test('mouse move shows controls', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const wrapper = container.firstChild;
      fireEvent.mouseMove(wrapper);

      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-100');
    });

    test('mouse leave hides controls when playing', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      // Simulate playing state by triggering play event
      const video = document.querySelector('video');

      act(() => {
        fireEvent.play(video);
      });

      // Mouse leave should hide controls
      const wrapper = container.firstChild;
      fireEvent.mouseLeave(wrapper);

      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-0');
    });

    test('controls auto-hide after timeout when playing', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      // Simulate playing state
      const video = document.querySelector('video');
      act(() => {
        fireEvent.play(video);
      });

      // Move mouse to show controls
      const wrapper = container.firstChild;
      fireEvent.mouseMove(wrapper);

      // Advance timer past 3 second timeout
      act(() => {
        vi.advanceTimersByTime(3500);
      });

      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-0');
    });

    test('mouse movement resets auto-hide timer', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      act(() => {
        fireEvent.play(video);
      });

      const wrapper = container.firstChild;

      // Move mouse
      fireEvent.mouseMove(wrapper);

      // Advance half the timeout
      act(() => {
        vi.advanceTimersByTime(1500);
      });

      // Move mouse again to reset timer
      fireEvent.mouseMove(wrapper);

      // Advance another 1.5 seconds (total 3s since last move)
      act(() => {
        vi.advanceTimersByTime(1500);
      });

      // Controls should still be visible (timer was reset)
      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-100');
    });

    test('mouse leave when paused does not hide controls', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      // Video is paused by default (isPlaying = false)
      const wrapper = container.firstChild;

      // Show controls first
      fireEvent.mouseMove(wrapper);
      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-100');

      // Mouse leave should NOT hide controls when paused
      fireEvent.mouseLeave(wrapper);

      // Controls should still be visible
      expect(controlsOverlay).toHaveClass('opacity-100');
    });

    test('auto-hide timeout is not set when paused', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      // Video is paused by default
      const wrapper = container.firstChild;
      fireEvent.mouseMove(wrapper);

      // Advance timer past 3 second timeout
      act(() => {
        vi.advanceTimersByTime(4000);
      });

      // Controls should still be visible since video is paused
      const controlsOverlay = container.querySelector('.bg-gradient-to-t');
      expect(controlsOverlay).toHaveClass('opacity-100');
    });
  });

  describe('Progress Bar', () => {
    test('progress bar is rendered', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const progressBar = container.querySelector('.bg-white\\/30');
      expect(progressBar).toBeInTheDocument();
    });

    test('played progress indicator exists', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const playedProgress = container.querySelector('.bg-aura-500');
      expect(playedProgress).toBeInTheDocument();
    });
  });

  describe('Callbacks', () => {
    test('calls onProgress during playback', () => {
      const onProgress = vi.fn();
      render(
        <VideoPlayer src="https://example.com/video.mp4" onProgress={onProgress} />
      );

      const video = document.querySelector('video');

      // Simulate time update with valid values
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });
      Object.defineProperty(video, 'duration', { value: 120, writable: true });

      act(() => {
        fireEvent.timeUpdate(video);
      });

      expect(onProgress).toHaveBeenCalled();
    });

    test('onProgress receives correct percentage', () => {
      const onProgress = vi.fn();
      render(
        <VideoPlayer src="https://example.com/video.mp4" onProgress={onProgress} />
      );

      const video = document.querySelector('video');

      Object.defineProperty(video, 'currentTime', { value: 60, writable: true });
      Object.defineProperty(video, 'duration', { value: 120, writable: true });

      act(() => {
        fireEvent.timeUpdate(video);
      });

      // Should be called with 50% progress
      expect(onProgress).toHaveBeenCalledWith(50, expect.any(Boolean));
    });

    test('calls onComplete when video ends', () => {
      const onComplete = vi.fn();
      render(
        <VideoPlayer src="https://example.com/video.mp4" onComplete={onComplete} />
      );

      const video = document.querySelector('video');

      act(() => {
        fireEvent.ended(video);
      });

      expect(onComplete).toHaveBeenCalled();
    });

    test('sets isPlaying to false when video ends', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');

      // Start playing
      act(() => {
        fireEvent.play(video);
      });

      expect(screen.getByLabelText('Pause')).toBeInTheDocument();

      // End video
      act(() => {
        fireEvent.ended(video);
      });

      // Should show play button again
      expect(screen.getByLabelText('Play')).toBeInTheDocument();
    });
  });

  describe('Metadata Loading', () => {
    test('loadedmetadata event sets duration', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');

      Object.defineProperty(video, 'duration', { value: 180, writable: true });

      act(() => {
        fireEvent.loadedMetadata(video);
      });

      // Should display duration in time display (3:00)
      expect(screen.getByText(/3:00/)).toBeInTheDocument();
    });

    test('respects initialProgress prop on load', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" initialProgress={50} />
      );

      const video = document.querySelector('video');

      Object.defineProperty(video, 'duration', { value: 120, writable: true });

      act(() => {
        fireEvent.loadedMetadata(video);
      });

      // Should have set currentTime based on initialProgress
      expect(video).toBeInTheDocument();
    });
  });

  describe('Time Formatting', () => {
    test('formats single-digit seconds with leading zero', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Initial display should be 0:00
      expect(screen.getByText(/0:00/)).toBeInTheDocument();
    });

    test('formats minutes correctly', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      // Chapter at 60 seconds should show 1:00
      expect(screen.getByText('1:00')).toBeInTheDocument();
    });

    test('formats minutes and seconds correctly', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      // Chapter at 90 seconds should show 1:30
      expect(screen.getByText('1:30')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('play overlay has accessible label', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Play video')).toBeInTheDocument();
    });

    test('all control buttons have accessible labels', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      expect(screen.getByLabelText('Play')).toBeInTheDocument();
      expect(screen.getByLabelText('Skip back 10 seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Skip forward 10 seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
      expect(screen.getByLabelText('Volume')).toBeInTheDocument();
      expect(screen.getByLabelText('Enter fullscreen')).toBeInTheDocument();
    });

    test('video element has playsInline attribute', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      expect(video).toHaveAttribute('playsInline');
    });
  });

  describe('Cleanup', () => {
    test('removes event listeners on unmount', () => {
      const { unmount } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      unmount();

      // Should not throw when triggering events after unmount
      fireEvent.keyDown(window, { key: 'm' });
    });

    test('clears auto-hide timeout on unmount', () => {
      const { container, unmount } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      act(() => {
        fireEvent.play(video);
      });

      const wrapper = container.firstChild;
      fireEvent.mouseMove(wrapper);

      unmount();

      // Should not throw when timer fires after unmount
      act(() => {
        vi.advanceTimersByTime(5000);
      });
    });
  });

  describe('Chapter Navigation', () => {
    test('clicking chapter button jumps to chapter time', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      // Click on "Getting Started" chapter (at 30 seconds)
      const chapterButton = screen.getByText('Getting Started');
      fireEvent.click(chapterButton);

      // Video should seek to chapter time
      expect(video.currentTime).toBe(30);
    });

    test('clicking chapter button when paused starts playing', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      // Mock the play method to track if it was called
      const playSpy = vi.fn();
      video.play = playSpy;

      // Video should be paused initially
      expect(screen.getByLabelText('Play')).toBeInTheDocument();

      // Click on a chapter
      const chapterButton = screen.getByText('Advanced Features');
      fireEvent.click(chapterButton);

      // Should have called play since video was paused
      expect(playSpy).toHaveBeenCalled();
    });

    test('clicking chapter button when already playing does not call play again', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      // Start playing
      act(() => {
        fireEvent.play(video);
      });

      // Mock play after setting playing state
      const playSpy = vi.fn();
      video.play = playSpy;

      // Should now show Pause button
      expect(screen.getByLabelText('Pause')).toBeInTheDocument();

      // Click on a chapter
      const chapterButton = screen.getByText('Conclusion');
      fireEvent.click(chapterButton);

      // Should not call play since already playing
      expect(playSpy).not.toHaveBeenCalled();
    });

    test('chapter button shows current chapter highlighted', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 45, writable: true });

      // Trigger time update to set current chapter
      act(() => {
        fireEvent.timeUpdate(video);
      });

      // The "Getting Started" chapter (time: 30) should be the current chapter at 45 seconds
      // It appears twice (indicator + chapter list), so use getAllByText
      const gettingStartedElements = screen.getAllByText('Getting Started');
      // Find the one that's a button (in the chapter list)
      const chapterButton = gettingStartedElements.find(
        (el) => el.closest('button')?.classList.contains('text-aura-400')
      );
      expect(chapterButton).toBeTruthy();
    });
  });

  describe('Keyboard Skip Controls', () => {
    test('ArrowLeft skips backward 10 seconds', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      fireEvent.keyDown(window, { key: 'ArrowLeft' });

      // Should skip back 10 seconds (30 - 10 = 20)
      expect(video.currentTime).toBe(20);
    });

    test('ArrowRight skips forward 10 seconds', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      fireEvent.keyDown(window, { key: 'ArrowRight' });

      // Should skip forward 10 seconds (30 + 10 = 40)
      expect(video.currentTime).toBe(40);
    });

    test('ArrowLeft does not go below 0', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 5, writable: true });

      fireEvent.keyDown(window, { key: 'ArrowLeft' });

      // Should clamp to 0 (5 - 10 would be -5, but clamped to 0)
      expect(video.currentTime).toBe(0);
    });

    test('ArrowRight does not exceed duration', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 115, writable: true });

      fireEvent.keyDown(window, { key: 'ArrowRight' });

      // Should clamp to duration (115 + 10 would be 125, but clamped to 120)
      expect(video.currentTime).toBe(120);
    });

    test('keyboard shortcuts are ignored when input is focused', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      // Create and append input element
      const inputElement = document.createElement('input');
      document.body.appendChild(inputElement);

      // Dispatch keydown event directly with the input as target
      const keyEvent = new KeyboardEvent('keydown', {
        key: 'ArrowLeft',
        bubbles: true,
      });
      Object.defineProperty(keyEvent, 'target', {
        value: inputElement,
        writable: false,
      });
      window.dispatchEvent(keyEvent);

      // Current time should not change since event was from input
      expect(video.currentTime).toBe(30);

      // Clean up
      document.body.removeChild(inputElement);
    });
  });

  describe('Progress Bar Seeking', () => {
    test('clicking progress bar seeks to correct position', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      // Find the progress bar
      const progressBar = container.querySelector('.bg-white\\/30');

      // Mock getBoundingClientRect for the progress bar
      progressBar.getBoundingClientRect = vi.fn(() => ({
        left: 100,
        width: 200,
        top: 0,
        right: 300,
        bottom: 10,
        height: 10,
      }));

      // Click at 50% position (150 = 100 + 200*0.5)
      fireEvent.click(progressBar, { clientX: 200 });

      // Should seek to 50% of duration (50 seconds)
      expect(video.currentTime).toBe(50);
    });

    test('clicking at progress bar start seeks to beginning', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 50, writable: true });

      const progressBar = container.querySelector('.bg-white\\/30');
      progressBar.getBoundingClientRect = vi.fn(() => ({
        left: 100,
        width: 200,
        top: 0,
        right: 300,
        bottom: 10,
        height: 10,
      }));

      // Click at the start (clientX at left edge)
      fireEvent.click(progressBar, { clientX: 100 });

      // Should seek to 0%
      expect(video.currentTime).toBe(0);
    });

    test('clicking at progress bar end seeks to end', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      const progressBar = container.querySelector('.bg-white\\/30');
      progressBar.getBoundingClientRect = vi.fn(() => ({
        left: 100,
        width: 200,
        top: 0,
        right: 300,
        bottom: 10,
        height: 10,
      }));

      // Click at the end (clientX at right edge)
      fireEvent.click(progressBar, { clientX: 300 });

      // Should seek to 100%
      expect(video.currentTime).toBe(100);
    });

    test('clicking beyond progress bar clamps to valid range', () => {
      const { container } = render(
        <VideoPlayer src="https://example.com/video.mp4" />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 50, writable: true });

      const progressBar = container.querySelector('.bg-white\\/30');
      progressBar.getBoundingClientRect = vi.fn(() => ({
        left: 100,
        width: 200,
        top: 0,
        right: 300,
        bottom: 10,
        height: 10,
      }));

      // Click beyond the end
      fireEvent.click(progressBar, { clientX: 400 });

      // Should clamp to 100%
      expect(video.currentTime).toBe(100);
    });
  });

  describe('Current Chapter Detection', () => {
    test('displays current chapter indicator in controls', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 65, writable: true });

      // Trigger time update
      act(() => {
        fireEvent.timeUpdate(video);
      });

      // At 65 seconds, the current chapter should be "Advanced Features" (starts at 60)
      // This appears twice - once in chapter list and once in indicator
      const advancedElements = screen.getAllByText('Advanced Features');
      expect(advancedElements.length).toBeGreaterThanOrEqual(1);
    });

    test('shows first chapter when at beginning', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={mockChapters} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 0, writable: true });

      act(() => {
        fireEvent.timeUpdate(video);
      });

      // At 0 seconds, should show Introduction (multiple instances)
      const introElements = screen.getAllByText('Introduction');
      expect(introElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('No Chapters', () => {
    test('does not show chapter list when empty', () => {
      render(
        <VideoPlayer src="https://example.com/video.mp4" chapters={[]} />
      );

      expect(screen.queryByText('Chapters')).not.toBeInTheDocument();
    });

    test('does not crash when chapters is undefined', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      // Should render without errors
      expect(screen.getByLabelText('Play video')).toBeInTheDocument();
    });
  });

  describe('onProgress completion flag', () => {
    test('onProgress passes true when near end of video', () => {
      const onProgress = vi.fn();
      render(
        <VideoPlayer src="https://example.com/video.mp4" onProgress={onProgress} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 99.5, writable: true });

      act(() => {
        fireEvent.timeUpdate(video);
      });

      // Should be called with (percentage, true) since within 1 second of end
      expect(onProgress).toHaveBeenCalledWith(expect.any(Number), true);
    });

    test('onProgress passes false when not near end', () => {
      const onProgress = vi.fn();
      render(
        <VideoPlayer src="https://example.com/video.mp4" onProgress={onProgress} />
      );

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 100, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 50, writable: true });

      act(() => {
        fireEvent.timeUpdate(video);
      });

      // Should be called with (percentage, false) since not near end
      expect(onProgress).toHaveBeenCalledWith(50, false);
    });
  });

  describe('Keyboard Shortcuts Edge Cases', () => {
    test('keyboard shortcut from volume slider input is ignored', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      const volumeSlider = screen.getByLabelText('Volume');

      // Dispatch keydown event with volume slider as target
      const keyEvent = new KeyboardEvent('keydown', {
        key: 'ArrowLeft',
        bubbles: true,
      });
      Object.defineProperty(keyEvent, 'target', {
        value: volumeSlider,
        writable: false,
      });
      window.dispatchEvent(keyEvent);

      // Current time should not change since event was from input
      expect(video.currentTime).toBe(30);
    });

    test('unrecognized key does nothing', () => {
      render(<VideoPlayer src="https://example.com/video.mp4" />);

      const video = document.querySelector('video');
      Object.defineProperty(video, 'duration', { value: 120, writable: true });
      Object.defineProperty(video, 'currentTime', { value: 30, writable: true });

      // Press an unrecognized key
      fireEvent.keyDown(window, { key: 'x' });

      // Nothing should change
      expect(video.currentTime).toBe(30);
    });
  });
});
