/**
 * Tests for the shared Modal (Radix Dialog)
 *
 * - Labelled dialog role for screen readers
 * - Focus moves inside on open and stays trapped while tabbing
 * - Escape and the close button dismiss it
 * - Focus returns to the opening element on close
 */

import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import Modal, { ModalTitle, ModalClose } from './Modal';

function Harness({ onClose = () => {} }) {
  const [open, setOpen] = useState(false);
  const close = () => { onClose(); setOpen(false); };
  return (
    <>
      <button onClick={() => setOpen(true)}>Open settings</button>
      <Modal open={open} onClose={close}>
        <ModalTitle>Trust settings</ModalTitle>
        <input aria-label="First field" />
        <ModalClose asChild><button>Done</button></ModalClose>
      </Modal>
    </>
  );
}

describe('Modal', () => {
  test('is a labelled dialog and moves focus inside when it opens', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: 'Open settings' }));
    const dialog = screen.getByRole('dialog', { name: 'Trust settings' });
    expect(dialog).toBeInTheDocument();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  test('keeps keyboard focus inside while tabbing', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: 'Open settings' }));
    const dialog = screen.getByRole('dialog');
    for (let i = 0; i < 4; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  test('closes on Escape and returns focus to the opener', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'Open settings' });
    await user.click(opener);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  test('a close button inside dismisses it', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: 'Open settings' }));
    await user.click(screen.getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('a dialog opened from inside another stacks: Escape closes only the inner one', async () => {
    const user = userEvent.setup();
    function Nested() {
      const [inner, setInner] = useState(false);
      return (
        <Modal open onClose={() => {}}>
          <ModalTitle>Capability details</ModalTitle>
          <button onClick={() => setInner(true)}>Edit permissions</button>
          <Modal open={inner} onClose={() => setInner(false)}>
            <ModalTitle>Edit permissions</ModalTitle>
            <input aria-label="Permission" />
          </Modal>
        </Modal>
      );
    }
    render(<Nested />);
    await user.click(screen.getByRole('button', { name: 'Edit permissions' }));
    const innerDialog = screen.getByRole('dialog', { name: 'Edit permissions' });
    await user.click(screen.getByRole('textbox', { name: 'Permission' }));
    expect(innerDialog).toBeInTheDocument(); // clicking inside the inner dialog keeps it open
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Edit permissions' })).not.toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Capability details' })).toBeInTheDocument();
  });
});

