/**
 * Tooltip Component
 *
 * Reusable tooltip for contextual help and information, built on Radix Tooltip. It opens on
 * hover or keyboard focus (the trigger is focusable, so keyboard users can reach help on icons),
 * closes on Escape, and is linked to its trigger with aria-describedby so screen readers
 * announce it.
 *
 * @module components/shared/Tooltip
 */

import * as RadixTooltip from '@radix-ui/react-tooltip';
import PropTypes from 'prop-types';

/**
 * Tooltip - Displays contextual information on hover or focus
 *
 * @param {Object} props
 * @param {React.ReactNode} props.content - Tooltip content
 * @param {React.ReactNode} props.children - Trigger element
 * @param {'top' | 'bottom' | 'left' | 'right'} [props.position='top'] - Tooltip position
 * @param {number} [props.delay=200] - Show delay in ms
 * @param {string} [props.className] - Additional CSS classes for the trigger wrapper
 */
function Tooltip({ content, children, position = 'top', delay = 200, className = '' }) {
  return (
    <RadixTooltip.Provider delayDuration={delay}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>
          <span
            tabIndex={0}
            className={`relative inline-block rounded focus:outline-none focus-visible:ring-2
              focus-visible:ring-aura-500 ${className}`}
          >
            {children}
          </span>
        </RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            side={position}
            sideOffset={8}
            className="z-50 px-2 py-1.5 text-xs font-medium text-white bg-surface-900
              dark:bg-surface-100 dark:text-surface-900 rounded-lg shadow-lg whitespace-nowrap"
          >
            {content}
            <RadixTooltip.Arrow className="fill-surface-900 dark:fill-surface-100" />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}

Tooltip.propTypes = {
  content: PropTypes.node.isRequired,
  children: PropTypes.node.isRequired,
  position: PropTypes.oneOf(['top', 'bottom', 'left', 'right']),
  delay: PropTypes.number,
  className: PropTypes.string,
};

export default Tooltip;
