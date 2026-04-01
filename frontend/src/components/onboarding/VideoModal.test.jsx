/**
 * Tests for VideoModal and VideoCard components
 *
 * Tests the P4 video modal wrapper including:
 * - Conditional rendering based on isOpen and video data
 * - Video title and description display
 * - Progress tracking and display
 * - Escape key to close
 * - Backdrop click to close
 * - Body scroll prevention
 * - Accessibility attributes
 *
 * Also tests VideoCard component for video listing.
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import VideoModal, { VideoCard } from './VideoModal';

// Mock the OnboardingContext
vi.mock('../../context/OnboardingContext', () => ({
  useVideoProgress: vi.fn(),
}));

// Mock VideoPlayer to avoid HTMLMediaElement issues in jsdom
vi.mock('./VideoPlayer', () => ({
  default: ({ src, onProgress, onComplete }) => (
    <div data-testid="mock-video-player" data-src={src}>
      <button onClick={() => onProgress?.(50, false)}>Simulate Progress</button>
      <button onClick={() => onComplete?.()}>Simulate Complete</button>
    </div>
  ),
}));

import { useVideoProgress } from '../../context/OnboardingContext';

const mockVideo = {
  id: 'getting_started',
  title: 'Getting Started with Project Aura',
  description: 'Learn the basics of the platform in this introductory video.',
  video_url: 'https://example.com/videos/getting-started.mp4',
  thumbnail_url: 'https://example.com/thumbnails/getting-started.jpg',
  duration: 150, // 2:30
  chapters: [
    { time: 0, title: 'Introduction' },
    { time: 60, title: 'Dashboard Overview' },
    { time: 120, title: 'Next Steps' },
  ],
};

const defaultMockProgress = {
  percent: 0,
  completed: false,
};

const defaultMockHook = {
  video: mockVideo,
  progress: defaultMockProgress,
  updateProgress: vi.fn(),
};

describe('VideoModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useVideoProgress.mockReturnValue({ ...defaultMockHook });
    document.body.style.overflow = '';
  });

  afterEach(() => {
    document.body.style.overflow = '';
  });

  describe('Visibility', () => {
    test('renders nothing when isOpen is false', () => {
      const { container } = render(
        <VideoModal videoId="getting_started" isOpen={false} onClose={vi.fn()} />
      );

      expect(container.firstChild).toBeNull();
    });

    test('renders nothing when video is null', () => {
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        video: null,
      });

      const { container } = render(
        <VideoModal videoId="nonexistent" isOpen={true} onClose={vi.fn()} />
      );

      expect(container.firstChild).toBeNull();
    });

    test('renders modal when isOpen is true and video exists', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('renders modal via portal to document.body', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      // Modal should be rendered in document.body via portal
      const dialog = document.body.querySelector('[role="dialog"]');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('Content Display', () => {
    test('displays video title', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByText('Getting Started with Project Aura')).toBeInTheDocument();
    });

    test('displays video description', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(
        screen.getByText('Learn the basics of the platform in this introductory video.')
      ).toBeInTheDocument();
    });

    test('displays formatted duration', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByText('Duration: 2:30')).toBeInTheDocument();
    });

    test('renders VideoPlayer component', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByTestId('mock-video-player')).toBeInTheDocument();
    });

    test('passes correct props to VideoPlayer', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      const player = screen.getByTestId('mock-video-player');
      expect(player).toHaveAttribute('data-src', mockVideo.video_url);
    });

    test('displays close button', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByLabelText('Close video')).toBeInTheDocument();
    });
  });

  describe('Progress Display', () => {
    test('shows nothing when progress is 0', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.queryByText(/watched/)).not.toBeInTheDocument();
      expect(screen.queryByText('Completed')).not.toBeInTheDocument();
    });

    test('shows percentage when progress is between 0 and 100', () => {
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        progress: { percent: 45, completed: false },
      });

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByText('45% watched')).toBeInTheDocument();
    });

    test('shows Completed when video is completed', () => {
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        progress: { percent: 100, completed: true },
      });

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    test('rounds progress percentage', () => {
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        progress: { percent: 33.7, completed: false },
      });

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByText('34% watched')).toBeInTheDocument();
    });
  });

  describe('Close Functionality', () => {
    test('calls onClose when close button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      await user.click(screen.getByLabelText('Close video'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('calls onClose when Escape key is pressed', () => {
      const onClose = vi.fn();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('does not call onClose for other keys', () => {
      const onClose = vi.fn();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      fireEvent.keyDown(document, { key: 'Enter' });
      expect(onClose).not.toHaveBeenCalled();
    });

    test('calls onClose when backdrop is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      const dialog = screen.getByRole('dialog');
      await user.click(dialog);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    test('does not call onClose when clicking inside modal content', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      await user.click(screen.getByText('Getting Started with Project Aura'));
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('Body Scroll Prevention', () => {
    test('prevents body scroll when modal is open', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(document.body.style.overflow).toBe('hidden');
    });

    test('restores body scroll when modal closes', () => {
      const { rerender } = render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(document.body.style.overflow).toBe('hidden');

      rerender(
        <VideoModal videoId="getting_started" isOpen={false} onClose={vi.fn()} />
      );

      expect(document.body.style.overflow).toBe('');
    });

    test('does not set overflow when modal is closed', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={false} onClose={vi.fn()} />
      );

      expect(document.body.style.overflow).toBe('');
    });

    test('cleans up body scroll on unmount', () => {
      const { unmount } = render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(document.body.style.overflow).toBe('hidden');

      unmount();

      expect(document.body.style.overflow).toBe('');
    });
  });

  describe('Progress Callbacks', () => {
    test('calls updateProgress when video progress changes', async () => {
      const updateProgress = vi.fn();
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        updateProgress,
      });
      const user = userEvent.setup();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      await user.click(screen.getByText('Simulate Progress'));
      expect(updateProgress).toHaveBeenCalledWith(50, false);
    });

    test('calls updateProgress with 100% when video completes', async () => {
      const updateProgress = vi.fn();
      useVideoProgress.mockReturnValue({
        ...defaultMockHook,
        updateProgress,
      });
      const user = userEvent.setup();

      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      await user.click(screen.getByText('Simulate Complete'));
      expect(updateProgress).toHaveBeenCalledWith(100, true);
    });
  });

  describe('Accessibility', () => {
    test('has dialog role', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('has aria-modal attribute', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
    });

    test('has aria-labelledby pointing to title', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'video-modal-title');

      const title = screen.getByText('Getting Started with Project Aura');
      expect(title).toHaveAttribute('id', 'video-modal-title');
    });

    test('close button has accessible label', () => {
      render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={vi.fn()} />
      );

      expect(screen.getByLabelText('Close video')).toBeInTheDocument();
    });
  });

  describe('Cleanup', () => {
    test('removes escape key listener on unmount', () => {
      const onClose = vi.fn();
      const { unmount } = render(
        <VideoModal videoId="getting_started" isOpen={true} onClose={onClose} />
      );

      unmount();

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onClose).not.toHaveBeenCalled();
    });

    test('does not add escape listener when modal is closed', () => {
      const onClose = vi.fn();

      render(
        <VideoModal videoId="getting_started" isOpen={false} onClose={onClose} />
      );

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onClose).not.toHaveBeenCalled();
    });
  });
});

describe('VideoCard', () => {
  const mockCardVideo = {
    id: 'security_scanning',
    title: 'Security Scanning',
    description: 'Learn how to scan your code for vulnerabilities.',
    thumbnail_url: 'https://example.com/thumbnails/security.jpg',
    duration: 165, // 2:45
  };

  const defaultProgress = {
    percent: 0,
    completed: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    test('renders video title', () => {
      render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(screen.getByText('Security Scanning')).toBeInTheDocument();
    });

    test('renders video description', () => {
      render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(
        screen.getByText('Learn how to scan your code for vulnerabilities.')
      ).toBeInTheDocument();
    });

    test('renders formatted duration badge', () => {
      render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(screen.getByText('2:45')).toBeInTheDocument();
    });

    test('renders thumbnail when provided', () => {
      const { container } = render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      // Image has alt="" so it's role="presentation", use querySelector
      const thumbnail = container.querySelector('img');
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('src', mockCardVideo.thumbnail_url);
    });

    test('renders placeholder icon when no thumbnail', () => {
      const videoWithoutThumbnail = {
        ...mockCardVideo,
        thumbnail_url: null,
      };

      const { container } = render(
        <VideoCard video={videoWithoutThumbnail} progress={defaultProgress} onClick={vi.fn()} />
      );

      // Should render PlayCircleIcon as placeholder
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    test('is rendered as a button', () => {
      render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('Progress Display', () => {
    test('does not show progress bar when progress is 0', () => {
      const { container } = render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={vi.fn()} />
      );

      // Progress bar inside thumbnail area
      const progressBar = container.querySelector('.bg-aura-500');
      expect(progressBar).not.toBeInTheDocument();
    });

    test('shows progress bar when progress is greater than 0', () => {
      const { container } = render(
        <VideoCard
          video={mockCardVideo}
          progress={{ percent: 50, completed: false }}
          onClick={vi.fn()}
        />
      );

      const progressBar = container.querySelector('.bg-aura-500');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveStyle({ width: '50%' });
    });

    test('shows Watched badge when completed', () => {
      render(
        <VideoCard
          video={mockCardVideo}
          progress={{ percent: 100, completed: true }}
          onClick={vi.fn()}
        />
      );

      expect(screen.getByText('Watched')).toBeInTheDocument();
    });

    test('does not show Watched badge when not completed', () => {
      render(
        <VideoCard
          video={mockCardVideo}
          progress={{ percent: 50, completed: false }}
          onClick={vi.fn()}
        />
      );

      expect(screen.queryByText('Watched')).not.toBeInTheDocument();
    });
  });

  describe('Click Handling', () => {
    test('calls onClick when card is clicked', async () => {
      const onClick = vi.fn();
      const user = userEvent.setup();

      render(
        <VideoCard video={mockCardVideo} progress={defaultProgress} onClick={onClick} />
      );

      await user.click(screen.getByRole('button'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Duration Formatting', () => {
    test('formats duration with leading zero for seconds', () => {
      const videoWithShortDuration = {
        ...mockCardVideo,
        duration: 65, // 1:05
      };

      render(
        <VideoCard video={videoWithShortDuration} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(screen.getByText('1:05')).toBeInTheDocument();
    });

    test('formats duration correctly for round minutes', () => {
      const videoWithRoundDuration = {
        ...mockCardVideo,
        duration: 180, // 3:00
      };

      render(
        <VideoCard video={videoWithRoundDuration} progress={defaultProgress} onClick={vi.fn()} />
      );

      expect(screen.getByText('3:00')).toBeInTheDocument();
    });
  });
});
