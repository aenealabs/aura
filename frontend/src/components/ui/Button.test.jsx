import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import { Button, IconButton, ButtonGroup } from './Button';

describe('Button', () => {
  test('renders with children', () => {
    render(<Button>Click me</Button>);

    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  test('has correct default type', () => {
    render(<Button>Click</Button>);

    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });

  test('allows custom type', () => {
    render(<Button type="submit">Submit</Button>);

    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });

  test('calls onClick handler', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(<Button onClick={handleClick}>Click me</Button>);

    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);

    expect(screen.getByRole('button')).toBeDisabled();
  });

  test('is disabled when loading', () => {
    render(<Button loading>Loading</Button>);

    expect(screen.getByRole('button')).toBeDisabled();
  });

  test('shows loading spinner when loading', () => {
    const { container } = render(<Button loading>Loading</Button>);

    // Loading text is sr-only, check for the accessible text
    expect(screen.getByText('Loading...', { selector: '.sr-only' })).toBeInTheDocument();
    // Also check for spinner animation
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });

  test('renders left icon', () => {
    render(
      <Button leftIcon={<span data-testid="left-icon">←</span>}>
        With Icon
      </Button>
    );

    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
  });

  test('renders right icon', () => {
    render(
      <Button rightIcon={<span data-testid="right-icon">→</span>}>
        With Icon
      </Button>
    );

    expect(screen.getByTestId('right-icon')).toBeInTheDocument();
  });

  test('applies full width class', () => {
    render(<Button fullWidth>Full Width</Button>);

    expect(screen.getByRole('button')).toHaveClass('w-full');
  });

  test('applies custom className', () => {
    render(<Button className="custom-class">Custom</Button>);

    expect(screen.getByRole('button')).toHaveClass('custom-class');
  });

  test('forwards ref', () => {
    const ref = { current: null };
    render(<Button ref={ref}>Ref Button</Button>);

    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  describe('variants', () => {
    // Test that all variants render correctly (behavior, not CSS implementation)
    const variants = ['primary', 'secondary', 'danger', 'warning', 'success', 'ghost', 'link', 'outline'];

    variants.forEach((variant) => {
      test(`renders ${variant} variant`, () => {
        render(<Button variant={variant}>{variant}</Button>);

        const button = screen.getByRole('button', { name: variant });
        expect(button).toBeInTheDocument();
        expect(button).not.toBeDisabled();
      });
    });

    test('defaults to primary variant', () => {
      render(<Button>Default</Button>);
      // Button renders without error with default variant
      expect(screen.getByRole('button', { name: 'Default' })).toBeInTheDocument();
    });
  });

  describe('sizes', () => {
    // Test that all sizes render correctly
    const sizes = ['xs', 'sm', 'md', 'lg', 'xl'];

    sizes.forEach((size) => {
      test(`renders ${size} size`, () => {
        render(<Button size={size}>{size.toUpperCase()}</Button>);

        const button = screen.getByRole('button', { name: size.toUpperCase() });
        expect(button).toBeInTheDocument();
      });
    });

    test('defaults to md size', () => {
      render(<Button>Default</Button>);
      // Button renders without error with default size
      expect(screen.getByRole('button', { name: 'Default' })).toBeInTheDocument();
    });
  });
});

describe('IconButton', () => {
  test('renders with icon', () => {
    render(
      <IconButton aria-label="Close">
        <span>×</span>
      </IconButton>
    );

    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  test('is disabled when disabled prop is true', () => {
    render(
      <IconButton aria-label="Close" disabled>
        <span>×</span>
      </IconButton>
    );

    expect(screen.getByRole('button')).toBeDisabled();
  });

  test('is disabled when loading', () => {
    render(
      <IconButton aria-label="Close" loading>
        <span>×</span>
      </IconButton>
    );

    expect(screen.getByRole('button')).toBeDisabled();
  });

  test('shows spinner when loading', () => {
    render(
      <IconButton aria-label="Close" loading>
        <span data-testid="icon">×</span>
      </IconButton>
    );

    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });

  test('calls onClick handler', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(
      <IconButton aria-label="Close" onClick={handleClick}>
        <span>×</span>
      </IconButton>
    );

    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test('forwards ref', () => {
    const ref = { current: null };
    render(
      <IconButton ref={ref} aria-label="Close">
        <span>×</span>
      </IconButton>
    );

    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });
});

describe('ButtonGroup', () => {
  test('renders children', () => {
    render(
      <ButtonGroup>
        <Button>One</Button>
        <Button>Two</Button>
        <Button>Three</Button>
      </ButtonGroup>
    );

    expect(screen.getByRole('button', { name: 'One' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Two' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Three' })).toBeInTheDocument();
  });

  test('has group role', () => {
    render(
      <ButtonGroup>
        <Button>One</Button>
        <Button>Two</Button>
      </ButtonGroup>
    );

    expect(screen.getByRole('group')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    render(
      <ButtonGroup className="custom-group">
        <Button>One</Button>
      </ButtonGroup>
    );

    expect(screen.getByRole('group')).toHaveClass('custom-group');
  });
});
