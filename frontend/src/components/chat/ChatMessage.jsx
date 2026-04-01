import { useState, useEffect, useRef, useMemo } from 'react';
import {
  ClipboardDocumentIcon,
  CheckIcon,
  ArrowPathIcon,
  HandThumbUpIcon,
  HandThumbDownIcon,
  ExclamationTriangleIcon,
  StopIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { useChat } from '../../context/ChatContext';
import { getMermaid } from '../../utils/mermaidLoader';

/**
 * ChatMessage - Individual message display with markdown rendering and streaming support
 *
 * Design Decisions:
 * - User messages: Right-aligned, blue/olive background
 * - Assistant messages: Left-aligned, gray background
 * - Markdown support for formatting
 * - Code blocks with syntax highlighting and copy button
 * - Streaming text animation with cursor
 * - Inline action buttons for assistant responses
 * - Timestamp, status indicators, and token count
 * - Message rating (thumbs up/down)
 */

export default function ChatMessage({ message, isLast = false }) {
  const {
    regenerateResponse,
    retryMessage,
    copyMessageContent,
    rateMessage,
    cancelStream,
    streamingMessageId,
  } = useChat();

  const isUser = message.role === 'user';
  const isError = message.status === 'error';
  const isCancelled = message.status === 'cancelled';
  const isStreaming = message.isStreaming || message.id === streamingMessageId;
  const hasAttachments = message.attachments && message.attachments.length > 0;
  const canRetry = message.canRetry !== false && (isError || isCancelled);

  // Message copy state
  const [copied, setCopied] = useState(false);

  // Handle copy message
  const handleCopy = async () => {
    const success = await copyMessageContent(message.id);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Handle message rating
  const handleRate = async (rating) => {
    await rateMessage(message.id, rating);
  };

  // Handle retry
  const handleRetry = () => {
    retryMessage(message.id);
  };

  return (
    <div
      className={`
        flex gap-3 px-4 py-3
        ${isUser ? 'flex-row-reverse' : 'flex-row'}
        animate-fade-in-up
      `}
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-aura-500 flex items-center justify-center">
            <span className="text-white font-medium text-sm">U</span>
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-aura-500 to-olive-500 flex items-center justify-center shadow-sm">
            <span className="text-white font-bold text-xs">A</span>
          </div>
        )}
      </div>

      {/* Message content */}
      <div
        className={`
          flex flex-col gap-1.5 max-w-[85%]
          ${isUser ? 'items-end' : 'items-start'}
        `}
      >
        {/* Attachments (displayed above message for user) */}
        {hasAttachments && (
          <MessageAttachments attachments={message.attachments} isUser={isUser} />
        )}

        {/* Message bubble - only show if there's content or is streaming */}
        {(message.content || isStreaming) && (
          <div
            className={`
              px-4 py-3 rounded-2xl relative
              ${isUser
                ? 'bg-aura-500 text-white rounded-tr-md'
                : 'bg-surface-100 dark:bg-surface-700 text-surface-900 dark:text-surface-100 rounded-tl-md'
              }
              ${isError ? 'ring-2 ring-critical-500 ring-opacity-50' : ''}
              ${isCancelled ? 'opacity-60' : ''}
            `}
          >
            {isUser ? (
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            ) : isStreaming ? (
              <StreamingMessageContent content={message.content} />
            ) : (
              <MessageContent content={message.content} />
            )}

            {/* Streaming indicator */}
            {isStreaming && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-surface-200 dark:border-surface-600">
                <SparklesIcon className="w-4 h-4 text-olive-500 animate-pulse" />
                <span className="text-xs text-surface-500 dark:text-surface-400">
                  Generating response...
                </span>
                <button
                  onClick={cancelStream}
                  className="ml-auto p-1 rounded hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-400 hover:text-critical-500"
                  aria-label="Stop generating"
                >
                  <StopIcon className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Error indicator with retry */}
        {isError && (
          <div className="flex items-center gap-2 text-critical-500 dark:text-critical-400 text-xs">
            <ExclamationTriangleIcon className="w-4 h-4" />
            <span>{message.error || 'Failed to send'}</span>
            {canRetry && (
              <button
                onClick={handleRetry}
                className="flex items-center gap-1 px-2 py-1 rounded bg-critical-100 dark:bg-critical-900/30 hover:bg-critical-200 dark:hover:bg-critical-900/50 transition-colors"
              >
                <ArrowPathIcon className="w-3 h-3" />
                Retry
              </button>
            )}
          </div>
        )}

        {/* Cancelled indicator */}
        {isCancelled && (
          <div className="flex items-center gap-1.5 text-surface-400 dark:text-surface-500 text-xs">
            <StopIcon className="w-4 h-4" />
            <span>Response cancelled</span>
          </div>
        )}

        {/* Timestamp, token count, and actions */}
        <div
          className={`
            flex items-center gap-3 flex-wrap
            ${isUser ? 'flex-row-reverse' : 'flex-row'}
          `}
        >
          {/* Timestamp */}
          <span className="text-xs text-surface-400 dark:text-surface-500">
            {formatTimestamp(message.timestamp)}
          </span>

          {/* Token count (for assistant messages) */}
          {!isUser && message.tokenUsage && (
            <span className="text-xs text-surface-400 dark:text-surface-500">
              {message.tokenUsage.completionTokens || message.tokenUsage.totalTokens} tokens
            </span>
          )}

          {/* Model indicator */}
          {!isUser && message.modelId && (
            <span className="text-xs text-surface-400 dark:text-surface-500 px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-700">
              {formatModelId(message.modelId)}
            </span>
          )}

          {/* Assistant actions */}
          {!isUser && !isStreaming && message.content && (
            <div className="flex items-center gap-1">
              {/* Copy button */}
              <ActionButton
                icon={copied ? CheckIcon : ClipboardDocumentIcon}
                label={copied ? 'Copied!' : 'Copy'}
                onClick={handleCopy}
                active={copied}
              />

              {/* Rating buttons */}
              <FeedbackButton
                type="up"
                selected={message.rating === 'positive'}
                onClick={() => handleRate('positive')}
              />
              <FeedbackButton
                type="down"
                selected={message.rating === 'negative'}
                onClick={() => handleRate('negative')}
              />

              {/* Regenerate (only for last message) */}
              {isLast && (
                <ActionButton
                  icon={ArrowPathIcon}
                  label="Regenerate"
                  onClick={regenerateResponse}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * StreamingMessageContent - Message content with typing cursor animation
 */
function StreamingMessageContent({ content }) {
  return (
    <div className="text-sm space-y-3 markdown-content">
      {content ? (
        <>
          <MessageContent content={content} />
          <span className="inline-block w-2 h-4 bg-olive-500 animate-blink ml-0.5" />
        </>
      ) : (
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-4 bg-olive-500 animate-blink" />
        </div>
      )}
    </div>
  );
}

/**
 * MessageAttachments - Display attachments in a message
 */
function MessageAttachments({ attachments, isUser }) {
  return (
    <div className={`flex flex-wrap gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {attachments.map((attachment, index) => (
        <AttachmentThumbnail key={index} attachment={attachment} isUser={isUser} />
      ))}
    </div>
  );
}

/**
 * AttachmentThumbnail - Individual attachment display
 */
function AttachmentThumbnail({ attachment, isUser }) {
  const isImage = attachment.type?.startsWith('image/');

  // Format file size
  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isImage && attachment.preview) {
    return (
      <div className="relative group">
        <img
          src={attachment.preview}
          alt={attachment.name}
          className={`
            max-w-[200px] max-h-[150px] rounded-lg object-cover
            border-2
            ${isUser
              ? 'border-aura-400/50'
              : 'border-surface-200 dark:border-surface-600'
            }
          `}
        />
        <div className="absolute bottom-0 left-0 right-0 px-2 py-1 bg-black/60 rounded-b-lg opacity-0 group-hover:opacity-100 transition-opacity">
          <p className="text-xs text-white truncate">{attachment.name}</p>
        </div>
      </div>
    );
  }

  // Non-image file display
  return (
    <div
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg
        ${isUser
          ? 'bg-aura-400/30 text-white'
          : 'bg-surface-100 dark:bg-surface-600 text-surface-700 dark:text-surface-300'
        }
      `}
    >
      <DocumentIcon className="w-5 h-5 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-sm font-medium truncate max-w-[150px]">{attachment.name}</p>
        <p className="text-xs opacity-70">{formatSize(attachment.size)}</p>
      </div>
    </div>
  );
}

/**
 * DocumentIcon for file attachments
 */
function DocumentIcon({ className }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}

/**
 * MessageContent - Renders markdown-like content
 */
function MessageContent({ content }) {
  // Memoize parsed content to avoid re-parsing on every render
  const elements = useMemo(() => parseMarkdown(content), [content]);

  return (
    <div className="text-sm space-y-3 markdown-content">
      {elements}
    </div>
  );
}

/**
 * Parse markdown-like syntax into React elements
 */
function parseMarkdown(content) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let inCodeBlock = false;
  let codeContent = [];
  let codeLanguage = '';
  let inTable = false;
  let tableRows = [];
  let listItems = [];
  let listType = null;

  const flushList = () => {
    if (listItems.length > 0) {
      const ListTag = listType === 'ordered' ? 'ol' : 'ul';
      const listClass = listType === 'ordered'
        ? 'list-decimal list-inside space-y-1 ml-4'
        : 'list-disc list-inside space-y-1 ml-4';
      elements.push(
        <ListTag key={`list-${elements.length}`} className={listClass}>
          {listItems.map((item, i) => (
            <li key={i}>{parseInline(item)}</li>
          ))}
        </ListTag>
      );
      listItems = [];
      listType = null;
    }
  };

  const flushTable = () => {
    if (tableRows.length > 0) {
      elements.push(
        <div key={`table-${elements.length}`} className="overflow-x-auto my-3">
          <table className="min-w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-surface-200 dark:border-surface-600">
                {tableRows[0].map((cell, i) => (
                  <th
                    key={i}
                    className="px-3 py-2 text-left font-semibold text-surface-900 dark:text-surface-100"
                  >
                    {parseInline(cell.trim())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(2).map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-surface-100 dark:border-surface-700"
                >
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className="px-3 py-2 text-surface-700 dark:text-surface-300"
                    >
                      {parseInline(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block start/end
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        // Check if this is a mermaid diagram
        const isMermaid = codeLanguage === 'mermaid' ||
          codeContent[0]?.trim().match(/^(flowchart|sequenceDiagram|classDiagram|erDiagram|stateDiagram|graph|pie|gantt)/);

        if (isMermaid) {
          elements.push(
            <MermaidDiagram
              key={`mermaid-${elements.length}`}
              code={codeContent.join('\n')}
            />
          );
        } else {
          elements.push(
            <CodeBlock
              key={`code-${elements.length}`}
              code={codeContent.join('\n')}
              language={codeLanguage}
            />
          );
        }
        codeContent = [];
        codeLanguage = '';
        inCodeBlock = false;
      } else {
        flushList();
        flushTable();
        inCodeBlock = true;
        codeLanguage = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeContent.push(line);
      continue;
    }

    // Table row
    if (line.includes('|') && line.trim().startsWith('|')) {
      flushList();
      const cells = line.split('|').filter(c => c.trim() !== '');
      if (cells.length > 0) {
        // Skip separator row (contains only dashes)
        if (cells.every(c => /^[-:\s]+$/.test(c))) {
          tableRows.push(cells);
        } else {
          tableRows.push(cells);
        }
        inTable = true;
      }
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Headers
    if (line.startsWith('**') && line.endsWith('**') && !line.includes(' ')) {
      flushList();
      elements.push(
        <h4 key={`h-${elements.length}`} className="font-semibold text-surface-900 dark:text-surface-100 mt-3">
          {line.replace(/\*\*/g, '')}
        </h4>
      );
      continue;
    }

    // Bold headers (like **Current Status:**)
    if (line.match(/^\*\*[^*]+:\*\*$/)) {
      flushList();
      elements.push(
        <h4 key={`h-${elements.length}`} className="font-semibold text-surface-900 dark:text-surface-100 mt-2">
          {line.replace(/\*\*/g, '')}
        </h4>
      );
      continue;
    }

    // Unordered list
    if (line.match(/^[-*]\s/)) {
      if (listType !== 'unordered') {
        flushList();
        listType = 'unordered';
      }
      listItems.push(line.replace(/^[-*]\s/, ''));
      continue;
    }

    // Ordered list
    if (line.match(/^\d+\.\s/)) {
      if (listType !== 'ordered') {
        flushList();
        listType = 'ordered';
      }
      listItems.push(line.replace(/^\d+\.\s/, ''));
      continue;
    }

    // Regular paragraph
    flushList();
    if (line.trim()) {
      elements.push(
        <p key={`p-${elements.length}`} className="text-surface-700 dark:text-surface-300">
          {parseInline(line)}
        </p>
      );
    }
  }

  flushList();
  flushTable();

  return elements;
}

/**
 * Parse inline markdown (bold, italic, code, links)
 */
function parseInline(text) {
  const parts = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Inline code
    const codeMatch = remaining.match(/`([^`]+)`/);
    if (codeMatch && codeMatch.index === 0) {
      parts.push(
        <code
          key={key++}
          className="px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-600 text-surface-800 dark:text-surface-200 font-mono text-xs"
        >
          {codeMatch[1]}
        </code>
      );
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }

    // Bold
    const boldMatch = remaining.match(/\*\*([^*]+)\*\*/);
    if (boldMatch && boldMatch.index === 0) {
      parts.push(
        <strong key={key++} className="font-semibold">
          {boldMatch[1]}
        </strong>
      );
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }

    // Link [text](url)
    const linkMatch = remaining.match(/\[([^\]]+)\]\(([^)]+)\)/);
    if (linkMatch && linkMatch.index === 0) {
      parts.push(
        <a
          key={key++}
          href={linkMatch[2]}
          className="text-olive-600 dark:text-olive-400 hover:underline"
          target={linkMatch[2].startsWith('http') ? '_blank' : undefined}
          rel={linkMatch[2].startsWith('http') ? 'noopener noreferrer' : undefined}
        >
          {linkMatch[1]}
        </a>
      );
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }

    // Find next special character
    const nextSpecial = remaining.search(/[`*[]/);
    if (nextSpecial === -1) {
      parts.push(remaining);
      break;
    } else if (nextSpecial === 0) {
      // If we're here, the special char didn't match a pattern, treat as text
      parts.push(remaining[0]);
      remaining = remaining.slice(1);
    } else {
      parts.push(remaining.slice(0, nextSpecial));
      remaining = remaining.slice(nextSpecial);
    }
  }

  return parts.length === 1 ? parts[0] : parts;
}

/**
 * CodeBlock - Syntax-highlighted code block with copy button
 */
function CodeBlock({ code, language }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="relative group my-3">
      {/* Language badge */}
      {language && (
        <span className="absolute top-2 left-3 text-xs text-surface-400 dark:text-surface-500 font-mono">
          {language}
        </span>
      )}

      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="
          absolute top-2 right-2
          p-1.5 rounded-md
          bg-surface-200 dark:bg-surface-600
          hover:bg-surface-300 dark:hover:bg-surface-500
          text-surface-500 dark:text-surface-400
          opacity-0 group-hover:opacity-100
          transition-opacity duration-150
          focus:outline-none focus:ring-2 focus:ring-olive-500
        "
        aria-label={copied ? 'Copied!' : 'Copy code'}
      >
        {copied ? (
          <CheckIcon className="w-4 h-4 text-olive-500" />
        ) : (
          <ClipboardDocumentIcon className="w-4 h-4" />
        )}
      </button>

      {/* Code content */}
      <pre
        className={`
          overflow-x-auto
          p-4 ${language ? 'pt-8' : ''}
          rounded-lg
          bg-surface-800 dark:bg-surface-900
          text-surface-100
          font-mono text-xs
          leading-relaxed
        `}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * MermaidDiagram - Renders Mermaid diagram code with export options
 * Uses dynamic import to avoid loading mermaid (~1MB) until needed
 */
function MermaidDiagram({ code }) {
  const containerRef = useRef(null);
  const [rendered, setRendered] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [svgContent, setSvgContent] = useState('');

  useEffect(() => {
    let isMounted = true;

    const renderDiagram = async () => {
      if (!containerRef.current || rendered) return;

      try {
        setLoading(true);

        // Dynamic import - only loads mermaid when a diagram is detected
        const mermaid = await getMermaid();

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, code);

        if (isMounted) {
          setSvgContent(svg);
          setRendered(true);
          setError(null);
        }
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        if (isMounted) {
          setError(err.message);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    renderDiagram();

    return () => {
      isMounted = false;
    };
  }, [code, rendered]);

  const handleExportSVG = () => {
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'diagram.svg';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPNG = async () => {
    const svgElement = containerRef.current?.querySelector('svg');
    if (!svgElement) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    const svgData = new XMLSerializer().serializeToString(svgElement);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      canvas.width = img.width * 2;
      canvas.height = img.height * 2;
      ctx.scale(2, 2);
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);

      const pngUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = pngUrl;
      a.download = 'diagram.png';
      a.click();
      URL.revokeObjectURL(url);
    };

    img.src = url;
  };

  if (loading) {
    return (
      <div className="my-3 p-4 rounded-lg bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-2 text-surface-500 dark:text-surface-400">
          <div className="w-4 h-4 border-2 border-surface-300 dark:border-surface-600 border-t-aura-500 rounded-full animate-spin" />
          <span className="text-sm">Loading diagram...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-3 p-4 rounded-lg bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800">
        <p className="text-sm text-critical-600 dark:text-critical-400">
          Failed to render diagram: {error}
        </p>
        <pre className="mt-2 text-xs text-surface-600 dark:text-surface-400 overflow-x-auto">
          {code}
        </pre>
      </div>
    );
  }

  return (
    <div className="my-3 relative group">
      {/* Export buttons */}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <button
          onClick={handleExportSVG}
          className="px-2 py-1 text-xs rounded bg-surface-200 dark:bg-surface-700 hover:bg-surface-300 dark:hover:bg-surface-600 text-surface-600 dark:text-surface-300"
          title="Export as SVG"
        >
          SVG
        </button>
        <button
          onClick={handleExportPNG}
          className="px-2 py-1 text-xs rounded bg-surface-200 dark:bg-surface-700 hover:bg-surface-300 dark:hover:bg-surface-600 text-surface-600 dark:text-surface-300"
          title="Export as PNG"
        >
          PNG
        </button>
      </div>

      {/* Diagram container */}
      <div
        ref={containerRef}
        className="p-4 rounded-lg bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
    </div>
  );
}

/**
 * ActionButton - Small icon button for message actions
 */
function ActionButton({ icon: Icon, label, onClick, active = false }) {
  return (
    <button
      onClick={onClick}
      className={`
        p-1 rounded
        transition-colors duration-150
        focus:outline-none focus:ring-2 focus:ring-olive-500
        ${active
          ? 'text-olive-500 dark:text-olive-400'
          : 'text-surface-400 dark:text-surface-500 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
        }
      `}
      aria-label={label}
      title={label}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

/**
 * FeedbackButton - Thumbs up/down feedback
 */
function FeedbackButton({ type, selected, onClick }) {
  const Icon = type === 'up' ? HandThumbUpIcon : HandThumbDownIcon;

  return (
    <button
      onClick={onClick}
      className={`
        p-1 rounded
        transition-colors duration-150
        focus:outline-none focus:ring-2 focus:ring-olive-500
        ${selected
          ? 'text-olive-500 dark:text-olive-400 bg-olive-100 dark:bg-olive-900/30'
          : 'text-surface-400 dark:text-surface-500 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
        }
      `}
      aria-label={type === 'up' ? 'Helpful' : 'Not helpful'}
      aria-pressed={selected}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

/**
 * Format timestamp to relative time
 */
function formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format model ID for display
 */
function formatModelId(modelId) {
  if (!modelId) return '';

  // Extract model name from full ID
  const parts = modelId.split('/');
  const name = parts[parts.length - 1];

  // Shorten common model names
  const shortNames = {
    'claude-3-5-sonnet': 'Claude 3.5',
    'claude-3-sonnet': 'Claude 3',
    'claude-3-haiku': 'Haiku',
    'claude-3.5-sonnet-mock': 'Mock',
  };

  for (const [pattern, short] of Object.entries(shortNames)) {
    if (name.includes(pattern)) return short;
  }

  return name.length > 15 ? name.substring(0, 15) + '...' : name;
}
