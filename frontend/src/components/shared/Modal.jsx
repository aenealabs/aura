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
 * @param {string} [props.panelClassName] - Replaces the panel's default look (background,
 *   radius, shadow), so an existing modal keeps its exact styling; position and size stay
 * @param {string} [props.className] - Extra classes for the panel
 * @param {string} [props.overlayClassName] - Classes for the backdrop
 * @param {string} [props.description] - Screen-reader description, when the content has none
 * @param {React.ReactNode} props.children - Panel content; include a `ModalTitle`
 */
function Modal({
  open,
  onClose,
  size = 'md',
  panelClassName = 'rounded-2xl bg-white dark:bg-surface-800 shadow-2xl',
  className = '',
  overlayClassName = 'bg-black/40 backdrop-blur-md',
  description,
  children,
}) {
  // Our modals open from app state, not a Dialog.Trigger, so Radix has no trigger to refocus on
  // close. Remember what had focus as the modal opens and return focus there.
  const returnFocusTo = useRef(null);

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose?.()}>
      <Dialog.Portal>
        <Dialog.Overlay className={`fixed inset-0 z-50 transition-opacity ${overlayClassName}`} />
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] ${SIZES[size] || SIZES.md}
            -translate-x-1/2 -translate-y-1/2 max-h-[calc(100vh-2rem)] overflow-y-auto
            focus:outline-none ${panelClassName} ${className}`}
          {...(description ? {} : { 'aria-describedby': undefined })}
          onOpenAutoFocus={() => { returnFocusTo.current = document.activeElement; }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusTo.current?.focus?.();
          }}
        >
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
  panelClassName: PropTypes.string,
  className: PropTypes.string,
  overlayClassName: PropTypes.string,
  description: PropTypes.string,
  children: PropTypes.node.isRequired,
};

/** The modal's visible title; also its accessible name. */
export const ModalTitle = Dialog.Title;
/** Optional visible description, linked for screen readers. */
export const ModalDescription = Dialog.Description;
/** Wrap a button with `asChild` to make it close the modal. */
export const ModalClose = Dialog.Close;

export default Modal;
