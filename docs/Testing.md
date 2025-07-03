# Testing Guide

## Running Tests

### All Tests
```bash
make test
```

### With Coverage
```bash
make test-coverage
# Report in htmlcov/index.html
```

### Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Single test file
pytest tests/unit/test_config.py -v
```

## Test Structure
- `tests/unit/`: Fast, isolated component tests
- `tests/integration/`: Full system tests
- `tests/conftest.py`: Shared fixtures

## Current Test Status
- ✅ 27 tests passing
- ✅ Core functionality covered
- ⚠️ Enhancement modules need additional tests
