/**
 * Tests for CKGEConsole's node context menu
 *
 * - Opens at the pointer as a named menu, with actions the node does not support disabled
 * - Choosing an action reports it and closes the menu; Escape closes it too
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';

vi.mock('./graph/KnowledgeGraph', () => ({ default: () => null }));
vi.mock('./graph/FileViewer', () => ({ default: () => null }));
vi.mock('./ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }));

import { NodeContextMenu } from './CKGEConsole';

const position = { x: 120, y: 80 };

describe('NodeContextMenu', () => {
  test('is a named menu with unsupported actions disabled', () => {
    render(
      <NodeContextMenu
        position={position}
        node={{ id: 'n1', label: 'AuthService', type: 'class' }}
        onAction={vi.fn()}
        onClose={vi.fn()}
      />
    );
    const menu = screen.getByRole('menu', { name: 'Actions for AuthService' });
    expect(menu).toBeInTheDocument();
    // No file path: only View References is available
    expect(screen.getByRole('menuitem', { name: 'View References' })).not.toHaveAttribute('aria-disabled');
    expect(screen.getByRole('menuitem', { name: 'View File' })).toHaveAttribute('aria-disabled', 'true');
  });

  test('choosing an action reports it and closes the menu', async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    const onClose = vi.fn();
    const node = { id: 'n2', label: 'auth.py', type: 'file', path: 'src/auth.py' };
    render(<NodeContextMenu position={position} node={node} onAction={onAction} onClose={onClose} />);

    await user.click(screen.getByRole('menuitem', { name: 'Copy Path' }));
    expect(onAction).toHaveBeenCalledWith('copyPath', node);
    expect(onClose).toHaveBeenCalled();
  });

  test('Escape closes it', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <NodeContextMenu
        position={position}
        node={{ id: 'n2', label: 'auth.py', type: 'file', path: 'src/auth.py' }}
        onAction={vi.fn()}
        onClose={onClose}
      />
    );
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});
