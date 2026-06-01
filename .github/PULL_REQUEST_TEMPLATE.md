## Summary

<!-- 1-3 sentences describing what this PR does and why. -->

## Related Issues

<!-- Use "Closes #123" / "Fixes #456" to auto-close on merge, or "Refs #789" for related context. -->

Closes #

## Type of Change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactor (no functional change)
- [ ] Test / CI change
- [ ] Infrastructure / CloudFormation change
- [ ] Security fix (also: did you file a Security Advisory? Link it below.)

## How Has This Been Tested?

<!-- Describe the tests you ran. Include commands, environments, and any relevant output. -->

- [ ] `pytest` passes locally
- [ ] `pre-commit run --files <changed files>` passes locally
- [ ] Tested in dev/QA environment (describe below if applicable)

## Checklist

- [ ] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.) — see `docs/deployment/RELEASE_PLEASE_GUIDE.md`
- [ ] I have updated relevant documentation (`docs/PROJECT_STATUS.md`, `docs/deployment/DEPLOYMENT_GUIDE.md`, or `docs/DOCUMENTATION_INDEX.md` if applicable)
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] I have not lowered the 70% test-coverage threshold in `pyproject.toml`
- [ ] No secrets, credentials, or AI attribution in commits or files (see CLAUDE.md)
- [ ] For container changes: I am using private ECR base images via `--build-arg` (see CLAUDE.md)

## Additional Context

<!-- Screenshots, links, related PRs, design docs, etc. -->
