import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * useFileAttachment Hook - File attachment handling with drag-and-drop support
 *
 * Features:
 * - Drag-and-drop file upload
 * - Click to browse files
 * - File type validation
 * - File size validation (configurable max size)
 * - Image preview generation
 * - Multiple file support
 * - Max attachments limit
 *
 * Issue: #20 - Frontend production polish
 *
 * Usage:
 *   const {
 *     attachments,
 *     isDragging,
 *     addFiles,
 *     removeFile,
 *     clearFiles,
 *     error,
 *     inputRef,
 *     dropZoneProps,
 *   } = useFileAttachment({
 *     maxSize: 10 * 1024 * 1024, // 10MB
 *     maxFiles: 5,
 *     acceptedTypes: ['image/*', 'application/pdf', '.py', '.js'],
 *   });
 */

// Default max file size (10MB)
const DEFAULT_MAX_SIZE = 10 * 1024 * 1024;

// Default max number of files
const DEFAULT_MAX_FILES = 5;

// Default accepted file types
const DEFAULT_ACCEPTED_TYPES = [
  // Images
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/svg+xml',
  // Documents
  'application/pdf',
  'text/plain',
  'text/markdown',
  'text/csv',
  // Code files (by extension)
  '.js',
  '.jsx',
  '.ts',
  '.tsx',
  '.py',
  '.java',
  '.go',
  '.rs',
  '.rb',
  '.php',
  '.c',
  '.cpp',
  '.h',
  '.cs',
  '.swift',
  '.kt',
  '.sh',
  '.yaml',
  '.yml',
  '.json',
  '.xml',
  '.html',
  '.css',
  '.sql',
  '.md',
  '.txt',
  '.log',
];

/**
 * Validate file against accepted types
 */
function isValidFileType(file, acceptedTypes) {
  const fileName = file.name.toLowerCase();
  const fileType = file.type;

  return acceptedTypes.some((type) => {
    // Extension-based check (e.g., '.py')
    if (type.startsWith('.')) {
      return fileName.endsWith(type);
    }
    // Wildcard MIME type (e.g., 'image/*')
    if (type.endsWith('/*')) {
      const category = type.split('/')[0];
      return fileType.startsWith(category + '/');
    }
    // Exact MIME type match
    return fileType === type;
  });
}

/**
 * Generate preview URL for image files
 */
function generatePreview(file) {
  return new Promise((resolve) => {
    if (!file.type.startsWith('image/')) {
      resolve(null);
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      resolve(reader.result);
    };
    reader.onerror = () => {
      resolve(null);
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Process files and add metadata
 */
async function processFiles(files, options) {
  const { maxSize, acceptedTypes } = options;
  const processed = [];

  for (const file of files) {
    const isValidType = isValidFileType(file, acceptedTypes);
    const isValidSize = file.size <= maxSize;

    let errorMessage = null;
    if (!isValidType) {
      errorMessage = 'Unsupported file type';
    } else if (!isValidSize) {
      errorMessage = `File exceeds ${formatBytes(maxSize)} limit`;
    }

    const preview = await generatePreview(file);

    processed.push({
      file,
      name: file.name,
      size: file.size,
      type: file.type,
      preview,
      error: errorMessage,
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      uploading: false,
    });
  }

  return processed;
}

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Main useFileAttachment hook
 */
export function useFileAttachment(options = {}) {
  const {
    maxSize = DEFAULT_MAX_SIZE,
    maxFiles = DEFAULT_MAX_FILES,
    acceptedTypes = DEFAULT_ACCEPTED_TYPES,
    onFilesAdded,
    onFileRemoved,
    onError,
  } = options;

  // State
  const [attachments, setAttachments] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);

  // Refs
  const inputRef = useRef(null);
  const dragCounterRef = useRef(0);

  // Cleanup previews on unmount
  useEffect(() => {
    return () => {
      attachments.forEach((attachment) => {
        if (attachment.preview?.startsWith('blob:')) {
          URL.revokeObjectURL(attachment.preview);
        }
      });
    };
  }, [attachments]);

  // Add files
  const addFiles = useCallback(
    async (fileList) => {
      setError(null);

      // Convert FileList to array
      const files = Array.from(fileList);

      if (files.length === 0) return;

      // Check max files limit
      const currentCount = attachments.length;
      const availableSlots = maxFiles - currentCount;

      if (availableSlots <= 0) {
        const errorMsg = `Maximum of ${maxFiles} files allowed`;
        setError(errorMsg);
        onError?.(errorMsg);
        return;
      }

      // Limit files to available slots
      const filesToProcess = files.slice(0, availableSlots);
      if (files.length > availableSlots) {
        const warnMsg = `Only ${availableSlots} more file(s) can be added`;
        setError(warnMsg);
      }

      // Process files
      const processed = await processFiles(filesToProcess, { maxSize, acceptedTypes });

      // Check for errors in processed files
      const hasErrors = processed.some((f) => f.error);
      if (hasErrors) {
        const errorFiles = processed.filter((f) => f.error);
        const firstError = errorFiles[0].error;
        setError(`${errorFiles.length} file(s) skipped: ${firstError}`);
        onError?.(firstError);
      }

      // Filter out invalid files
      const validFiles = processed.filter((f) => !f.error);

      if (validFiles.length > 0) {
        setAttachments((prev) => [...prev, ...validFiles]);
        onFilesAdded?.(validFiles);
      }
    },
    [attachments.length, maxFiles, maxSize, acceptedTypes, onFilesAdded, onError]
  );

  // Remove file by index
  const removeFile = useCallback(
    (index) => {
      setAttachments((prev) => {
        const removed = prev[index];
        const newAttachments = prev.filter((_, i) => i !== index);

        // Cleanup preview URL
        if (removed?.preview?.startsWith('blob:')) {
          URL.revokeObjectURL(removed.preview);
        }

        onFileRemoved?.(removed, index);
        return newAttachments;
      });
      setError(null);
    },
    [onFileRemoved]
  );

  // Remove file by ID
  const removeFileById = useCallback(
    (id) => {
      const index = attachments.findIndex((a) => a.id === id);
      if (index !== -1) {
        removeFile(index);
      }
    },
    [attachments, removeFile]
  );

  // Clear all files
  const clearFiles = useCallback(() => {
    // Cleanup all preview URLs
    attachments.forEach((attachment) => {
      if (attachment.preview?.startsWith('blob:')) {
        URL.revokeObjectURL(attachment.preview);
      }
    });
    setAttachments([]);
    setError(null);
  }, [attachments]);

  // Open file picker
  const openFilePicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  // Handle file input change
  const handleInputChange = useCallback(
    (event) => {
      const files = event.target.files;
      if (files && files.length > 0) {
        addFiles(files);
      }
      // Reset input value to allow selecting the same file again
      event.target.value = '';
    },
    [addFiles]
  );

  // Drag event handlers
  const handleDragEnter = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current++;
    if (event.dataTransfer?.items?.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      dragCounterRef.current = 0;

      const files = event.dataTransfer?.files;
      if (files && files.length > 0) {
        addFiles(files);
      }
    },
    [addFiles]
  );

  // Props to spread on drop zone element
  const dropZoneProps = {
    onDragEnter: handleDragEnter,
    onDragLeave: handleDragLeave,
    onDragOver: handleDragOver,
    onDrop: handleDrop,
  };

  // Props for the hidden file input
  const inputProps = {
    ref: inputRef,
    type: 'file',
    multiple: maxFiles > 1,
    accept: acceptedTypes.join(','),
    onChange: handleInputChange,
    style: { display: 'none' },
    'aria-hidden': true,
    tabIndex: -1,
  };

  return {
    // State
    attachments,
    isDragging,
    error,
    hasAttachments: attachments.length > 0,
    canAddMore: attachments.length < maxFiles,
    attachmentCount: attachments.length,

    // Actions
    addFiles,
    removeFile,
    removeFileById,
    clearFiles,
    openFilePicker,

    // Props for elements
    inputRef,
    inputProps,
    dropZoneProps,

    // Config
    maxFiles,
    maxSize,
    acceptedTypes,
  };
}

/**
 * DropZoneOverlay - Visual overlay when dragging files
 */
export function DropZoneOverlay({ isDragging, maxFiles, currentCount }) {
  if (!isDragging) return null;

  const canAdd = currentCount < maxFiles;
  const slotsRemaining = maxFiles - currentCount;

  return (
    <div
      className="
        absolute inset-0 z-50
        bg-olive-500/10 dark:bg-olive-400/10
        border-2 border-dashed border-olive-500 dark:border-olive-400
        rounded-2xl
        flex items-center justify-center
        backdrop-blur-sm
        animate-fade-in
      "
    >
      <div className="text-center">
        <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-olive-100 dark:bg-olive-900/50 flex items-center justify-center">
          <svg
            className="w-6 h-6 text-olive-600 dark:text-olive-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>
        {canAdd ? (
          <>
            <p className="text-sm font-medium text-olive-700 dark:text-olive-300">
              Drop files here
            </p>
            <p className="text-xs text-olive-600 dark:text-olive-400 mt-1">
              {slotsRemaining} slot{slotsRemaining !== 1 ? 's' : ''} remaining
            </p>
          </>
        ) : (
          <p className="text-sm font-medium text-warning-600 dark:text-warning-400">
            Maximum files reached
          </p>
        )}
      </div>
    </div>
  );
}

export default useFileAttachment;
