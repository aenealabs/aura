/**
 * Project Aura - Video Player
 *
 * P4: Custom video player for onboarding videos.
 *
 * Features:
 * - Custom controls (play/pause, seek, volume, fullscreen)
 * - Chapter navigation
 * - Progress tracking
 * - Keyboard shortcuts
 * - Accessibility support
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  PlayIcon,
  PauseIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ForwardIcon,
  BackwardIcon,
} from '@heroicons/react/24/solid';

const VideoPlayer = ({
  src,
  poster,
  chapters = [],
  initialProgress = 0,
  onProgress,
  onComplete,
  className = '',
}) => {
  const videoRef = useRef(null);
  const progressRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const controlsTimeoutRef = useRef(null);

  // Format time as MM:SS
  const formatTime = useCallback((seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  // Calculate progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  // Play/Pause
  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
  }, [isPlaying]);

  // Seek
  const handleSeek = useCallback((e) => {
    const video = videoRef.current;
    const bar = progressRef.current;
    if (!video || !bar) return;

    const rect = bar.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    video.currentTime = percent * video.duration;
  }, []);

  // Skip forward/backward
  const skip = useCallback((seconds) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
  }, []);

  // Go to chapter
  const goToChapter = useCallback((time) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = time;
    if (!isPlaying) {
      video.play();
    }
  }, [isPlaying]);

  // Toggle mute
  const toggleMute = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    video.muted = !isMuted;
    setIsMuted(!isMuted);
  }, [isMuted]);

  // Change volume
  const handleVolumeChange = useCallback((e) => {
    const video = videoRef.current;
    if (!video) return;

    const newVolume = parseFloat(e.target.value);
    video.volume = newVolume;
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
  }, []);

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    const container = videoRef.current?.parentElement;
    if (!container) return;

    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      container.requestFullscreen();
    }
  }, []);

  // Handle video events
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      const progressPercent = (video.currentTime / video.duration) * 100;
      onProgress?.(progressPercent, video.currentTime >= video.duration - 1);
    };
    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      if (initialProgress > 0) {
        video.currentTime = (initialProgress / 100) * video.duration;
      }
    };
    const handleEnded = () => {
      setIsPlaying(false);
      onComplete?.();
    };
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('ended', handleEnded);
    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('ended', handleEnded);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [initialProgress, onProgress, onComplete]);

  // Auto-hide controls
  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current);
    }
    if (isPlaying) {
      controlsTimeoutRef.current = setTimeout(() => {
        setShowControls(false);
      }, 3000);
    }
  }, [isPlaying]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT') return;

      switch (e.key) {
        case ' ':
        case 'k':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          skip(-10);
          break;
        case 'ArrowRight':
          e.preventDefault();
          skip(10);
          break;
        case 'm':
          e.preventDefault();
          toggleMute();
          break;
        case 'f':
          e.preventDefault();
          toggleFullscreen();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, skip, toggleMute, toggleFullscreen]);

  // Get current chapter
  const currentChapter = chapters.reduce((acc, chapter) => {
    if (currentTime >= chapter.time) return chapter;
    return acc;
  }, chapters[0]);

  return (
    <div
      className={`relative bg-black rounded-lg overflow-hidden group ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => isPlaying && setShowControls(false)}
    >
      {/* Video element */}
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        className="w-full h-full object-contain"
        onClick={togglePlay}
        playsInline
      />

      {/* Play button overlay (when paused) */}
      {!isPlaying && (
        <button
          onClick={togglePlay}
          className="absolute inset-0 flex items-center justify-center bg-black/30"
          aria-label="Play video"
        >
          <div className="w-16 h-16 flex items-center justify-center rounded-full bg-white shadow-lg">
            <PlayIcon className="w-8 h-8 text-surface-900 ml-1" />
          </div>
        </button>
      )}

      {/* Controls overlay */}
      <div
        className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent transition-opacity ${
          showControls ? 'opacity-100' : 'opacity-0'
        }`}
      >
        {/* Progress bar */}
        <div
          ref={progressRef}
          className="relative h-1 mx-4 mb-2 bg-white/30 rounded-full cursor-pointer group/progress"
          onClick={handleSeek}
        >
          {/* Chapter markers */}
          {chapters.map((chapter) => (
            <div
              key={chapter.time}
              className="absolute top-0 bottom-0 w-0.5 bg-white/50"
              style={{ left: `${(chapter.time / duration) * 100}%` }}
              title={chapter.title}
            />
          ))}

          {/* Played progress */}
          <div
            className="absolute inset-y-0 left-0 bg-aura-500 rounded-full"
            style={{ width: `${progress}%` }}
          />

          {/* Seek handle */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow opacity-0 group-hover/progress:opacity-100 transition-opacity"
            style={{ left: `${progress}%`, marginLeft: '-6px' }}
          />
        </div>

        {/* Control buttons */}
        <div className="flex items-center justify-between px-4 pb-3">
          {/* Left controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlay}
              className="p-1.5 text-white hover:text-aura-400 transition-colors"
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? (
                <PauseIcon className="w-5 h-5" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
            </button>

            <button
              onClick={() => skip(-10)}
              className="p-1.5 text-white hover:text-aura-400 transition-colors"
              aria-label="Skip back 10 seconds"
            >
              <BackwardIcon className="w-5 h-5" />
            </button>

            <button
              onClick={() => skip(10)}
              className="p-1.5 text-white hover:text-aura-400 transition-colors"
              aria-label="Skip forward 10 seconds"
            >
              <ForwardIcon className="w-5 h-5" />
            </button>

            {/* Time display */}
            <span className="text-xs text-white/80 font-mono ml-2">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-2">
            {/* Chapter indicator */}
            {currentChapter && (
              <span className="text-xs text-white/60 mr-2">
                {currentChapter.title}
              </span>
            )}

            {/* Volume */}
            <div className="flex items-center gap-1 group/volume">
              <button
                onClick={toggleMute}
                className="p-1.5 text-white hover:text-aura-400 transition-colors"
                aria-label={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted || volume === 0 ? (
                  <SpeakerXMarkIcon className="w-5 h-5" />
                ) : (
                  <SpeakerWaveIcon className="w-5 h-5" />
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="w-0 group-hover/volume:w-16 transition-all opacity-0 group-hover/volume:opacity-100"
                aria-label="Volume"
              />
            </div>

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="p-1.5 text-white hover:text-aura-400 transition-colors"
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            >
              {isFullscreen ? (
                <ArrowsPointingInIcon className="w-5 h-5" />
              ) : (
                <ArrowsPointingOutIcon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Chapter list (optional, can be toggled) */}
      {chapters.length > 0 && showControls && (
        <div className="absolute top-4 right-4 bg-black/60 rounded-lg p-2 max-h-40 overflow-y-auto">
          <p className="text-xs text-white/60 mb-1 px-2">Chapters</p>
          {chapters.map((chapter) => (
            <button
              key={chapter.time}
              onClick={() => goToChapter(chapter.time)}
              className={`block w-full text-left px-2 py-1 text-xs rounded hover:bg-white/10 transition-colors ${
                currentChapter?.time === chapter.time
                  ? 'text-aura-400'
                  : 'text-white/80'
              }`}
            >
              <span className="font-mono mr-2">{formatTime(chapter.time)}</span>
              {chapter.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default VideoPlayer;
