/**
 * Project Aura - Tooltip Indicator
 *
 * Pulsing dot indicator that shows there's a tooltip available.
 * Used to highlight new or unfamiliar features.
 */

const TooltipIndicator = ({ show, size = 'sm', className = '' }) => {
  if (!show) return null;

  const sizeClasses = {
    xs: 'w-1.5 h-1.5',
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  return (
    <span
      className={`relative inline-flex ${className}`}
      aria-hidden="true"
    >
      {/* Ping animation */}
      <span
        className={`absolute inline-flex ${sizeClasses[size]} rounded-full bg-aura-400 opacity-75 animate-ping`}
      />
      {/* Solid dot */}
      <span
        className={`relative inline-flex ${sizeClasses[size]} rounded-full bg-aura-500`}
      />
    </span>
  );
};

export default TooltipIndicator;
