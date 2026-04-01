# Testing Checklist Template - [Package Name] v[Version]

**Package:** [package-name]
**Current Version:** [x.y.z]
**Target Version:** [x.y.z]
**Risk Level:** 🟢 Low / 🟡 Medium / 🔴 High
**Testing Date:** YYYY-MM-DD
**Tester:** [Name]

---

## Pre-Update Analysis

### Changelog Review
- [ ] Read full changelog: [link to changelog]
- [ ] Identify breaking changes
- [ ] Identify deprecations
- [ ] Identify new features

**Breaking Changes Found:**
1. [Change 1]
2. [Change 2]

**Deprecations:**
1. [Deprecated API 1] - Replacement: [New API]
2. [Deprecated API 2] - Replacement: [New API]

---

## Code Impact Assessment

### Files Using This Package
```bash
# Search for imports
grep -r "from package_name" src/
grep -r "import package_name" src/
```

**Affected Files:**
- [ ] `src/file1.py` - [usage description]
- [ ] `src/file2.py` - [usage description]

### API Usage Patterns
- [ ] Pattern 1: [description] - Used in X files
- [ ] Pattern 2: [description] - Used in Y files

---

## Test Plan

### Unit Tests
- [ ] Run existing unit tests: `pytest tests/test_*.py -v`
- [ ] All tests passing: ✅ / ❌
- [ ] New test failures: [list any failures]

### Integration Tests
- [ ] Test integration point 1: [description]
- [ ] Test integration point 2: [description]
- [ ] All integrations working: ✅ / ❌

### Regression Tests
- [ ] Test Case 1: [description]
  - **Steps:** [test steps]
  - **Expected:** [expected result]
  - **Actual:** [actual result]
  - **Status:** ✅ Pass / ❌ Fail

- [ ] Test Case 2: [description]
  - **Steps:** [test steps]
  - **Expected:** [expected result]
  - **Actual:** [actual result]
  - **Status:** ✅ Pass / ❌ Fail

### Performance Tests
- [ ] Benchmark 1: [description]
  - **Before:** [metric]
  - **After:** [metric]
  - **Change:** [% change]

- [ ] Benchmark 2: [description]
  - **Before:** [metric]
  - **After:** [metric]
  - **Change:** [% change]

---

## Environment Testing

### Development
- [ ] Update applied: `pip install package==version`
- [ ] Tests passing: ✅ / ❌
- [ ] No warnings/errors: ✅ / ❌

### Staging (if applicable)
- [ ] Deployed to staging
- [ ] Smoke tests passing
- [ ] No production errors in logs

---

## Migration Actions Required

### Code Changes
- [ ] Update API usage in [file]: [description]
- [ ] Replace deprecated call in [file]: [description]
- [ ] Update type hints/annotations

### Configuration Changes
- [ ] Update [config file]: [description]
- [ ] Update environment variables

### Documentation Changes
- [ ] Update README.md
- [ ] Update API documentation
- [ ] Update CHANGELOG.md

---

## Rollback Plan

### Rollback Command
```bash
pip install package-name==previous-version
# or
npm install package-name@previous-version
```

### Rollback Verification
- [ ] Tests passing after rollback
- [ ] Application functioning normally
- [ ] No data corruption

---

## Sign-Off

### Test Results
- **Total Tests:** [number]
- **Passed:** [number]
- **Failed:** [number]
- **Coverage:** [%]

### Decision
- [ ] ✅ **APPROVE** - Safe to deploy to production
- [ ] ⏸️ **DEFER** - Issues found, needs more work
- [ ] ❌ **REJECT** - Too risky, revert update

**Rationale:** [Explain decision]

### Approvals
- [ ] Developer: [Name] - [Date]
- [ ] Tech Lead: [Name] - [Date]
- [ ] QA: [Name] - [Date]

---

## Post-Deployment Monitoring

### Metrics to Watch (48 hours)
- [ ] Error rate: [baseline vs current]
- [ ] Response time: [baseline vs current]
- [ ] Memory usage: [baseline vs current]
- [ ] Test suite duration: [baseline vs current]

### Incident Response
- **On-Call:** [Name]
- **Rollback SLA:** 15 minutes
- **Communication Channel:** #engineering-alerts

---

## Lessons Learned

**What went well:**
- [Item 1]
- [Item 2]

**What could be improved:**
- [Item 1]
- [Item 2]

**Action Items:**
- [ ] [Action 1] - Owner: [Name]
- [ ] [Action 2] - Owner: [Name]
