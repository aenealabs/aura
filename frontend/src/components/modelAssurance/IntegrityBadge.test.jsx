import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';

import IntegrityBadge from './IntegrityBadge';

describe('IntegrityBadge', () => {
  test('verified state shows green check', () => {
    render(<IntegrityBadge state="verified" />);
    expect(screen.getByText('Integrity verified')).toBeDefined();
  });

  test('tampered state shows expected vs actual hash prefix', () => {
    render(
      <IntegrityBadge
        state="tampered"
        expected="abcdef0123456789abcdef0123456789"
        actual="ffffffffffffffffffffffffffffffff"
      />,
    );
    expect(screen.getByText(/Integrity FAILED/)).toBeDefined();
    expect(screen.getByText(/abcdef01/)).toBeDefined();
    expect(screen.getByText(/ffffffff/)).toBeDefined();
  });

  test('demo state surfaces unverified message', () => {
    render(<IntegrityBadge state="demo" />);
    expect(screen.getByText(/Demo mode \(integrity unverified\)/)).toBeDefined();
  });
});
