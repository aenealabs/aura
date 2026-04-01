/**
 * Project Aura - DiagramExportPanel Tests (ADR-060 Phase 4)
 *
 * Tests for multi-format diagram export panel component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';

// Mock ThemeContext
vi.mock('../../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

// Mock URL.createObjectURL and revokeObjectURL
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
global.URL.revokeObjectURL = vi.fn();

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

import DiagramExportPanel, {
  FormatCard,
  ExportOptions,
  EXPORT_FORMATS,
  base64ToBlob,
} from './DiagramExportPanel';

const SAMPLE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="blue" width="100" height="100"/></svg>';

describe('DiagramExportPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  describe('Rendering', () => {
    test('renders export panel with title', () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      expect(screen.getByText('Export Diagram')).toBeInTheDocument();
      expect(screen.getByText(/download your diagram/i)).toBeInTheDocument();
    });

    test('renders all format options', () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      expect(screen.getByText('SVG')).toBeInTheDocument();
      expect(screen.getByText('PNG')).toBeInTheDocument();
      expect(screen.getByText('PDF')).toBeInTheDocument();
      expect(screen.getByText('draw.io')).toBeInTheDocument();
    });

    test('SVG is selected by default', () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const downloadButton = screen.getByRole('button', { name: /download svg/i });
      expect(downloadButton).toBeInTheDocument();
    });
  });

  describe('Format Selection', () => {
    test('changes selected format when clicking format card', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));

      const downloadButton = screen.getByRole('button', { name: /download png/i });
      expect(downloadButton).toBeInTheDocument();
    });

    test('applies selected styles to active format', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      const pngCard = screen.getByText('PNG').closest('button');
      await user.click(pngCard);

      expect(pngCard).toHaveClass('border-aura-500');
    });
  });

  describe('Export Options', () => {
    test('shows options panel when expanded', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      // Select PNG to see scale options
      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));

      // Expand options
      await user.click(screen.getByText('Export Options'));

      expect(screen.getByText('Scale')).toBeInTheDocument();
    });

    test('shows scale options for PNG format', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));
      await user.click(screen.getByText('Export Options'));

      expect(screen.getByText('1x')).toBeInTheDocument();
      expect(screen.getByText('2x')).toBeInTheDocument();
    });

    test('shows background options for SVG format', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('Export Options'));

      expect(screen.getByText('Background')).toBeInTheDocument();
    });

    test('shows metadata toggle for SVG format', async () => {
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('Export Options'));

      expect(screen.getByText('Include metadata')).toBeInTheDocument();
    });
  });

  describe('SVG Export', () => {
    test('downloads SVG directly without server call', async () => {
      // Render first, then set up mocks for download
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} diagramName="test-diagram" />);

      // Mock click on anchor - set up AFTER render
      const clickSpy = vi.fn();
      const originalAppendChild = document.body.appendChild.bind(document.body);
      const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => {
        if (el.tagName === 'A') {
          el.click = clickSpy;
          return el;
        }
        return originalAppendChild(el);
      });
      const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /download svg/i }));

      expect(URL.createObjectURL).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();

      appendChildSpy.mockRestore();
      removeChildSpy.mockRestore();
    });
  });

  describe('Server Export', () => {
    test('calls server API for PNG export', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          contentBase64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ',
        }),
      });

      // Render first
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} diagramName="test" />);

      // Mock document operations AFTER render
      const originalAppendChild = document.body.appendChild.bind(document.body);
      const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => {
        if (el.tagName === 'A') {
          el.click = vi.fn();
          return el;
        }
        return originalAppendChild(el);
      });
      const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));
      await user.click(screen.getByRole('button', { name: /download png/i }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/v1/diagrams/export', expect.any(Object));
      });

      appendChildSpy.mockRestore();
      removeChildSpy.mockRestore();
    });

    test('shows error message on export failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: 'Export failed' }),
      });

      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));
      await user.click(screen.getByRole('button', { name: /download png/i }));

      await waitFor(() => {
        expect(screen.getByText(/export failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Disabled State', () => {
    test('disables download button when no SVG content', () => {
      render(<DiagramExportPanel svgContent="" />);

      const downloadButton = screen.getByRole('button', { name: /download/i });
      expect(downloadButton).toBeDisabled();
    });

    test('disables format cards during export', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

      render(<DiagramExportPanel svgContent={SAMPLE_SVG} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));
      await user.click(screen.getByRole('button', { name: /download png/i }));

      // Format cards should be disabled during export
      const pdfCard = screen.getByText('PDF').closest('button');
      expect(pdfCard).toBeDisabled();
    });
  });

  describe('Callbacks', () => {
    test('calls onExportStart when export begins', async () => {
      const onExportStart = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, contentBase64: 'dGVzdA==' }),
      });

      // Render first
      render(<DiagramExportPanel svgContent={SAMPLE_SVG} onExportStart={onExportStart} />);

      // Mock document operations AFTER render
      const originalAppendChild = document.body.appendChild.bind(document.body);
      const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => {
        if (el.tagName === 'A') {
          el.click = vi.fn();
          return el;
        }
        return originalAppendChild(el);
      });
      vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});

      const user = userEvent.setup();
      await user.click(screen.getByText('PNG'));
      await user.click(screen.getByRole('button', { name: /download png/i }));

      expect(onExportStart).toHaveBeenCalled();

      appendChildSpy.mockRestore();
    });
  });
});

describe('FormatCard', () => {
  const defaultProps = {
    format: EXPORT_FORMATS.svg,
    isSelected: false,
    onSelect: vi.fn(),
    isExporting: false,
    status: 'idle',
  };

  test('renders format name and description', () => {
    render(<FormatCard {...defaultProps} />);

    expect(screen.getByText('SVG')).toBeInTheDocument();
    expect(screen.getByText('Scalable vector graphics')).toBeInTheDocument();
  });

  test('applies selected styles when isSelected is true', () => {
    const { container } = render(<FormatCard {...defaultProps} isSelected={true} />);

    expect(container.querySelector('button')).toHaveClass('border-aura-500');
  });

  test('calls onSelect when clicked', async () => {
    const onSelect = vi.fn();
    render(<FormatCard {...defaultProps} onSelect={onSelect} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    expect(onSelect).toHaveBeenCalledWith('svg');
  });

  test('is disabled when isExporting is true', () => {
    render(<FormatCard {...defaultProps} isExporting={true} />);

    expect(screen.getByRole('button')).toBeDisabled();
  });

  test('shows check icon on success', () => {
    render(<FormatCard {...defaultProps} isSelected={true} status="success" />);

    // Check icon should be visible (CheckIcon from heroicons)
    const svg = document.querySelector('svg.text-green-500');
    expect(svg).toBeInTheDocument();
  });

  test('shows spinner icon when exporting', () => {
    render(<FormatCard {...defaultProps} isSelected={true} status="exporting" />);

    // Spinner should have animate-spin class
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });
});

describe('ExportOptions', () => {
  const defaultProps = {
    format: 'png',
    scale: 1,
    onScaleChange: vi.fn(),
    backgroundColor: null,
    onBackgroundColorChange: vi.fn(),
    includeMetadata: true,
    onIncludeMetadataChange: vi.fn(),
    padding: 20,
    onPaddingChange: vi.fn(),
  };

  test('renders options button', () => {
    render(<ExportOptions {...defaultProps} />);

    expect(screen.getByText('Export Options')).toBeInTheDocument();
  });

  test('expands when clicked', async () => {
    render(<ExportOptions {...defaultProps} />);

    const user = userEvent.setup();
    await user.click(screen.getByText('Export Options'));

    expect(screen.getByText('Scale')).toBeInTheDocument();
  });

  test('calls onScaleChange when scale button clicked', async () => {
    const onScaleChange = vi.fn();
    render(<ExportOptions {...defaultProps} onScaleChange={onScaleChange} />);

    const user = userEvent.setup();
    await user.click(screen.getByText('Export Options'));
    await user.click(screen.getByText('2x'));

    expect(onScaleChange).toHaveBeenCalledWith(2);
  });

  test('returns null when format has no options', () => {
    // draw.io format doesn't have scale or background options
    const { container } = render(<ExportOptions {...defaultProps} format="drawio" />);

    // Should still render the metadata toggle
    expect(screen.getByText('Export Options')).toBeInTheDocument();
  });
});

describe('base64ToBlob', () => {
  test('converts base64 string to Blob', () => {
    const base64 = btoa('Hello World');
    const blob = base64ToBlob(base64, 'text/plain');

    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe('text/plain');
  });

  test('creates blob with correct size', () => {
    const content = 'Test content';
    const base64 = btoa(content);
    const blob = base64ToBlob(base64, 'text/plain');

    expect(blob.size).toBe(content.length);
  });
});

describe('EXPORT_FORMATS', () => {
  test('contains all expected formats', () => {
    expect(EXPORT_FORMATS).toHaveProperty('svg');
    expect(EXPORT_FORMATS).toHaveProperty('png');
    expect(EXPORT_FORMATS).toHaveProperty('pdf');
    expect(EXPORT_FORMATS).toHaveProperty('drawio');
  });

  test('each format has required properties', () => {
    Object.values(EXPORT_FORMATS).forEach((format) => {
      expect(format).toHaveProperty('id');
      expect(format).toHaveProperty('label');
      expect(format).toHaveProperty('extension');
      expect(format).toHaveProperty('mimeType');
      expect(format).toHaveProperty('icon');
    });
  });
});
