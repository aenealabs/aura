import { useRef, useEffect, useState, useCallback } from 'react';
import {
  PaperAirplaneIcon,
  PaperClipIcon,
  MicrophoneIcon,
  StopIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import { useChat } from '../../context/ChatContext';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import { useFileAttachment, DropZoneOverlay } from '../../hooks/useFileAttachment';
import AttachmentPreview, { MAX_FILE_SIZE, MAX_ATTACHMENTS, FILE_ACCEPT_STRING } from './AttachmentPreview';

/**
 * ChatInput - Message input area with multi-line support, file attachments, and voice input
 *
 * Design Decisions:
 * - Auto-growing textarea (expands with content)
 * - Enter to send, Shift+Enter for new line
 * - Character counter (subtle, shows near limit)
 * - File attachment with drag-and-drop support
 * - Voice input using Web Speech API
 * - Aura blue send button
 */

const MAX_CHARS = 4000;
const WARN_THRESHOLD = 3500;

export default function ChatInput({ disabled = false, placeholder }) {
  const { sendMessage, draftMessage, setDraftMessage, isTyping } = useChat();
  const textareaRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);

  // File attachment hook
  const {
    attachments,
    isDragging,
    error: attachmentError,
    addFiles: _addFiles,
    removeFile,
    clearFiles,
    openFilePicker,
    inputProps,
    dropZoneProps,
    canAddMore,
  } = useFileAttachment({
    maxSize: MAX_FILE_SIZE,
    maxFiles: MAX_ATTACHMENTS,
    acceptedTypes: FILE_ACCEPT_STRING.split(','),
  });

  // Voice input hook
  const {
    isListening,
    isProcessing,
    transcript: _transcript,
    interimTranscript,
    error: voiceError,
    isSupported: isVoiceSupported,
    startListening,
    stopListening,
    resetTranscript,
  } = useVoiceInput({
    onResult: (text) => {
      // Append transcribed text to draft message
      setDraftMessage((prev) => {
        const separator = prev.trim() ? ' ' : '';
        return prev + separator + text;
      });
    },
  });

  // Track if we've appended the transcript
  const lastTranscriptRef = useRef('');

  // Effect to update message with interim transcript for preview
  useEffect(() => {
    if (interimTranscript && interimTranscript !== lastTranscriptRef.current) {
      lastTranscriptRef.current = interimTranscript;
    }
  }, [interimTranscript]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [draftMessage]);

  // Focus input on mount
  useEffect(() => {
    if (textareaRef.current && !disabled) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  // Reset transcript when starting fresh
  useEffect(() => {
    if (!isListening) {
      lastTranscriptRef.current = '';
    }
  }, [isListening]);

  const handleSubmit = useCallback((e) => {
    e?.preventDefault();
    if ((draftMessage.trim() || attachments.length > 0) && !disabled && !isTyping) {
      // Build message with attachments
      const messageContent = draftMessage.trim();
      const messageAttachments = attachments.map(a => ({
        name: a.name,
        size: a.size,
        type: a.type,
        preview: a.preview,
      }));

      // Send message (context will handle attachments in payload)
      sendMessage(messageContent, messageAttachments);
      clearFiles();
      resetTranscript();
    }
  }, [draftMessage, attachments, disabled, isTyping, sendMessage, clearFiles, resetTranscript]);

  const handleKeyDown = (e) => {
    // Enter to send, Shift+Enter for new line
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e) => {
    const value = e.target.value;
    if (value.length <= MAX_CHARS) {
      setDraftMessage(value);
    }
  };

  const handleVoiceClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleAttachClick = () => {
    if (canAddMore) {
      openFilePicker();
    }
  };

  const charCount = draftMessage.length;
  const showCharCount = charCount >= WARN_THRESHOLD;
  const isNearLimit = charCount >= WARN_THRESHOLD;
  const isAtLimit = charCount >= MAX_CHARS;
  const canSend = (draftMessage.trim().length > 0 || attachments.length > 0) && !disabled && !isTyping;

  // Display text includes interim transcription
  const _displayText = draftMessage + (interimTranscript && isListening ? ` ${interimTranscript}` : '');

  return (
    <div
      className="border-t border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800"
      {...dropZoneProps}
    >
      {/* Drag-and-drop overlay */}
      <DropZoneOverlay
        isDragging={isDragging}
        maxFiles={MAX_ATTACHMENTS}
        currentCount={attachments.length}
      />

      {/* Attachment previews */}
      <AttachmentPreview
        attachments={attachments}
        onRemove={removeFile}
        maxAttachments={MAX_ATTACHMENTS}
      />

      {/* Error messages */}
      {(attachmentError || voiceError) && (
        <div className="px-4 py-2 bg-critical-50 dark:bg-critical-900/20 border-b border-critical-200 dark:border-critical-800">
          <div className="flex items-center gap-2">
            <XCircleIcon className="w-4 h-4 text-critical-500" />
            <p className="text-sm text-critical-600 dark:text-critical-400">
              {attachmentError || voiceError}
            </p>
          </div>
        </div>
      )}

      {/* Voice recording indicator */}
      {isListening && (
        <div className="px-4 py-2 bg-critical-50 dark:bg-critical-900/20 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="relative">
              <span className="absolute inset-0 rounded-full bg-critical-500 animate-ping opacity-75" />
              <span className="relative block w-3 h-3 rounded-full bg-critical-500" />
            </div>
            <span className="text-sm font-medium text-critical-600 dark:text-critical-400">
              {isProcessing ? 'Listening...' : 'Starting microphone...'}
            </span>
            {interimTranscript && (
              <span className="text-sm text-surface-500 dark:text-surface-400 italic truncate flex-1">
                {interimTranscript}
              </span>
            )}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="relative p-4">
        {/* Hidden file input */}
        <input {...inputProps} />

        {/* Input container */}
        <div
          className={`
            relative flex items-end gap-2
            bg-surface-50 dark:bg-surface-700/50
            border rounded-2xl
            transition-all duration-200
            ${isDragging
              ? 'border-blue-500 dark:border-blue-400 ring-2 ring-blue-500/20 bg-blue-50 dark:bg-blue-900/10'
              : 'border-surface-200 dark:border-surface-600'
            }
          `}
        >
          {/* Attachment button */}
          <button
            type="button"
            onClick={handleAttachClick}
            disabled={!canAddMore || disabled}
            className={`
              flex-shrink-0 p-3
              transition-colors duration-150
              focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg
              ${canAddMore && !disabled
                ? 'text-surface-500 dark:text-surface-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-surface-100 dark:hover:bg-surface-600'
                : 'text-surface-300 dark:text-surface-600 cursor-not-allowed'
              }
            `}
            aria-label={canAddMore ? 'Attach file' : 'Maximum attachments reached'}
            title={canAddMore ? 'Attach file (drag and drop supported)' : 'Maximum attachments reached'}
          >
            <PaperClipIcon className="w-5 h-5" />
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={draftMessage}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            disabled={disabled}
            placeholder={isListening ? 'Speak now...' : (placeholder || 'Ask Aura anything...')}
            rows={1}
            className={`
              flex-1 py-3 pr-2
              bg-transparent
              text-surface-900 dark:text-surface-100
              placeholder-surface-400 dark:placeholder-surface-500
              text-sm
              resize-none
              focus:outline-none
              disabled:opacity-50 disabled:cursor-not-allowed
              min-h-[44px] max-h-[200px]
              ${isListening ? 'placeholder:animate-pulse' : ''}
            `}
            aria-label="Message input"
          />

          {/* Voice input button */}
          <button
            type="button"
            onClick={handleVoiceClick}
            disabled={disabled || !isVoiceSupported}
            className={`
              flex-shrink-0 p-3
              transition-all duration-150
              focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg
              ${!isVoiceSupported
                ? 'text-surface-300 dark:text-surface-600 cursor-not-allowed'
                : isListening
                  ? 'text-critical-500 dark:text-critical-400 hover:text-critical-600 dark:hover:text-critical-300 hover:bg-critical-50 dark:hover:bg-critical-900/30 animate-pulse'
                  : 'text-surface-500 dark:text-surface-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-surface-100 dark:hover:bg-surface-600'
              }
            `}
            aria-label={
              !isVoiceSupported
                ? 'Voice input not supported in this browser'
                : isListening
                  ? 'Stop recording'
                  : 'Start voice input'
            }
            title={
              !isVoiceSupported
                ? 'Voice input not supported. Try Chrome, Edge, or Safari.'
                : isListening
                  ? 'Click to stop recording'
                  : 'Click to start voice input'
            }
          >
            {isListening ? (
              <StopIcon className="w-5 h-5" />
            ) : (
              <MicrophoneIcon className="w-5 h-5" />
            )}
          </button>

          {/* Send button */}
          <button
            type="submit"
            disabled={!canSend}
            className={`
              flex-shrink-0 p-3 mr-1 mb-1
              rounded-xl
              transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-blue-500
              ${canSend
                ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-sm hover:shadow'
                : 'bg-surface-200 dark:bg-surface-600 text-surface-400 dark:text-surface-500 cursor-not-allowed'
              }
            `}
            aria-label="Send message"
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Footer with character count and hints */}
        <div className="flex items-center justify-between mt-2 px-2">
          {/* Keyboard hint */}
          <p className="text-xs text-surface-400 dark:text-surface-500">
            <kbd className="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 font-mono text-xs">
              Enter
            </kbd>
            {' to send, '}
            <kbd className="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 font-mono text-xs">
              Shift+Enter
            </kbd>
            {' for new line'}
          </p>

          {/* Character count */}
          {showCharCount && (
            <span
              className={`
                text-xs font-medium
                transition-colors duration-200
                ${isAtLimit
                  ? 'text-critical-500'
                  : isNearLimit
                    ? 'text-warning-500'
                    : 'text-surface-400'
                }
              `}
            >
              {charCount}/{MAX_CHARS}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

/**
 * ChatInputCompact - Smaller input variant for embedded use
 */
export function ChatInputCompact({
  value,
  onChange,
  onSubmit,
  placeholder = 'Type a message...',
  disabled = false,
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="
          flex-1 px-4 py-2
          bg-surface-50 dark:bg-surface-700
          border border-surface-200 dark:border-surface-600
          rounded-full
          text-sm text-surface-900 dark:text-surface-100
          placeholder-surface-400 dark:placeholder-surface-500
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          disabled:opacity-50 disabled:cursor-not-allowed
        "
      />
      <button
        onClick={onSubmit}
        disabled={!value?.trim() || disabled}
        className={`
          p-2 rounded-full
          transition-all duration-200
          ${value?.trim()
            ? 'bg-blue-500 hover:bg-blue-600 text-white'
            : 'bg-surface-200 dark:bg-surface-600 text-surface-400 cursor-not-allowed'
          }
        `}
        aria-label="Send"
      >
        <PaperAirplaneIcon className="w-4 h-4" />
      </button>
    </div>
  );
}
