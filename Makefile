.PHONY: test test-cov test-watch install-test clean-test

# Install test dependencies
install-test:
	pip install -r requirements-dev.txt

# Run all tests
test:
	pytest

# Run tests with coverage
test-cov:
	pytest --cov=app --cov-report=html --cov-report=term-missing

# Run tests in watch mode (requires pytest-watch)
test-watch:
	ptw tests

# Run specific test file
test-file:
	pytest $(FILE)

# Clean test artifacts
clean-test:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
