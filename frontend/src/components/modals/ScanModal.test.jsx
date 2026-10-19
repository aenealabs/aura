/**
 * Tests for ScanModal's repository picker
 *
 * - The picker is a menu button named by its label and current choice
 * - Repositories are radio options; choosing one updates the button and closes the menu
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import ScanModal from './ScanModal';

vi.mock('../../services/repositoryApi', () => ({
  listRepositories: vi.fn().mockResolvedValue([
    { repository_id: 'r1', name: 'aura-core', provider: 'github', branch: 'main' },
    { repository_id: 'r2', name: 'aura-web', provider: 'github', branch: 'develop' },
  ]),
}));

describe('ScanModal repository picker', () => {
  test('lists repositories as radio options and selects the one chosen', async () => {
    const user = userEvent.setup();
    render(<ScanModal isOpen onClose={vi.fn()} onScanStart={vi.fn()} />);

    const picker = await screen.findByRole('button', { name: /Target Repository/ });
    await user.click(picker);
    const options = screen.getAllByRole('menuitemradio');
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringContaining('aura-core'),
      expect.stringContaining('aura-web'),
    ]);

    await user.click(screen.getByRole('menuitemradio', { name: /aura-web/ }));
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(picker).toHaveAccessibleName(expect.stringContaining('aura-web'));
    expect(picker).toHaveFocus();
  });
});
