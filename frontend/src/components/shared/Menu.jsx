/**
 * Menu Component
 *
 * Accessible dropdown menu built on Radix Dropdown Menu and styled with Aura's tokens. Opens
 * from its trigger by click, Enter, Space, or the arrow keys; moves between items with the
 * arrow keys and type-ahead; closes on Escape or an outside click and returns focus to the
 * trigger. Screen readers hear a menu with menu items.
 *
 * @example
 * <Menu trigger={<button>Account</button>} side="top">
 *   <MenuItem onSelect={logout}>Sign out</MenuItem>
 * </Menu>
 *
 * @module components/shared/Menu
 */

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import PropTypes from 'prop-types';

const ITEM = `flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm cursor-pointer
  outline-none select-none transition-colors duration-150
  text-surface-700 dark:text-surface-300
  data-[highlighted]:bg-surface-50 dark:data-[highlighted]:bg-surface-700
  data-[disabled]:opacity-50 data-[disabled]:pointer-events-none`;

/**
 * @param {Object} props
 * @param {React.ReactElement} props.trigger - The element that opens the menu (a button)
 * @param {'top'|'bottom'|'left'|'right'} [props.side='bottom'] - Where the menu opens
 * @param {'start'|'center'|'end'} [props.align='start'] - Alignment against the trigger
 * @param {string} [props.className] - Extra classes for the menu panel
 * @param {React.ReactNode} props.children - MenuItem, MenuLabel, and MenuSeparator elements
 */
function Menu({ trigger, side = 'bottom', align = 'start', className = '', children }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side={side}
          align={align}
          sideOffset={8}
          className={`z-50 min-w-[200px] rounded-xl py-1 bg-white dark:bg-surface-800
            backdrop-blur-xl border border-white/50 dark:border-surface-700/50
            shadow-[var(--shadow-glass)] focus:outline-none ${className}`}
        >
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

Menu.propTypes = {
  trigger: PropTypes.element.isRequired,
  side: PropTypes.oneOf(['top', 'bottom', 'left', 'right']),
  align: PropTypes.oneOf(['start', 'center', 'end']),
  className: PropTypes.string,
  children: PropTypes.node.isRequired,
};

/**
 * A menu item. Pass `onSelect` for an action, or `asChild` with a link to navigate.
 * `tone="danger"` styles destructive actions such as signing out.
 */
export function MenuItem({ className = '', tone, ...props }) {
  const color = tone === 'danger'
    ? '!text-critical-600 dark:!text-critical-400 data-[highlighted]:!bg-critical-50/80 dark:data-[highlighted]:!bg-critical-900/20'
    : '';
  return <DropdownMenu.Item className={`${ITEM} ${color} ${className}`} {...props} />;
}

MenuItem.propTypes = {
  className: PropTypes.string,
  tone: PropTypes.oneOf(['danger']),
};

/** A non-interactive heading or block inside the menu. */
export function MenuLabel({ className = '', ...props }) {
  return <DropdownMenu.Label className={className} {...props} />;
}

MenuLabel.propTypes = { className: PropTypes.string };

/** A divider between groups of items. */
export function MenuSeparator({ className = '' }) {
  return (
    <DropdownMenu.Separator
      className={`my-1 h-px bg-surface-100/50 dark:bg-surface-700/30 ${className}`}
    />
  );
}

MenuSeparator.propTypes = { className: PropTypes.string };

export default Menu;
