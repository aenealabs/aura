/**
 * Project Aura - Video Modal
 *
 * Modal wrapper for the video player.
 * Used to display getting-started videos.
 */

import { useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { XMarkIcon, PlayCircleIcon } from '@heroicons/react/24/outline';
import VideoPlayer from './VideoPlayer';
import { useVideoProgress } from '../../context/OnboardingContext';
import { useFocusTrap } from '../../hooks/useFocusTrap';

const VideoModal = ({ videoId, isOpen, onClose }) => {
  const { video, progress, updateProgress } = useVideoProgress(videoId);

  // WCAG 2.1 AA: Focus trap for modal
  const { containerRef } = useFocusTrap(isOpen, {
    autoFocus: true,
    restoreFocus: true,
    escapeDeactivates: true,
    onEscape: onClose,
  });

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleBackdropClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  const handleProgress = useCallback(
    (percent, completed) => {
      updateProgress(percent, completed);
    },
    [updateProgress]
  );

  const handleComplete = useCallback(() => {
    updateProgress(100, true);
  }, [updateProgress]);

  if (!isOpen || !video) {
    return null;
  }

  const modal = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="video-modal-title"
    >
      {/* Modal container */}
      <div ref={containerRef} className="relative w-full max-w-4xl bg-surface-900 rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-surface-800 border-b border-surface-700">
          <div className="flex items-center gap-3">
            <PlayCircleIcon className="w-6 h-6 text-aura-400" />
            <div>
              <h2
                id="video-modal-title"
                className="text-sm font-semibold text-white"
              >
                {video.title}
              </h2>
              <p className="text-xs text-surface-400">{video.description}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-700 transition-colors"
            aria-label="Close video"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Video Player */}
        <VideoPlayer
          src={video.video_url}
          poster={video.thumbnail_url}
          chapters={video.chapters}
          initialProgress={progress.percent}
          onProgress={handleProgress}
          onComplete={handleComplete}
          className="aspect-video"
        />

        {/* Footer */}
        <div className="px-4 py-3 bg-surface-800 border-t border-surface-700">
          <div className="flex items-center justify-between">
            {/* Duration */}
            <span className="text-xs text-surface-400">
              Duration: {Math.floor(video.duration / 60)}:{(video.duration % 60).toString().padStart(2, '0')}
            </span>

            {/* Progress indicator */}
            <div className="flex items-center gap-2">
              {progress.completed ? (
                <span className="text-xs text-olive-400 font-medium">Completed</span>
              ) : progress.percent > 0 ? (
                <span className="text-xs text-surface-400">
                  {Math.round(progress.percent)}% watched
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};

// Video Card component for listing videos
export const VideoCard = ({ video, progress, onClick }) => {
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <button
      onClick={onClick}
      className="group flex flex-col bg-white dark:bg-surface-800 rounded-xl overflow-hidden border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-700 shadow-sm hover:shadow-md transition-all text-left"
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-surface-100 dark:bg-surface-700">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt=""
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <PlayCircleIcon className="w-12 h-12 text-surface-300 dark:text-surface-600" />
          </div>
        )}

        {/* Duration badge */}
        <span className="absolute bottom-2 right-2 px-1.5 py-0.5 text-xs font-medium text-white bg-black/70 rounded">
          {formatDuration(video.duration)}
        </span>

        {/* Play overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/30 transition-colors">
          <PlayCircleIcon className="w-12 h-12 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        {/* Progress bar */}
        {progress.percent > 0 && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/50">
            <div
              className="h-full bg-aura-500"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 group-hover:text-aura-600 dark:group-hover:text-aura-400 transition-colors">
          {video.title}
        </h3>
        <p className="mt-1 text-xs text-surface-500 dark:text-surface-400 line-clamp-2">
          {video.description}
        </p>

        {/* Status */}
        {progress.completed && (
          <span className="inline-flex items-center mt-2 text-xs text-olive-600 dark:text-olive-400">
            <svg className="w-3.5 h-3.5 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            Watched
          </span>
        )}
      </div>
    </button>
  );
};

export default VideoModal;
