# Release Checklist

## Pre-Release
- [ ] All tests passing (`make test`)
- [ ] Version bumped in setup.py and __init__.py
- [ ] CHANGELOG.md updated
- [ ] Documentation reviewed
- [ ] Example config updated

## Release
- [ ] Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Create GitHub release with changelog

## Post-Release
- [ ] Verify Docker image builds
- [ ] Test installation from fresh clone
- [ ] Update project board/issues
