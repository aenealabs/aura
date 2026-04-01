/**
 * Project Aura - Tour Spotlight
 *
 * Overlay with spotlight cutout around the target element.
 * Creates a darkened backdrop with a highlighted area.
 */

import { useEffect, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';

const TourSpotlight = ({ target, padding = 8, borderRadius = 8 }) => {
  const [rect, setRect] = useState(null);

  // Get target element position
  useEffect(() => {
    if (!target) {
      setRect(null);
      return;
    }

    const element = document.querySelector(target);
    if (!element) {
      setRect(null);
      return;
    }

    const updateRect = () => {
      const elementRect = element.getBoundingClientRect();
      setRect({
        x: elementRect.x - padding,
        y: elementRect.y - padding,
        width: elementRect.width + padding * 2,
        height: elementRect.height + padding * 2,
      });
    };

    // Initial position
    updateRect();

    // Scroll element into view
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
      inline: 'center',
    });

    // Update on resize/scroll
    window.addEventListener('resize', updateRect);
    window.addEventListener('scroll', updateRect, true);

    return () => {
      window.removeEventListener('resize', updateRect);
      window.removeEventListener('scroll', updateRect, true);
    };
  }, [target, padding]);

  // SVG path for spotlight cutout
  const maskPath = useMemo(() => {
    if (!rect) return '';

    const { x, y, width, height } = rect;
    const r = borderRadius;

    // Create a path that covers the whole screen with a rounded rect hole
    return `
      M 0 0
      L 100vw 0
      L 100vw 100vh
      L 0 100vh
      Z
      M ${x + r} ${y}
      L ${x + width - r} ${y}
      Q ${x + width} ${y} ${x + width} ${y + r}
      L ${x + width} ${y + height - r}
      Q ${x + width} ${y + height} ${x + width - r} ${y + height}
      L ${x + r} ${y + height}
      Q ${x} ${y + height} ${x} ${y + height - r}
      L ${x} ${y + r}
      Q ${x} ${y} ${x + r} ${y}
      Z
    `;
  }, [rect, borderRadius]);

  // No spotlight for center placement (completion step)
  if (!target) {
    return createPortal(
      <div className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm pointer-events-none" />,
      document.body
    );
  }

  if (!rect) {
    return null;
  }

  return createPortal(
    <svg
      className="fixed inset-0 z-[90] pointer-events-none"
      style={{ width: '100vw', height: '100vh' }}
    >
      <defs>
        <mask id="tour-spotlight-mask">
          <rect fill="white" x="0" y="0" width="100%" height="100%" />
          <rect
            fill="black"
            x={rect.x}
            y={rect.y}
            width={rect.width}
            height={rect.height}
            rx={borderRadius}
            ry={borderRadius}
          />
        </mask>
      </defs>

      {/* Darkened overlay with spotlight hole */}
      <rect
        fill="rgba(0, 0, 0, 0.6)"
        x="0"
        y="0"
        width="100%"
        height="100%"
        mask="url(#tour-spotlight-mask)"
      />

      {/* Spotlight border glow */}
      <rect
        x={rect.x}
        y={rect.y}
        width={rect.width}
        height={rect.height}
        rx={borderRadius}
        ry={borderRadius}
        fill="none"
        stroke="rgba(59, 130, 246, 0.5)"
        strokeWidth="2"
        className="animate-pulse"
      />
    </svg>,
    document.body
  );
};

export default TourSpotlight;
