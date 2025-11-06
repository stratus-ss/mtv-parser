# MTV Parser - Migration Toolkit for Virtualization Parser
# Makefile for development and testing workflow

.PHONY: help install install-dev test test-unit test-coverage lint fix format type-check clean
.PHONY: run-example run-analysis build package validate-requirements security

# Variables
PYTHON := venv/bin/python
PIP := venv/bin/pip
PYTHON_VERSION := python3.11
PROJECT_NAME := mtv-parser
SRC_DIR := mtv_parser
TEST_DIR := tests

# Default target
help:
	@echo "🚀 MTV Parser - Migration Toolkit for Virtualization Parser"
	@echo "==========================================================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@echo "🏗️  Setup & Installation:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install development environment"
	@echo "  clean         - Clean build artifacts and cache"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  validate-fix  - Validate the aggregate transfer speed fix"
	@echo ""
	@echo "🔧 Code Quality:"
	@echo "  lint          - Run linting checks (flake8)"
	@echo "  format        - Format code (black)"
	@echo "  fix           - Auto-fix formatting and import issues"
	@echo ""
	@echo "🎯 MTV Parser Operations:"
	@echo "  run-example   - Run parser with example data"
	@echo "  run-analysis  - Run parser with real migration data"
	@echo "  demo          - Run demonstration with sample data"
	@echo ""
	@echo "📦 Build & Package:"
	@echo "  build         - Build the package"
	@echo "  package       - Create distribution packages"
	@echo "  install-local - Install package locally"
	@echo ""
	@echo "🔍 Validation:"
	@echo "  validate-requirements - Check requirements files"
	@echo "  validate-structure    - Check project structure"

# Setup virtual environment
venv:
	@echo "🐍 Setting up Python virtual environment..."
	$(PYTHON_VERSION) -m venv venv
	$(PIP) install --upgrade pip setuptools wheel
	@echo "✅ Virtual environment created"

# Install production dependencies
install: venv
	@echo "📦 Installing production dependencies..."
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	@echo "✅ Production installation complete"

# Install development environment
install-dev: venv
	@echo "🛠️  Installing development environment..."
	$(PIP) install -r requirements.txt
	$(PIP) install -r tests/requirements.txt
	$(PIP) install -e .
	@echo "✅ Development environment ready"

# Testing targets
test: venv
	@echo "🧪 Running all tests..."
	$(PYTHON) -m pytest $(TEST_DIR)/ -v

test-unit: venv
	@echo "🧪 Running unit tests..."
	$(PYTHON) -m pytest $(TEST_DIR)/unit/ -v

test-coverage: venv
	@echo "📊 Running tests with coverage..."
	$(PYTHON) -m pytest $(TEST_DIR)/ --cov=$(SRC_DIR) --cov-report=html --cov-report=term --cov-report=xml

# Validate the aggregate transfer speed fix
validate-fix: venv
	@echo "🔍 Validating aggregate transfer speed fix..."
	@echo "Running parser and checking for correct aggregate throughput calculation..."
	$(PYTHON) $(SRC_DIR)/mtv_plan_parser.py > validation_output.txt 2>&1
	@echo "Expected: ~2766 GB/hour for successful migrations"
	@grep "Aggregate transfer per hour" validation_output.txt || echo "❌ Fix validation failed"
	@echo "✅ Validation complete - check validation_output.txt for details"

# Code quality targets
lint: venv
	@echo "🔍 Running linting checks..."
	$(PYTHON) -m flake8 $(SRC_DIR)/ $(TEST_DIR)/

format: venv
	@echo "🎨 Formatting code..."
	$(PYTHON) -m black $(SRC_DIR)/ $(TEST_DIR)/ --line-length 120

fix: venv
	@echo "🔧 Auto-fixing code issues..."
	$(PYTHON) -m black $(SRC_DIR)/ $(TEST_DIR)/ --line-length 120
	$(PYTHON) -m isort $(SRC_DIR)/ $(TEST_DIR)/
	@echo "✅ Auto-fixes applied"

# MTV Parser operations
run-example: venv
	@echo "🎯 Running MTV parser with example data..."
	@if [ -f "plans/single/vm-plan-sample.yaml" ]; then \
		$(PYTHON) $(SRC_DIR)/mtv_plan_parser.py; \
	else \
		echo "❌ Example data not found. Please ensure plans/single/vm-plan-sample.yaml exists"; \
	fi

run-analysis: venv
	@echo "🎯 Running MTV parser with real migration data..."
	@if [ -f "plans/multiple/2240_migration_plans.yaml" ]; then \
		$(PYTHON) $(SRC_DIR)/mtv_plan_parser.py; \
	else \
		echo "❌ Real migration data not found. Please ensure plans/multiple/ contains YAML files"; \
	fi

demo: venv
	@echo "🎭 Running MTV parser demonstration..."
	@echo "Using sample migration plans to demonstrate analysis capabilities..."
	$(PYTHON) $(SRC_DIR)/mtv_plan_parser.py
	@echo ""
	@echo "📊 Demo complete. Check the output above for:"
	@echo "  • Migration success/failure counts"
	@echo "  • Aggregate transfer per hour (fixed calculation)"
	@echo "  • Total disk size migrated"
	@echo "  • Migration timing analysis"

# Build and package
build: venv
	@echo "🏗️  Building package..."
	$(PYTHON) -m build

package: build
	@echo "📦 Creating distribution packages..."
	$(PYTHON) -m build --wheel --sdist
	@echo "✅ Distribution packages created in dist/"

install-local: package
	@echo "📥 Installing package locally..."
	$(PIP) install dist/$(PROJECT_NAME)-*.whl --force-reinstall

# Validation targets
validate-requirements: venv
	@echo "🔍 Validating requirements files..."
	@echo "Production requirements:"
	@$(PIP) check -r requirements.txt || echo "❌ Production requirements issues found"
	@echo "Test requirements:"
	@$(PIP) check -r tests/requirements.txt || echo "❌ Test requirements issues found"
	@echo "✅ Requirements validation complete"

validate-structure: 
	@echo "🔍 Validating project structure..."
	@echo "Checking core files..."
	@test -f "$(SRC_DIR)/__init__.py" || echo "❌ Missing $(SRC_DIR)/__init__.py"
	@test -f "$(SRC_DIR)/mtv_plan_parser.py" || echo "❌ Missing main parser script"
	@test -f "$(SRC_DIR)/migration_information.py" || echo "❌ Missing migration analysis module"
	@test -f "$(SRC_DIR)/clioutput.py" || echo "❌ Missing CLI output module"
	@test -f "pyproject.toml" || echo "❌ Missing pyproject.toml"
	@test -f "requirements.txt" || echo "❌ Missing requirements.txt"
	@test -d "$(TEST_DIR)/unit/" || echo "❌ Missing unit tests directory"
	@echo "✅ Project structure validation complete"

# Security
security: venv
	@echo "🔒 Running security checks..."
	@echo "Note: Install bandit for security scanning: pip install bandit"
	@echo "Example: bandit -r $(SRC_DIR)/"

# Cleanup
clean:
	@echo "🧹 Cleaning build artifacts and cache..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf coverage.xml
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -f validation_output.txt
	@echo "✅ Cleanup completed"

# Development utilities
dev-setup: install-dev
	@echo "🚀 Complete development setup..."
	@echo "Running initial tests to verify setup..."
	$(MAKE) test-unit
	@echo "Running lint check..."
	$(MAKE) lint
	@echo "✅ Development environment is ready!"

# Quick commands for common workflows
quick-test: test-unit lint
	@echo "✅ Quick test complete"

quick-fix: fix test-unit
	@echo "✅ Quick fix and test complete"

# Example workflows
example-workflow:
	@echo "📋 Example MTV Parser Workflow:"
	@echo "1. make install-dev    # Set up development environment"
	@echo "2. make test           # Run tests to ensure everything works"
	@echo "3. make run-analysis   # Analyze migration data"
	@echo "4. make validate-fix   # Verify aggregate transfer speed fix"
	@echo "5. make lint           # Check code quality"

# Show current MTV parser status
status:
	@echo "📊 MTV Parser Status:"
	@echo "Python version: $$($(PYTHON) --version 2>/dev/null || echo 'Not installed')"
	@echo "Virtual environment: $$([ -d venv ] && echo '✅ Active' || echo '❌ Not found')"
	@echo "Core modules: $$([ -f $(SRC_DIR)/mtv_plan_parser.py ] && echo '✅ Present' || echo '❌ Missing')"
	@echo "Test data: $$([ -d plans/multiple ] && echo '✅ Available' || echo '❌ Missing')"
	@echo "Recent fix: Aggregate transfer speed calculation (✅ Applied)"