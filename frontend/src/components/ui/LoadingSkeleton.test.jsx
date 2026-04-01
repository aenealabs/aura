import { render } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import {
  Skeleton,
  SkeletonText,
  SkeletonCircle,
  MetricCardSkeleton,
  ChartSkeleton,
  TableSkeleton,
  PageSkeleton,
  ActivityFeedSkeleton,
} from './LoadingSkeleton';

describe('Skeleton', () => {
  test('renders with default styles', () => {
    const { container } = render(<Skeleton />);

    expect(container.firstChild).toHaveClass('skeleton');
    expect(container.firstChild).toHaveClass('animate-pulse');
  });

  test('applies custom className', () => {
    const { container } = render(<Skeleton className="custom-class" />);

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('passes through additional props', () => {
    const { container } = render(<Skeleton data-testid="test-skeleton" />);

    expect(container.firstChild).toHaveAttribute('data-testid', 'test-skeleton');
  });
});

describe('SkeletonText', () => {
  test('renders correct number of lines', () => {
    const { container } = render(<SkeletonText lines={3} />);

    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons).toHaveLength(3);
  });

  test('defaults to 1 line', () => {
    const { container } = render(<SkeletonText />);

    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons).toHaveLength(1);
  });

  test('last line is shorter when multiple lines', () => {
    const { container } = render(<SkeletonText lines={3} />);

    const skeletons = container.querySelectorAll('.skeleton');
    // Last line should have 75% width
    expect(skeletons[2]).toHaveStyle({ width: '75%' });
  });

  test('applies custom className', () => {
    const { container } = render(<SkeletonText className="custom-text" />);

    expect(container.firstChild).toHaveClass('custom-text');
  });
});

describe('SkeletonCircle', () => {
  test('renders with circular shape', () => {
    const { container } = render(<SkeletonCircle />);

    expect(container.firstChild).toHaveClass('rounded-full');
  });

  test('defaults to medium size', () => {
    const { container } = render(<SkeletonCircle />);

    expect(container.firstChild).toHaveClass('w-10');
    expect(container.firstChild).toHaveClass('h-10');
  });

  test('applies small size', () => {
    const { container } = render(<SkeletonCircle size="sm" />);

    expect(container.firstChild).toHaveClass('w-8');
    expect(container.firstChild).toHaveClass('h-8');
  });

  test('applies large size', () => {
    const { container } = render(<SkeletonCircle size="lg" />);

    expect(container.firstChild).toHaveClass('w-12');
    expect(container.firstChild).toHaveClass('h-12');
  });

  test('applies extra-large size', () => {
    const { container } = render(<SkeletonCircle size="xl" />);

    expect(container.firstChild).toHaveClass('w-16');
    expect(container.firstChild).toHaveClass('h-16');
  });

  test('applies custom className', () => {
    const { container } = render(<SkeletonCircle className="custom-circle" />);

    expect(container.firstChild).toHaveClass('custom-circle');
  });
});

describe('MetricCardSkeleton', () => {
  test('renders card structure', () => {
    const { container } = render(<MetricCardSkeleton />);

    expect(container.firstChild).toHaveClass('glass-card');
  });

  test('includes multiple skeleton elements', () => {
    const { container } = render(<MetricCardSkeleton />);

    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(3);
  });

  test('applies custom className', () => {
    const { container } = render(<MetricCardSkeleton className="custom-card" />);

    expect(container.firstChild).toHaveClass('custom-card');
  });
});

describe('ChartSkeleton', () => {
  test('renders chart structure', () => {
    const { container } = render(<ChartSkeleton />);

    expect(container.firstChild).toHaveClass('glass-card');
  });

  test('includes chart bars', () => {
    const { container } = render(<ChartSkeleton />);

    // 7 bars in the chart
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(10);
  });

  test('applies custom className', () => {
    const { container } = render(<ChartSkeleton className="custom-chart" />);

    expect(container.firstChild).toHaveClass('custom-chart');
  });
});

describe('TableSkeleton', () => {
  test('renders table structure', () => {
    const { container } = render(<TableSkeleton />);

    expect(container.querySelector('table')).toBeInTheDocument();
  });

  test('renders correct number of rows by default', () => {
    const { container } = render(<TableSkeleton />);

    const rows = container.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(5);
  });

  test('renders specified number of rows', () => {
    const { container } = render(<TableSkeleton rows={3} />);

    const rows = container.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(3);
  });

  test('renders correct number of columns by default', () => {
    const { container } = render(<TableSkeleton />);

    const headerCells = container.querySelectorAll('thead th');
    expect(headerCells).toHaveLength(4);
  });

  test('renders specified number of columns', () => {
    const { container } = render(<TableSkeleton columns={6} />);

    const headerCells = container.querySelectorAll('thead th');
    expect(headerCells).toHaveLength(6);
  });

  test('includes header row', () => {
    const { container } = render(<TableSkeleton />);

    expect(container.querySelector('thead')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(<TableSkeleton className="custom-table" />);

    expect(container.firstChild).toHaveClass('custom-table');
  });
});

describe('ActivityFeedSkeleton', () => {
  test('renders feed structure', () => {
    const { container } = render(<ActivityFeedSkeleton />);

    expect(container.firstChild).toHaveClass('glass-card');
  });

  test('renders default 5 items', () => {
    const { container } = render(<ActivityFeedSkeleton />);

    // Each activity item has multiple skeletons
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(10);
  });

  test('renders specified count of items', () => {
    const { container } = render(<ActivityFeedSkeleton count={3} />);

    // Should render 3 activity items
    const dividers = container.querySelectorAll('.divide-y > div');
    expect(dividers).toHaveLength(3);
  });

  test('applies custom className', () => {
    const { container } = render(<ActivityFeedSkeleton className="custom-feed" />);

    expect(container.firstChild).toHaveClass('custom-feed');
  });
});

describe('PageSkeleton', () => {
  test('renders page structure', () => {
    const { container } = render(<PageSkeleton />);

    expect(container.firstChild).toHaveClass('p-6');
  });

  test('includes metric cards section', () => {
    const { container } = render(<PageSkeleton />);

    // Should have a grid for metric cards
    const grid = container.querySelector('.grid');
    expect(grid).toBeInTheDocument();
  });

  test('includes chart skeletons', () => {
    const { container } = render(<PageSkeleton />);

    // Should have multiple glass-card containers for charts
    const charts = container.querySelectorAll('.glass-card');
    expect(charts.length).toBeGreaterThan(2);
  });

  test('includes activity feed', () => {
    const { container } = render(<PageSkeleton />);

    // Activity feed has divide-y class
    const dividers = container.querySelector('.divide-y');
    expect(dividers).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(<PageSkeleton className="custom-page" />);

    expect(container.firstChild).toHaveClass('custom-page');
  });
});
