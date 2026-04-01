/**
 * Identity Provider Configuration Modal
 *
 * Multi-step wizard for configuring identity providers.
 * Steps: 1) Type Selection, 2) Configuration, 3) Attribute Mapping, 4) Group Mapping, 5) Test & Save
 *
 * ADR-054: Multi-IdP Authentication
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  IDP_TYPE_CONFIG,
  createIdentityProvider,
  updateIdentityProvider,
  testIdentityProvider,
} from '../../../services/identityProviderApi';
import { getProviderLogo } from '../../integrations/ProviderLogos';
import AttributeMappingSection from './AttributeMappingSection';
import GroupRoleMappingSection from './GroupRoleMappingSection';

// Steps
const STEPS = [
  { id: 'type', label: 'Provider Type' },
  { id: 'config', label: 'Configuration' },
  { id: 'attributes', label: 'Attribute Mapping' },
  { id: 'groups', label: 'Group Mapping' },
  { id: 'test', label: 'Test & Save' },
];

export default function IdPConfigModal({ isOpen, onClose, existingConfig, onSave, onError }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedType, setSelectedType] = useState(existingConfig?.type || '');
  const [config, setConfig] = useState({
    display_name: '',
    enabled: true,
    // LDAP fields
    server_url: '',
    bind_dn: '',
    bind_password: '',
    base_dn: '',
    user_filter: '(objectClass=person)',
    group_filter: '(objectClass=group)',
    username_attribute: 'sAMAccountName',
    email_attribute: 'mail',
    require_tls: true,
    verify_certificate: true,
    // SAML fields
    metadata_url: '',
    metadata_xml: '',
    entity_id: '',
    sso_url: '',
    certificate: '',
    sign_requests: true,
    encrypt_assertions: false,
    nameid_format: 'emailAddress',
    // OIDC fields
    issuer_url: '',
    client_id: '',
    client_secret: '',
    scopes: ['openid', 'profile', 'email'],
    response_type: 'code',
    // PingID fields
    environment_id: '',
    region: 'NA',
    // Cognito fields
    user_pool_id: '',
    app_client_id: '',
    aws_region: 'us-east-1',
    // Entra ID fields (OIDC-based)
    tenant_id: '',
    entra_client_id: '',
    entra_client_secret: '',
    entra_scopes: ['openid', 'profile', 'email', 'User.Read'],
    // Azure AD B2C fields
    b2c_tenant_name: '',
    b2c_policy_name: 'B2C_1_SignUpSignIn',
    b2c_client_id: '',
    b2c_client_secret: '',
    b2c_scopes: ['openid', 'profile', 'email'],
    ...existingConfig,
  });
  const [attributeMappings, setAttributeMappings] = useState(
    existingConfig?.attribute_mappings || [
      { source: 'email', target: 'email' },
      { source: 'given_name', target: 'first_name' },
      { source: 'family_name', target: 'last_name' },
    ]
  );
  const [groupMappings, setGroupMappings] = useState(
    existingConfig?.group_mappings || []
  );
  const [defaultRole, setDefaultRole] = useState(existingConfig?.default_role || 'viewer');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  // If editing, skip to config step
  useEffect(() => {
    if (existingConfig) {
      setCurrentStep(1);
      setSelectedType(existingConfig.type);
    }
  }, [existingConfig]);

  const handleTypeSelect = (type) => {
    setSelectedType(type);
  };

  const handleConfigChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
  };

  const validateConfig = () => {
    const newErrors = {};

    if (!config.display_name?.trim()) {
      newErrors.display_name = 'Display name is required';
    }

    switch (selectedType) {
      case 'ldap':
        if (!config.server_url) newErrors.server_url = 'Server URL is required';
        if (!config.bind_dn) newErrors.bind_dn = 'Bind DN is required';
        if (!config.bind_password && !existingConfig) newErrors.bind_password = 'Bind password is required';
        if (!config.base_dn) newErrors.base_dn = 'Base DN is required';
        break;
      case 'saml':
        if (!config.metadata_url && !config.metadata_xml) {
          newErrors.metadata_url = 'Metadata URL or XML is required';
        }
        break;
      case 'oidc':
        if (!config.issuer_url) newErrors.issuer_url = 'Issuer URL is required';
        if (!config.client_id) newErrors.client_id = 'Client ID is required';
        if (!config.client_secret && !existingConfig) newErrors.client_secret = 'Client secret is required';
        break;
      case 'pingid':
        if (!config.environment_id) newErrors.environment_id = 'Environment ID is required';
        if (!config.client_id) newErrors.client_id = 'Client ID is required';
        if (!config.client_secret && !existingConfig) newErrors.client_secret = 'Client secret is required';
        break;
      case 'cognito':
        if (!config.user_pool_id) newErrors.user_pool_id = 'User Pool ID is required';
        if (!config.app_client_id) newErrors.app_client_id = 'App Client ID is required';
        break;
      case 'entra_id':
        if (!config.tenant_id) newErrors.tenant_id = 'Tenant ID is required';
        if (!config.entra_client_id) newErrors.entra_client_id = 'Application (Client) ID is required';
        if (!config.entra_client_secret && !existingConfig) newErrors.entra_client_secret = 'Client secret is required';
        break;
      case 'azure_ad_b2c':
        if (!config.b2c_tenant_name) newErrors.b2c_tenant_name = 'Tenant name is required';
        if (!config.b2c_policy_name) newErrors.b2c_policy_name = 'Policy name is required';
        if (!config.b2c_client_id) newErrors.b2c_client_id = 'Application (Client) ID is required';
        if (!config.b2c_client_secret && !existingConfig) newErrors.b2c_client_secret = 'Client secret is required';
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (currentStep === 0 && !selectedType) {
      return;
    }
    if (currentStep === 1 && !validateConfig()) {
      return;
    }
    setCurrentStep((prev) => Math.min(prev + 1, STEPS.length - 1));
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, existingConfig ? 1 : 0));
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Save first if new, then test
      let providerId = existingConfig?.id;
      if (!providerId) {
        const saved = await handleSave(false);
        providerId = saved?.id;
      }
      if (providerId) {
        const result = await testIdentityProvider(providerId);
        setTestResult(result);
      }
    } catch (err) {
      setTestResult({ success: false, message: err.message || 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (closeAfter = true) => {
    setSaving(true);
    try {
      const payload = {
        type: selectedType,
        display_name: config.display_name,
        enabled: config.enabled,
        attribute_mappings: attributeMappings,
        group_mappings: groupMappings,
        default_role: defaultRole,
        // Include type-specific fields
        ...(selectedType === 'ldap' && {
          server_url: config.server_url,
          bind_dn: config.bind_dn,
          bind_password: config.bind_password,
          base_dn: config.base_dn,
          user_filter: config.user_filter,
          group_filter: config.group_filter,
          username_attribute: config.username_attribute,
          email_attribute: config.email_attribute,
          require_tls: config.require_tls,
          verify_certificate: config.verify_certificate,
        }),
        ...(selectedType === 'saml' && {
          metadata_url: config.metadata_url,
          metadata_xml: config.metadata_xml,
          entity_id: config.entity_id,
          sso_url: config.sso_url,
          certificate: config.certificate,
          sign_requests: config.sign_requests,
          encrypt_assertions: config.encrypt_assertions,
          nameid_format: config.nameid_format,
        }),
        ...(selectedType === 'oidc' && {
          issuer_url: config.issuer_url,
          client_id: config.client_id,
          client_secret: config.client_secret,
          scopes: config.scopes,
          response_type: config.response_type,
        }),
        ...(selectedType === 'pingid' && {
          environment_id: config.environment_id,
          client_id: config.client_id,
          client_secret: config.client_secret,
          region: config.region,
        }),
        ...(selectedType === 'cognito' && {
          user_pool_id: config.user_pool_id,
          app_client_id: config.app_client_id,
          aws_region: config.aws_region,
        }),
        ...(selectedType === 'entra_id' && {
          tenant_id: config.tenant_id,
          client_id: config.entra_client_id,
          client_secret: config.entra_client_secret,
          scopes: config.entra_scopes,
          // Construct issuer URL for Entra ID
          issuer_url: `https://login.microsoftonline.com/${config.tenant_id}/v2.0`,
        }),
        ...(selectedType === 'azure_ad_b2c' && {
          tenant_name: config.b2c_tenant_name,
          policy_name: config.b2c_policy_name,
          client_id: config.b2c_client_id,
          client_secret: config.b2c_client_secret,
          scopes: config.b2c_scopes,
          // Construct issuer URL for Azure AD B2C
          issuer_url: `https://${config.b2c_tenant_name}.b2clogin.com/${config.b2c_tenant_name}.onmicrosoft.com/${config.b2c_policy_name}/v2.0`,
        }),
      };

      let result;
      if (existingConfig?.id) {
        result = await updateIdentityProvider(existingConfig.id, payload);
      } else {
        result = await createIdentityProvider(payload);
      }

      if (closeAfter) {
        onSave(result);
      }
      return result;
    } catch (err) {
      onError?.(err.message || 'Failed to save provider');
      return null;
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const renderTypeSelection = () => (
    <div className="grid grid-cols-2 gap-4">
      {IDP_TYPE_CONFIG.map((type) => {
        const LogoComponent = getProviderLogo(type.id);
        const isSelected = selectedType === type.id;
        return (
          <button
            key={type.id}
            onClick={() => handleTypeSelect(type.id)}
            className={`
              p-4 rounded-xl border-2 text-left transition-all
              ${isSelected
                ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20 ring-2 ring-aura-500'
                : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
              }
            `}
          >
            <div className="flex items-center gap-3 mb-2">
              <LogoComponent className="w-10 h-10 rounded-lg flex-shrink-0" />
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                {type.name}
              </h3>
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              {type.description}
            </p>
          </button>
        );
      })}
    </div>
  );

  const renderConfigForm = () => {
    const inputClass = "w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500";
    const labelClass = "block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1";
    const errorClass = "text-xs text-critical-600 dark:text-critical-400 mt-1";

    return (
      <div className="space-y-4">
        {/* Common Fields */}
        <div>
          <label className={labelClass}>Display Name *</label>
          <input
            type="text"
            value={config.display_name}
            onChange={(e) => handleConfigChange('display_name', e.target.value)}
            placeholder="e.g., Corporate SSO"
            className={inputClass}
          />
          {errors.display_name && <p className={errorClass}>{errors.display_name}</p>}
        </div>

        {/* LDAP Fields */}
        {selectedType === 'ldap' && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Server URL *</label>
                <input
                  type="text"
                  value={config.server_url}
                  onChange={(e) => handleConfigChange('server_url', e.target.value)}
                  placeholder="ldaps://ldap.company.com:636"
                  className={inputClass}
                />
                {errors.server_url && <p className={errorClass}>{errors.server_url}</p>}
              </div>
              <div>
                <label className={labelClass}>Base DN *</label>
                <input
                  type="text"
                  value={config.base_dn}
                  onChange={(e) => handleConfigChange('base_dn', e.target.value)}
                  placeholder="dc=company,dc=com"
                  className={inputClass}
                />
                {errors.base_dn && <p className={errorClass}>{errors.base_dn}</p>}
              </div>
            </div>
            <div>
              <label className={labelClass}>Bind DN *</label>
              <input
                type="text"
                value={config.bind_dn}
                onChange={(e) => handleConfigChange('bind_dn', e.target.value)}
                placeholder="cn=aura-svc,ou=services,dc=company,dc=com"
                className={inputClass}
              />
              {errors.bind_dn && <p className={errorClass}>{errors.bind_dn}</p>}
            </div>
            <div>
              <label className={labelClass}>Bind Password *</label>
              <input
                type="password"
                value={config.bind_password}
                onChange={(e) => handleConfigChange('bind_password', e.target.value)}
                placeholder={existingConfig ? '(unchanged)' : 'Enter password'}
                className={inputClass}
              />
              {errors.bind_password && <p className={errorClass}>{errors.bind_password}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>User Filter</label>
                <input
                  type="text"
                  value={config.user_filter}
                  onChange={(e) => handleConfigChange('user_filter', e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Email Attribute</label>
                <input
                  type="text"
                  value={config.email_attribute}
                  onChange={(e) => handleConfigChange('email_attribute', e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.require_tls}
                  onChange={(e) => handleConfigChange('require_tls', e.target.checked)}
                  className="rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                />
                <span className="text-sm text-surface-700 dark:text-surface-300">Require TLS</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.verify_certificate}
                  onChange={(e) => handleConfigChange('verify_certificate', e.target.checked)}
                  className="rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                />
                <span className="text-sm text-surface-700 dark:text-surface-300">Verify Certificate</span>
              </label>
            </div>
          </>
        )}

        {/* SAML Fields */}
        {selectedType === 'saml' && (
          <>
            <div>
              <label className={labelClass}>Metadata URL</label>
              <input
                type="url"
                value={config.metadata_url}
                onChange={(e) => handleConfigChange('metadata_url', e.target.value)}
                placeholder="https://idp.example.com/metadata.xml"
                className={inputClass}
              />
              {errors.metadata_url && <p className={errorClass}>{errors.metadata_url}</p>}
              <p className="text-xs text-surface-500 mt-1">Or paste metadata XML below</p>
            </div>
            <div>
              <label className={labelClass}>Metadata XML</label>
              <textarea
                value={config.metadata_xml}
                onChange={(e) => handleConfigChange('metadata_xml', e.target.value)}
                placeholder="Paste SAML metadata XML here..."
                rows={4}
                className={inputClass}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>NameID Format</label>
                <select
                  value={config.nameid_format}
                  onChange={(e) => handleConfigChange('nameid_format', e.target.value)}
                  className={inputClass}
                >
                  <option value="emailAddress">Email Address</option>
                  <option value="persistent">Persistent</option>
                  <option value="transient">Transient</option>
                </select>
              </div>
              <div className="flex items-end gap-4 pb-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={config.sign_requests}
                    onChange={(e) => handleConfigChange('sign_requests', e.target.checked)}
                    className="rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                  />
                  <span className="text-sm text-surface-700 dark:text-surface-300">Sign Requests</span>
                </label>
              </div>
            </div>
          </>
        )}

        {/* OIDC Fields */}
        {selectedType === 'oidc' && (
          <>
            <div>
              <label className={labelClass}>Issuer URL *</label>
              <input
                type="url"
                value={config.issuer_url}
                onChange={(e) => handleConfigChange('issuer_url', e.target.value)}
                placeholder="https://accounts.google.com"
                className={inputClass}
              />
              {errors.issuer_url && <p className={errorClass}>{errors.issuer_url}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Client ID *</label>
                <input
                  type="text"
                  value={config.client_id}
                  onChange={(e) => handleConfigChange('client_id', e.target.value)}
                  className={inputClass}
                />
                {errors.client_id && <p className={errorClass}>{errors.client_id}</p>}
              </div>
              <div>
                <label className={labelClass}>Client Secret *</label>
                <input
                  type="password"
                  value={config.client_secret}
                  onChange={(e) => handleConfigChange('client_secret', e.target.value)}
                  placeholder={existingConfig ? '(unchanged)' : ''}
                  className={inputClass}
                />
                {errors.client_secret && <p className={errorClass}>{errors.client_secret}</p>}
              </div>
            </div>
          </>
        )}

        {/* PingID Fields */}
        {selectedType === 'pingid' && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Environment ID *</label>
                <input
                  type="text"
                  value={config.environment_id}
                  onChange={(e) => handleConfigChange('environment_id', e.target.value)}
                  className={inputClass}
                />
                {errors.environment_id && <p className={errorClass}>{errors.environment_id}</p>}
              </div>
              <div>
                <label className={labelClass}>Region</label>
                <select
                  value={config.region}
                  onChange={(e) => handleConfigChange('region', e.target.value)}
                  className={inputClass}
                >
                  <option value="NA">North America</option>
                  <option value="EU">Europe</option>
                  <option value="AP">Asia Pacific</option>
                  <option value="CA">Canada</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Client ID *</label>
                <input
                  type="text"
                  value={config.client_id}
                  onChange={(e) => handleConfigChange('client_id', e.target.value)}
                  className={inputClass}
                />
                {errors.client_id && <p className={errorClass}>{errors.client_id}</p>}
              </div>
              <div>
                <label className={labelClass}>Client Secret *</label>
                <input
                  type="password"
                  value={config.client_secret}
                  onChange={(e) => handleConfigChange('client_secret', e.target.value)}
                  placeholder={existingConfig ? '(unchanged)' : ''}
                  className={inputClass}
                />
                {errors.client_secret && <p className={errorClass}>{errors.client_secret}</p>}
              </div>
            </div>
          </>
        )}

        {/* Cognito Fields */}
        {selectedType === 'cognito' && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>User Pool ID *</label>
                <input
                  type="text"
                  value={config.user_pool_id}
                  onChange={(e) => handleConfigChange('user_pool_id', e.target.value)}
                  placeholder="us-east-1_xxxxxxxx"
                  className={inputClass}
                />
                {errors.user_pool_id && <p className={errorClass}>{errors.user_pool_id}</p>}
              </div>
              <div>
                <label className={labelClass}>AWS Region</label>
                <select
                  value={config.aws_region}
                  onChange={(e) => handleConfigChange('aws_region', e.target.value)}
                  className={inputClass}
                >
                  <option value="us-east-1">US East (N. Virginia)</option>
                  <option value="us-west-2">US West (Oregon)</option>
                  <option value="eu-west-1">EU (Ireland)</option>
                  <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                </select>
              </div>
            </div>
            <div>
              <label className={labelClass}>App Client ID *</label>
              <input
                type="text"
                value={config.app_client_id}
                onChange={(e) => handleConfigChange('app_client_id', e.target.value)}
                className={inputClass}
              />
              {errors.app_client_id && <p className={errorClass}>{errors.app_client_id}</p>}
            </div>
          </>
        )}

        {/* Entra ID Fields */}
        {selectedType === 'entra_id' && (
          <>
            <div>
              <label className={labelClass}>Tenant ID *</label>
              <input
                type="text"
                value={config.tenant_id}
                onChange={(e) => handleConfigChange('tenant_id', e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className={inputClass}
              />
              {errors.tenant_id && <p className={errorClass}>{errors.tenant_id}</p>}
              <p className="text-xs text-surface-500 mt-1">Find in Azure Portal → Microsoft Entra ID → Overview</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Application (Client) ID *</label>
                <input
                  type="text"
                  value={config.entra_client_id}
                  onChange={(e) => handleConfigChange('entra_client_id', e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className={inputClass}
                />
                {errors.entra_client_id && <p className={errorClass}>{errors.entra_client_id}</p>}
              </div>
              <div>
                <label className={labelClass}>Client Secret *</label>
                <input
                  type="password"
                  value={config.entra_client_secret}
                  onChange={(e) => handleConfigChange('entra_client_secret', e.target.value)}
                  placeholder={existingConfig ? '(unchanged)' : ''}
                  className={inputClass}
                />
                {errors.entra_client_secret && <p className={errorClass}>{errors.entra_client_secret}</p>}
              </div>
            </div>
            <div className="bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg p-3">
              <p className="text-sm text-aura-700 dark:text-aura-300">
                <strong>Redirect URI:</strong> Add this to your Entra ID app registration:
              </p>
              <code className="text-xs bg-aura-100 dark:bg-aura-900/30 px-2 py-1 rounded mt-1 block">
                {window.location.origin}/auth/callback/entra
              </code>
            </div>
          </>
        )}

        {/* Azure AD B2C Fields */}
        {selectedType === 'azure_ad_b2c' && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>B2C Tenant Name *</label>
                <input
                  type="text"
                  value={config.b2c_tenant_name}
                  onChange={(e) => handleConfigChange('b2c_tenant_name', e.target.value)}
                  placeholder="contosob2c"
                  className={inputClass}
                />
                {errors.b2c_tenant_name && <p className={errorClass}>{errors.b2c_tenant_name}</p>}
                <p className="text-xs text-surface-500 mt-1">Without .onmicrosoft.com suffix</p>
              </div>
              <div>
                <label className={labelClass}>Policy Name *</label>
                <input
                  type="text"
                  value={config.b2c_policy_name}
                  onChange={(e) => handleConfigChange('b2c_policy_name', e.target.value)}
                  placeholder="B2C_1_SignUpSignIn"
                  className={inputClass}
                />
                {errors.b2c_policy_name && <p className={errorClass}>{errors.b2c_policy_name}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Application (Client) ID *</label>
                <input
                  type="text"
                  value={config.b2c_client_id}
                  onChange={(e) => handleConfigChange('b2c_client_id', e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className={inputClass}
                />
                {errors.b2c_client_id && <p className={errorClass}>{errors.b2c_client_id}</p>}
              </div>
              <div>
                <label className={labelClass}>Client Secret *</label>
                <input
                  type="password"
                  value={config.b2c_client_secret}
                  onChange={(e) => handleConfigChange('b2c_client_secret', e.target.value)}
                  placeholder={existingConfig ? '(unchanged)' : ''}
                  className={inputClass}
                />
                {errors.b2c_client_secret && <p className={errorClass}>{errors.b2c_client_secret}</p>}
              </div>
            </div>
            <div className="bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg p-3">
              <p className="text-sm text-aura-700 dark:text-aura-300">
                <strong>Redirect URI:</strong> Add this to your B2C app registration:
              </p>
              <code className="text-xs bg-aura-100 dark:bg-aura-900/30 px-2 py-1 rounded mt-1 block">
                {window.location.origin}/auth/callback/b2c
              </code>
            </div>
          </>
        )}
      </div>
    );
  };

  const renderTestStep = () => (
    <div className="space-y-6">
      <div className="text-center py-4">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-2">
          Test Your Configuration
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Test the connection to verify your settings before saving.
        </p>
      </div>

      <div className="flex justify-center">
        <button
          onClick={handleTest}
          disabled={testing}
          className="flex items-center gap-2 px-6 py-3 bg-aura-600 text-white font-medium rounded-xl hover:bg-aura-700 disabled:opacity-50 transition-colors"
        >
          {testing ? (
            <>
              <ArrowPathIcon className="h-5 w-5 animate-spin" />
              Testing Connection...
            </>
          ) : (
            <>
              <ArrowPathIcon className="h-5 w-5" />
              Test Connection
            </>
          )}
        </button>
      </div>

      {testResult && (
        <div
          className={`
            flex items-center gap-3 p-4 rounded-lg
            ${testResult.success
              ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
              : 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
            }
          `}
        >
          {testResult.success ? (
            <CheckCircleIcon className="h-6 w-6 text-olive-600 dark:text-olive-400" />
          ) : (
            <ExclamationCircleIcon className="h-6 w-6 text-critical-600 dark:text-critical-400" />
          )}
          <div className="flex-1">
            <p className="font-medium">{testResult.message}</p>
            {testResult.latency_ms && (
              <p className="text-sm opacity-75">Response time: {testResult.latency_ms}ms</p>
            )}
          </div>
        </div>
      )}

      <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
        <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-2">
          Configuration Summary
        </h4>
        <dl className="text-sm space-y-1">
          <div className="flex justify-between">
            <dt className="text-surface-500 dark:text-surface-400">Provider Type</dt>
            <dd className="font-medium text-surface-900 dark:text-surface-100 capitalize">{selectedType}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-surface-500 dark:text-surface-400">Display Name</dt>
            <dd className="font-medium text-surface-900 dark:text-surface-100">{config.display_name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-surface-500 dark:text-surface-400">Attribute Mappings</dt>
            <dd className="font-medium text-surface-900 dark:text-surface-100">{attributeMappings.length}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-surface-500 dark:text-surface-400">Group Mappings</dt>
            <dd className="font-medium text-surface-900 dark:text-surface-100">{groupMappings.length}</dd>
          </div>
        </dl>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            {existingConfig ? 'Edit Identity Provider' : 'Add Identity Provider'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Progress Steps */}
        <div className="px-4 py-3 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const isActive = index === currentStep;
              const isCompleted = index < currentStep;
              const isDisabled = existingConfig && index === 0;
              return (
                <div key={step.id} className="flex items-center">
                  <div className="flex items-center gap-2">
                    <div
                      className={`
                        w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors
                        ${isCompleted
                          ? 'bg-aura-600 text-white'
                          : isActive
                            ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 ring-2 ring-aura-500'
                            : 'bg-surface-100 dark:bg-surface-700 text-surface-500'
                        }
                        ${isDisabled ? 'opacity-50' : ''}
                      `}
                    >
                      {isCompleted ? <CheckIcon className="h-4 w-4" /> : index + 1}
                    </div>
                    <span className={`text-sm hidden sm:block ${isActive ? 'font-medium text-surface-900 dark:text-surface-100' : 'text-surface-500'}`}>
                      {step.label}
                    </span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div className={`w-8 sm:w-16 h-0.5 mx-2 ${isCompleted ? 'bg-aura-500' : 'bg-surface-200 dark:bg-surface-700'}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {currentStep === 0 && renderTypeSelection()}
          {currentStep === 1 && renderConfigForm()}
          {currentStep === 2 && (
            <AttributeMappingSection
              mappings={attributeMappings}
              onChange={setAttributeMappings}
            />
          )}
          {currentStep === 3 && (
            <GroupRoleMappingSection
              mappings={groupMappings}
              onChange={setGroupMappings}
              defaultRole={defaultRole}
              onDefaultRoleChange={setDefaultRole}
            />
          )}
          {currentStep === 4 && renderTestStep()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={handleBack}
            disabled={currentStep === 0 || (existingConfig && currentStep === 1)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            {currentStep < STEPS.length - 1 ? (
              <button
                onClick={handleNext}
                disabled={currentStep === 0 && !selectedType}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next
                <ArrowRightIcon className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={() => handleSave(true)}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
              >
                {saving ? (
                  <>
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckIcon className="h-4 w-4" />
                    Save Provider
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
