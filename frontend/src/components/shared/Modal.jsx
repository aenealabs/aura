/**
 * Modal Component
 *
 * Accessible dialog built on Radix Dialog and styled with Aura's tokens. It traps keyboard
 * focus inside while open, closes on Escape or a backdrop click, returns focus to the element
 * that opened it, and labels itself for screen readers from `ModalTitle`.
 *
 * @example
 * <Modal open={isOpen} onClose={close} size="lg">
 *   <ModalTitle className="text-lg font-semibold">Modify action</ModalTitle>
 *   ...
 * </Modal>
 *
 * @module components/shared/Modal
 */

import { useRef } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import PropTypes from 'prop-types';

// Where the panel sits: centered dialog, bottom sheet, or right-hand drawer
const PLACEMENTS = {
  center: (size) => `left-1/2 top-1/2 w-[calc(100%-2rem)] ${size} -translate-x-1/2 -translate-y-1/2
    max-h-[calc(100vh-2rem)]`,
  bottom: () => 'inset-x-0 bottom-0 max-h-[80vh]',
  right: (size) => `inset-y-0 right-0 h-full w-full ${size}`,
  full: () => 'inset-0',
};

// The element to refocus when the modal closes: whatever had focus as it opened, except that a
// menu item (a menu action that opens this modal) is about to unmount with its menu, so use the
// button that opened the menu instead. Radix labels each menu with its trigger's id.
function focusReturnTarget() {
  const active = document.activeElement;
  const menu = active?.closest?.('[role="menu"]');
  const trigger = menu && document.getElementById(menu.getAttribute('aria-labelledby'));
  return trigger || active;
}

const SIZES = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

/**
 * @param {Object} props
 * @param {boolean} props.open - Whether the modal is shown
 * @param {function} props.onClose - Called when the user dismisses it (Escape, backdrop, close)
 * @param {'sm'|'md'|'lg'|'xl'} [props.size='md'] - Maximum width
 * @param {'center'|'bottom'|'right'|'full'} [props.placement='center'] - Dialog, bottom sheet,
 *   right-hand drawer, or full screen
 * @param {string} [props.panelClassName] - Replaces the panel's default look (background,
 *   radius, shadow), so an existing modal keeps its exact styling; position and size stay
 * @param {string} [props.className] - Extra classes for the panel
 * @param {string} [props.overlayClassName] - Classes for the backdrop
 * @param {string} [props.description] - Screen-reader description, when the content has none
 * @param {string} [props.label] - Screen-reader title, for a dialog with no visible heading
 * @param {boolean} [props.closeOnOutsideClick=true] - false keeps it open on a backdrop click
 *   (Escape and its own buttons still close it)
 * @param {React.RefObject} [props.initialFocusRef] - Element to focus on open (default: the
 *   first focusable element)
 * @param {React.ReactNode} props.children - Panel content; include a `ModalTitle`
 *
 * Other props (id, data-testid, aria-labelledby) are passed to the panel.
 */
function Modal({
  open,
  onClose,
  size = 'md',
  placement = 'center',
  panelClassName = 'rounded-2xl bg-white dark:bg-surface-800 shadow-2xl',
  className = '',
  overlayClassName = 'bg-black/40 backdrop-blur-md',
  description,
  label,
  closeOnOutsideClick = true,
  initialFocusRef,
  children,
  ...rest
}) {
  // Our modals open from app state, not a Dialog.Trigger, so Radix has no trigger to refocus on
  // close. Remember what had focus as the modal opens and return focus there.
  const returnFocusTo = useRef(null);

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose?.()}>
      <Dialog.Portal>
        <Dialog.Overlay
          data-modal-overlay=""
          className={`fixed inset-0 z-50 transition-opacity ${overlayClassName}`}
        />
        <Dialog.Content
          className={`fixed z-50 ${(PLACEMENTS[placement] || PLACEMENTS.center)(SIZES[size] || SIZES.md)}
            overflow-y-auto focus:outline-none ${panelClassName} ${className}`}
          aria-modal="true"
          {...(description ? {} : { 'aria-describedby': undefined })}
          {...rest}
          onOpenAutoFocus={(event) => {
            returnFocusTo.current = focusReturnTarget();
            if (initialFocusRef?.current) {
              event.preventDefault();
              initialFocusRef.current.focus();
            }
          }}
          {...(closeOnOutsideClick ? {} : { onInteractOutside: (event) => event.preventDefault() })}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusTo.current?.focus?.();
          }}
        >
          {label && <Dialog.Title className="sr-only">{label}</Dialog.Title>}
          {description && <Dialog.Description className="sr-only">{description}</Dialog.Description>}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

Modal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl']),
  placement: PropTypes.oneOf(['center', 'bottom', 'right', 'full']),
  panelClassName: PropTypes.string,
  className: PropTypes.string,
  overlayClassName: PropTypes.string,
  description: PropTypes.string,
  label: PropTypes.string,
  closeOnOutsideClick: PropTypes.bool,
  initialFocusRef: PropTypes.shape({ current: PropTypes.any }),
  children: PropTypes.node.isRequired,
};

/** The modal's visible title; also its accessible name. */
export const ModalTitle = Dialog.Title;
/**
 * Optional visible description. Give it an id and pass the same id as the Modal's
 * `aria-describedby` so screen readers link it (or use the Modal's `description` prop).
 */
export const ModalDescription = Dialog.Description;
/** Wrap a button with `asChild` to make it close the modal. */
export const ModalClose = Dialog.Close;

export default Modal;
