/**
 * Upgrade Prompt Component
 *
 * Displays feature comparison and upgrade CTAs.
 */

import { CheckCircleIcon, XCircleIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';

const EDITION_FEATURES = {
  community: {
    name: 'Community',
    price: 'Free',
    priceDetail: 'Apache 2.0',
    features: [
      { name: 'Basic GraphRAG', included: true },
      { name: 'Single Repository', included: true },
      { name: 'Vulnerability Scanning', included: true },
      { name: 'Basic HITL Approval', included: true },
      { name: 'Community Support', included: true },
      { name: 'Multi-Repository', included: false },
      { name: 'SSO/SAML Integration', included: false },
      { name: 'Audit Logging', included: false },
      { name: 'Priority Support', included: false },
      { name: 'Custom Integrations', included: false },
    ],
  },
  enterprise: {
    name: 'Enterprise',
    price: '$99',
    priceDetail: 'per user/month',
    features: [
      { name: 'Advanced GraphRAG', included: true },
      { name: 'Multi-Repository', included: true },
      { name: 'Autonomous Patching', included: true },
      { name: 'SSO/SAML + RBAC', included: true },
      { name: 'Full Audit Logging', included: true },
      { name: 'Priority Support (SLA)', included: true },
      { name: 'Custom Integrations', included: true },
      { name: 'Advanced Analytics', included: true },
      { name: 'Air-Gap Deployment', included: false },
      { name: 'FIPS 140-2', included: false },
    ],
  },
  enterprise_plus: {
    name: 'Enterprise Plus',
    price: 'Contact Sales',
    priceDetail: 'Custom pricing',
    features: [
      { name: 'Everything in Enterprise', included: true },
      { name: 'Air-Gap Deployment', included: true },
      { name: 'FIPS 140-2 Compliance', included: true },
      { name: 'Custom LLM Integration', included: true },
      { name: 'Compliance Reporting', included: true },
      { name: 'Dedicated Support Engineer', included: true },
      { name: 'White-Label Options', included: true },
      { name: 'On-Prem LLM Hosting', included: true },
      { name: 'Hardware Security Module', included: true },
      { name: 'Custom SLA (99.99%)', included: true },
    ],
  },
};

function FeatureList({ features }) {
  return (
    <ul className="space-y-2">
      {features.map((feature) => (
        <li
          key={feature.name}
          className={`flex items-center gap-2 text-sm ${
            feature.included
              ? 'text-surface-700 dark:text-surface-300'
              : 'text-surface-400 dark:text-surface-500'
          }`}
        >
          {feature.included ? (
            <CheckCircleIcon className="h-4 w-4 text-olive-500 flex-shrink-0" />
          ) : (
            <XCircleIcon className="h-4 w-4 text-surface-300 dark:text-surface-600 flex-shrink-0" />
          )}
          <span className={feature.included ? '' : 'line-through'}>
            {feature.name}
          </span>
        </li>
      ))}
    </ul>
  );
}

function EditionCard({ edition, editionKey, isCurrent, onUpgrade, onContactSales }) {
  const isEnterprisePlus = editionKey === 'enterprise_plus';

  return (
    <div
      className={`
        relative rounded-xl p-6
        ${isCurrent
          ? 'bg-surface-50 dark:bg-surface-700/30 border-2 border-surface-300 dark:border-surface-600'
          : isEnterprisePlus
            ? 'bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-2 border-amber-300 dark:border-amber-800'
            : 'bg-aura-50 dark:bg-aura-900/20 border-2 border-aura-200 dark:border-aura-800'
        }
      `}
    >
      {isCurrent && (
        <div className="absolute -top-3 left-4 px-2 py-0.5 bg-surface-600 dark:bg-surface-500 text-white text-xs font-medium rounded">
          Current Plan
        </div>
      )}

      <div className="mb-4">
        <h4 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          {edition.name}
        </h4>
        <div className="mt-1">
          <span className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            {edition.price}
          </span>
          {edition.priceDetail && (
            <span className="text-sm text-surface-500 dark:text-surface-400 ml-1">
              {edition.priceDetail}
            </span>
          )}
        </div>
      </div>

      <FeatureList features={edition.features} />

      <div className="mt-6">
        {isCurrent ? (
          <button
            disabled
            className="
              w-full py-2 px-4 rounded-lg
              bg-surface-200 dark:bg-surface-600
              text-surface-500 dark:text-surface-400
              font-medium text-sm
              cursor-not-allowed
            "
          >
            Current Plan
          </button>
        ) : isEnterprisePlus ? (
          <button
            onClick={onContactSales}
            className="
              w-full py-2 px-4 rounded-lg
              bg-gradient-to-r from-amber-500 to-orange-500
              hover:from-amber-600 hover:to-orange-600
              text-white font-medium text-sm
              transition-all duration-200
              flex items-center justify-center gap-2
            "
          >
            Contact Sales
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={() => onUpgrade?.(editionKey)}
            className="
              w-full py-2 px-4 rounded-lg
              bg-aura-600 hover:bg-aura-700
              text-white font-medium text-sm
              transition-colors duration-200
            "
          >
            Upgrade Now
          </button>
        )}
      </div>
    </div>
  );
}

export default function UpgradePrompt({
  currentEdition,
  onUpgrade,
  onContactSales,
}) {
  // Determine which editions to show
  const showCommunity = currentEdition === 'community';
  const showEnterprise = currentEdition === 'community' || currentEdition === 'enterprise';
  const showEnterprisePlus = true; // Always show as upgrade option

  const editions = [];
  if (showCommunity) {
    editions.push({ key: 'community', ...EDITION_FEATURES.community });
  }
  if (showEnterprise) {
    editions.push({ key: 'enterprise', ...EDITION_FEATURES.enterprise });
  }
  if (showEnterprisePlus && currentEdition !== 'enterprise_plus') {
    editions.push({ key: 'enterprise_plus', ...EDITION_FEATURES.enterprise_plus });
  }

  // If only showing Enterprise Plus, show as a banner instead
  if (editions.length === 1 && editions[0].key === 'enterprise_plus') {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 rounded-xl border border-amber-200 dark:border-amber-800 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-amber-900 dark:text-amber-100">
              Upgrade to Enterprise Plus
            </h3>
            <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
              Unlock GovCloud support, FIPS 140-2 compliance, air-gap deployment, and dedicated support.
            </p>
          </div>
          <button
            onClick={onContactSales}
            className="
              flex-shrink-0 py-2 px-4 rounded-lg
              bg-gradient-to-r from-amber-500 to-orange-500
              hover:from-amber-600 hover:to-orange-600
              text-white font-medium text-sm
              transition-all duration-200
              flex items-center gap-2
            "
          >
            Contact Sales
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6">
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-6">
        {currentEdition === 'community' ? 'Upgrade Your Edition' : 'Available Upgrades'}
      </h3>

      <div className={`grid gap-6 ${editions.length === 2 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
        {editions.map((edition) => (
          <EditionCard
            key={edition.key}
            edition={edition}
            editionKey={edition.key}
            isCurrent={edition.key === currentEdition}
            onUpgrade={onUpgrade}
            onContactSales={onContactSales}
          />
        ))}
      </div>

      <div className="mt-6 pt-4 border-t border-surface-200/50 dark:border-surface-700/30">
        <a
          href="https://aenealabs.com/pricing"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium flex items-center gap-1"
        >
          View full pricing details
          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}
