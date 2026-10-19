/**
 * Tests for the shared Tooltip (Radix Tooltip)
 *
 * - The trigger is keyboard-focusable, so help on an icon is reachable
 * - Focus shows the tooltip, linked to the trigger with aria-describedby
 * - Escape hides it
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect } from 'vitest';
import Tooltip from './Tooltip';

describe('Tooltip', () => {
  test('keyboard focus shows it, described for screen readers; Escape hides it', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Locked by compliance" delay={0}>
        <svg data-testid="lock" />
      </Tooltip>
    );
    await user.tab();
    const trigger = screen.getByTestId('lock').parentElement;
    expect(document.activeElement).toBe(trigger);
    const tip = await screen.findByRole('tooltip');
    expect(tip).toHaveTextContent('Locked by compliance');
    expect(trigger.getAttribute('aria-describedby')).toBe(tip.id);
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument());
  });
});
