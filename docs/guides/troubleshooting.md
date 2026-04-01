# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Aura Platform.

---

## Quick Diagnostics

### Platform Health Check

1. Navigate to the **Dashboard**
2. Check the **System Health** widget
3. Look for any red or yellow indicators
4. Click for component-level details

### Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| **Healthy** | All systems operational | None |
| **Degraded** | Partial functionality | Monitor, check logs |
| **Unhealthy** | Significant issues | Contact support |

---

## Authentication Issues

### Cannot Sign In

**Symptoms**: Login fails, redirects back to login page

**Solutions**:

1. **Clear browser cache and cookies**
2. **Check your credentials** are correct
3. **Verify account is active** with your administrator
4. **Try a different browser** to rule out browser issues
5. **Check SSO configuration** if using SSO

### Session Expired

**Symptoms**: Suddenly logged out, actions fail

**Solutions**:

1. **Refresh the page** to trigger re-authentication
2. **Sign in again** if refresh doesn't work
3. **Check session timeout settings** with your admin

### Permission Denied

**Symptoms**: 403 errors, actions blocked

**Solutions**:

1. **Verify your role** has required permissions
2. **Check if action requires admin** privileges
3. **Contact your administrator** for role adjustment

---

## Agent Issues

### Agents Not Running

**Symptoms**: Jobs stuck in QUEUED, no agent activity

**Possible Causes**:

| Cause | Check | Solution |
|-------|-------|----------|
| Deployment mode issue | Settings > Orchestrator | Restart agent pool |
| Resource exhaustion | Dashboard > Agents | Scale up or wait |
| Configuration error | Agent logs | Review and fix config |

**Solutions**:

1. **Check agent status** in Agents > Registry
2. **Review recent changes** to configuration
3. **Check deployment mode** is correctly set
4. **Wait for cool-down** if mode was recently changed

### Agent Task Failures

**Symptoms**: Jobs fail repeatedly, error in results

**Solutions**:

1. **View task logs**:
   - Navigate to the failed job
   - Click **View Logs**
   - Look for error messages

2. **Common errors and fixes**:

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| `LLM timeout` | High load or API issue | Retry later |
| `Context too large` | File too big | Split into smaller files |
| `Invalid input` | Malformed request | Check input data |
| `Rate limited` | Too many requests | Wait and retry |

### Slow Agent Performance

**Symptoms**: Tasks take longer than expected

**Solutions**:

1. **Check semantic cache hit rate**:
   - Low hit rate = more LLM calls
   - Review cache settings

2. **Review task complexity**:
   - Large repositories take longer
   - Consider incremental scans

3. **Check deployment mode**:
   - On-Demand has cold start delay
   - Consider Warm Pool for faster response

---

## Vulnerability Scanning Issues

### Scan Not Starting

**Symptoms**: Scan button clicked but nothing happens

**Solutions**:

1. **Check repository connection** is active
2. **Verify permissions** to the repository
3. **Check for running scans** (one at a time)
4. **Review agent availability**

### Incomplete Scan Results

**Symptoms**: Expected findings not appearing

**Possible Causes**:

| Cause | Check | Solution |
|-------|-------|----------|
| File type not supported | Supported extensions | Request support |
| Files excluded | Exclusion settings | Review .gitignore |
| Parsing errors | Scan logs | Check file syntax |

### False Positives

**Symptoms**: Findings that aren't real vulnerabilities

**Solutions**:

1. **Report the false positive** via the finding details
2. **Review the code context** - sometimes requires understanding
3. **Check if pattern is common** in your codebase
4. **Request tuning** from your administrator

---

## Approval Workflow Issues

### Approval Not Appearing

**Symptoms**: Expected approval not in queue

**Solutions**:

1. **Check autonomy policy**:
   - Navigate to Settings > HITL
   - Verify HITL is enabled
   - Check severity thresholds

2. **Verify sandbox testing completed**:
   - Approvals appear after sandbox
   - Check sandbox status

3. **Check guardrails**:
   - Some operations always need approval
   - Verify operation type

### Cannot Approve/Reject

**Symptoms**: Approve/Reject buttons don't work

**Solutions**:

1. **Check your permissions**:
   - Approvers need specific role
   - Contact admin if missing

2. **Verify approval hasn't expired**:
   - Check expiration time
   - Request new approval if expired

3. **Check minimum approvers**:
   - May need multiple approvers
   - Coordinate with team

### Approval Notifications Not Received

**Symptoms**: No email/Slack notifications

**Solutions**:

1. **Check notification settings**:
   - Navigate to Settings > HITL
   - Verify notifications enabled

2. **Verify contact information**:
   - Correct email address
   - Slack channel configured

3. **Check spam/junk folders**

4. **Integration mode**:
   - Defense mode blocks external notifications
   - Use Dashboard instead

---

## Environment Issues

### Cannot Create Environment

**Symptoms**: Environment creation fails

**Possible Causes**:

| Cause | Error Message | Solution |
|-------|---------------|----------|
| Quota exceeded | "Quota limit reached" | Terminate unused envs |
| Budget exceeded | "Budget exceeded" | Wait for reset or request increase |
| HITL required | "Approval required" | Wait for approval |
| Template error | "Template validation failed" | Use different template |

### Environment Stuck Provisioning

**Symptoms**: Environment stays in PROVISIONING state

**Solutions**:

1. **Wait up to 10 minutes** - complex environments take time
2. **Check for HITL approval** if required by template
3. **View provisioning logs** for errors
4. **Terminate and retry** if stuck > 15 minutes

### Cannot Connect to Environment

**Symptoms**: Connection details don't work

**Solutions**:

1. **Verify environment is RUNNING**
2. **Download fresh connection info** - may have rotated
3. **Check your network** can reach the endpoint
4. **Verify VPN/firewall** rules allow connection

---

## Integration Issues

### MCP Gateway Connection Failed

**Symptoms**: Cannot connect to external tools

**Solutions**:

1. **Verify not in Defense Mode**:
   - Defense mode blocks all external
   - Switch to Enterprise or Hybrid

2. **Check gateway configuration**:
   - Correct URL
   - Valid API key
   - Use Test Connection button

3. **Verify network connectivity**:
   - Firewall rules
   - Proxy configuration

### Slack/Jira Not Working

**Symptoms**: Notifications not sending, tickets not creating

**Solutions**:

1. **Verify integration is connected**:
   - Navigate to Settings > Integrations
   - Check status indicator

2. **Test the connection**:
   - Click Test Connection
   - Review error message

3. **Re-authorize if needed**:
   - Tokens may have expired
   - Disconnect and reconnect

### Webhook Delivery Failed

**Symptoms**: External systems not receiving events

**Solutions**:

1. **Check webhook endpoint**:
   - Is it reachable?
   - Is it returning 200?

2. **Review webhook logs**:
   - Navigate to Settings > Webhooks
   - View delivery history

3. **Verify payload format**:
   - Check receiver expects our format
   - Review documentation

---

## Security Alert Issues

### Alerts Not Appearing

**Symptoms**: Expected alerts not showing

**Solutions**:

1. **Check alert severity**:
   - Lower priority may not show prominently
   - Filter to show all priorities

2. **Verify detection is enabled**:
   - Navigate to Settings > Security
   - Check detection settings

3. **Review alert rules**:
   - Custom rules may not be active
   - Check rule configuration

### Cannot Resolve Alert

**Symptoms**: Resolve button not working

**Solutions**:

1. **Ensure you have permissions** to resolve alerts
2. **Add required resolution notes** if prompted
3. **Check if alert requires** investigation first

---

## Performance Issues

### Dashboard Loading Slowly

**Symptoms**: Dashboard takes long to load

**Solutions**:

1. **Clear browser cache**
2. **Reduce widget count** - fewer widgets = faster load
3. **Check internet connection**
4. **Try different browser**

### API Requests Timing Out

**Symptoms**: API calls fail with timeout errors

**Solutions**:

1. **Check rate limits**:
   - May be rate limited
   - Wait and retry

2. **Reduce request size**:
   - Large payloads take longer
   - Use pagination

3. **Check service health**:
   - May be temporary issue
   - Wait and retry

---

## Data Issues

### Missing Code in Graph

**Symptoms**: Expected code entities not found

**Solutions**:

1. **Trigger re-index**:
   - Navigate to repository settings
   - Click Re-index

2. **Check file is supported**:
   - Review supported languages
   - File extension correct?

3. **Verify file is not excluded**:
   - Check .gitignore patterns
   - Review exclusion settings

### Search Not Finding Results

**Symptoms**: Known entities not returned

**Solutions**:

1. **Try different query terms**:
   - Be more specific or general
   - Try exact name if known

2. **Check index status**:
   - Is indexing complete?
   - Recent changes may not be indexed

3. **Use different search type**:
   - Graph for structure
   - Vector for semantics
   - Keyword for exact match

---

## Configuration Issues

### Settings Not Saving

**Symptoms**: Changes revert after save

**Solutions**:

1. **Check for validation errors**:
   - Review error message
   - Fix invalid values

2. **Verify admin permissions**:
   - Some settings require admin
   - Contact administrator

3. **Wait for save confirmation**:
   - Don't navigate away immediately
   - Wait for success message

### Compliance Profile Not Applying

**Symptoms**: Settings don't change after applying profile

**Solutions**:

1. **Refresh the page** after applying
2. **Check for conflicting settings** that block changes
3. **Review change propagation time**:
   - Some changes take time
   - Wait and check again

---

## Getting Help

### Self-Service Resources

1. **Chat Assistant**: Ask questions directly in platform
2. **Documentation**: Review relevant guides
3. **Logs**: Check application and audit logs

### Information to Gather

When contacting support, collect:

| Information | Where to Find |
|-------------|---------------|
| Error message | Screenshot or copy text |
| Timestamp | When issue occurred |
| Steps to reproduce | What you did |
| Browser/version | Browser settings |
| User ID | Profile page |
| Job/Environment ID | From URL or details |

### Reporting Issues

1. **Gather information** listed above
2. **Check known issues** in documentation
3. **Use Chat Assistant** for immediate help
4. **Contact support** with collected details

---

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `UNAUTHORIZED` | Session expired or invalid | Sign in again |
| `FORBIDDEN` | Insufficient permissions | Contact admin |
| `NOT_FOUND` | Resource doesn't exist | Verify ID is correct |
| `RATE_LIMITED` | Too many requests | Wait and retry |
| `VALIDATION_ERROR` | Invalid input data | Review and correct |
| `SERVICE_UNAVAILABLE` | Temporary outage | Wait and retry |
| `QUOTA_EXCEEDED` | Limit reached | Clean up or request increase |
| `BUDGET_EXCEEDED` | Spending limit hit | Wait for reset |

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Getting Started](./getting-started.md) | Platform basics |
| [Configuration](./configuration.md) | Settings reference |
| [Monitoring](./monitoring-observability.md) | Health monitoring |
| [API Reference](./api-reference.md) | API errors |
