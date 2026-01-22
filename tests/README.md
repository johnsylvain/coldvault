# ColdVault Test Suite

This directory contains the unit test suite for ColdVault. The tests use pytest and cover the main application components.

## Running Tests

### Install Test Dependencies

First, install the development dependencies (which includes test dependencies):

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=app --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

### Run Specific Test Files

```bash
# Run only API tests
pytest tests/test_api_jobs.py

# Run only encryption tests
pytest tests/test_encryption.py
```

### Run Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Run only API tests
pytest -m api

# Skip slow tests
pytest -m "not slow"
```

### Verbose Output

```bash
pytest -v
```

### Run Tests in Parallel

```bash
# Install pytest-xdist first
pip install pytest-xdist

# Run tests in parallel
pytest -n auto
```

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_config.py` - Configuration module tests
- `test_encryption.py` - Encryption utility tests
- `test_database.py` - Database model tests
- `test_api_jobs.py` - Jobs API endpoint tests
- `test_api_backups.py` - Backups API endpoint tests
- `test_aws.py` - AWS S3 integration tests (mocked)
- `test_main.py` - Main application tests

## Test Fixtures

The test suite includes several useful fixtures defined in `conftest.py`:

- `db_session` - Fresh database session for each test
- `client` - FastAPI test client with database override
- `temp_dir` - Temporary directory for test files
- `mock_s3_client` - Mocked S3 client for AWS tests
- `sample_job_data` - Sample job data dictionary
- `sample_job` - Sample job created in database

## Writing New Tests

When adding new tests:

1. Follow the naming convention: `test_*.py` for test files, `test_*` for test functions
2. Use fixtures from `conftest.py` when possible
3. Mock external dependencies (AWS, file system, etc.)
4. Use descriptive test names that explain what is being tested
5. Add markers for test categories (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)

### Example Test

```python
def test_create_job(client, sample_job_data):
    """Test creating a new job"""
    response = client.post("/api/jobs/", json=sample_job_data)
    assert response.status_code == 201
    assert response.json()["name"] == sample_job_data["name"]
```

## Coverage Goals

The test suite aims for:
- 80%+ code coverage for core modules
- 100% coverage for critical paths (encryption, authentication, etc.)
- All API endpoints should have at least basic tests

## Continuous Integration

Tests should be run automatically in CI/CD pipelines. The test suite is designed to:
- Run quickly (most tests complete in < 1 second)
- Be isolated (each test uses its own database session)
- Be deterministic (no flaky tests)
- Mock external dependencies (no actual AWS calls)
