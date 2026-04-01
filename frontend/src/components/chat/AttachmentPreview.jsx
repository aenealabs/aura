import {
  XMarkIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  PhotoIcon,
  DocumentIcon,
} from '@heroicons/react/24/outline';

/**
 * AttachmentPreview - Displays file attachment previews before sending
 *
 * Design Decisions:
 * - Thumbnail preview for images
 * - File type icons for non-image files
 * - File size and name display
 * - Remove button for each attachment
 * - Horizontal scroll for multiple attachments
 * - Max 5 attachments limit
 */

// File size formatter
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Get file type category
function getFileCategory(file) {
  const type = file.type || '';
  const name = file.name.toLowerCase();

  if (type.startsWith('image/')) return 'image';
  if (type === 'application/pdf') return 'pdf';
  if (
    type.includes('javascript') ||
    type.includes('typescript') ||
    type.includes('json') ||
    type.includes('xml') ||
    type.includes('html') ||
    type.includes('css') ||
    name.match(/\.(js|jsx|ts|tsx|py|java|go|rs|rb|php|c|cpp|h|hpp|cs|swift|kt|scala|sh|bash|zsh|yaml|yml|toml|ini|sql|graphql|vue|svelte)$/)
  ) {
    return 'code';
  }
  if (type.startsWith('text/') || name.match(/\.(txt|md|csv|log)$/)) {
    return 'text';
  }

  return 'document';
}

// Get icon component for file type
function getFileIcon(category) {
  switch (category) {
    case 'image':
      return PhotoIcon;
    case 'code':
      return CodeBracketIcon;
    case 'text':
    case 'pdf':
      return DocumentTextIcon;
    default:
      return DocumentIcon;
  }
}

// Get color classes for file type
function getFileColor(category) {
  switch (category) {
    case 'image':
      return 'bg-aura-100 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400';
    case 'code':
      return 'bg-olive-100 dark:bg-olive-900/30 text-olive-600 dark:text-olive-400';
    case 'pdf':
      return 'bg-critical-100 dark:bg-critical-900/30 text-critical-600 dark:text-critical-400';
    case 'text':
      return 'bg-aura-100 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400';
    default:
      return 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400';
  }
}

/**
 * Single attachment preview item
 */
function AttachmentItem({ file, onRemove, index }) {
  const category = getFileCategory(file);
  const Icon = getFileIcon(category);
  const isImage = category === 'image';

  // Truncate long filenames
  const displayName = file.name.length > 20
    ? file.name.substring(0, 17) + '...' + file.name.substring(file.name.lastIndexOf('.'))
    : file.name;

  return (
    <div
      className="
        relative flex-shrink-0
        group animate-fade-in
      "
      role="listitem"
      aria-label={`Attached file: ${file.name}`}
    >
      {/* Preview container */}
      <div
        className="
          relative w-24 h-24
          rounded-xl overflow-hidden
          border-2 border-surface-200 dark:border-surface-600
          bg-surface-50 dark:bg-surface-700
          transition-all duration-200
          group-hover:border-olive-400 dark:group-hover:border-olive-500
          group-hover:shadow-md
        "
      >
        {/* Image preview or icon */}
        {isImage && file.preview ? (
          <img
            src={file.preview}
            alt={file.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className={`w-full h-full flex items-center justify-center ${getFileColor(category)}`}>
            <Icon className="w-10 h-10" />
          </div>
        )}

        {/* Remove button */}
        <button
          onClick={() => onRemove(index)}
          className="
            absolute top-1 right-1
            p-1 rounded-full
            bg-surface-900/70 dark:bg-surface-100/70
            text-white dark:text-surface-900
            opacity-0 group-hover:opacity-100
            transition-opacity duration-150
            hover:bg-surface-900/90 dark:hover:bg-surface-100/90
            focus:outline-none focus:ring-2 focus:ring-olive-500
          "
          aria-label={`Remove ${file.name}`}
        >
          <XMarkIcon className="w-4 h-4" />
        </button>

        {/* Error indicator for oversized files */}
        {file.error && (
          <div className="absolute inset-0 bg-critical-500/20 flex items-center justify-center">
            <span className="text-xs text-critical-600 dark:text-critical-400 font-medium">
              Too large
            </span>
          </div>
        )}
      </div>

      {/* File info */}
      <div className="mt-1.5 px-0.5 max-w-24">
        <p
          className="text-xs font-medium text-surface-700 dark:text-surface-300 truncate"
          title={file.name}
        >
          {displayName}
        </p>
        <p className="text-xs text-surface-500 dark:text-surface-400">
          {formatFileSize(file.size)}
        </p>
      </div>
    </div>
  );
}

/**
 * Main AttachmentPreview component
 */
export default function AttachmentPreview({ attachments, onRemove, maxAttachments = 5 }) {
  if (!attachments || attachments.length === 0) return null;

  const hasMaxAttachments = attachments.length >= maxAttachments;

  return (
    <div className="px-4 py-3 border-b border-surface-200 dark:border-surface-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-surface-500 dark:text-surface-400">
          Attachments ({attachments.length}/{maxAttachments})
        </p>
        {hasMaxAttachments && (
          <p className="text-xs text-warning-500">
            Maximum attachments reached
          </p>
        )}
      </div>

      {/* Attachment list - horizontal scroll */}
      <div
        className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1"
        role="list"
        aria-label="File attachments"
      >
        {attachments.map((file, index) => (
          <AttachmentItem
            key={`${file.name}-${index}`}
            file={file}
            index={index}
            onRemove={onRemove}
          />
        ))}
      </div>

      {/* Upload progress indicator (when uploading) */}
      {attachments.some(f => f.uploading) && (
        <div className="mt-2">
          <div className="h-1 bg-surface-200 dark:bg-surface-600 rounded-full overflow-hidden">
            <div
              className="h-full bg-olive-500 rounded-full transition-all duration-300 animate-pulse"
              style={{ width: '60%' }}
            />
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
            Processing attachments...
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Supported file types list for reference
 */
export const SUPPORTED_FILE_TYPES = {
  images: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'],
  documents: ['application/pdf', 'text/plain', 'text/markdown', 'text/csv'],
  code: [
    'text/javascript',
    'text/typescript',
    'application/json',
    'text/html',
    'text/css',
    'text/x-python',
    'text/x-java',
    'text/x-go',
    'text/x-rust',
  ],
};

/**
 * File type accept string for input element
 */
export const FILE_ACCEPT_STRING = [
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
  // Code files (by extension since MIME types are inconsistent)
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
  '.hpp',
  '.cs',
  '.swift',
  '.kt',
  '.scala',
  '.sh',
  '.bash',
  '.yaml',
  '.yml',
  '.json',
  '.xml',
  '.html',
  '.css',
  '.sql',
  '.graphql',
  '.vue',
  '.svelte',
  '.md',
  '.txt',
  '.log',
].join(',');

/**
 * Maximum file size (10MB)
 */
export const MAX_FILE_SIZE = 10 * 1024 * 1024;

/**
 * Maximum number of attachments
 */
export const MAX_ATTACHMENTS = 5;
