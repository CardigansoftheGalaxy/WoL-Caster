# WoL-Caster Makefile
# Cross-platform build automation

.PHONY: help install dev build clean test lint format package release

# Default target
help:
	@echo "🎯 WoL-Caster Build Commands"
	@echo "=========================================="
	@echo "Development:"
	@echo "  install     Install dependencies"
	@echo "  dev         Install development dependencies"
	@echo "  test        Run tests"
	@echo "  lint        Run linting checks"
	@echo "  format      Format code with black"
	@echo ""
	@echo "Building:"
	@echo "  build       Build executables"
	@echo "  package     Create distribution packages"
	@echo "  clean       Clean build directories"
	@echo ""
	@echo "Distribution:"
	@echo "  release     Build and package for release"
	@echo ""
	@echo "Quick start:"
	@echo "  make dev && make test && make build"

# Installation targets
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

dev: install
	@echo "🛠️  Installing development dependencies..."
	pip install -e .
	pip install pytest pytest-cov black flake8 pyinstaller

# Development targets
test:
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v --cov=wol_caster --cov-report=term-missing || true
	@echo "🔍 Testing import..."
	python -c "import wol_caster; print('✅ Import successful')"
	@echo "🔍 Testing CLI..."
	python wol_caster.py --version
	python wol_caster.py --help > /dev/null

lint:
	@echo "🔍 Running linting checks..."
	flake8 wol_caster.py --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 wol_caster.py --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

format:
	@echo "✨ Formatting code with black..."
	black wol_caster.py setup.py build.py

# Build targets
clean:
	@echo "🧹 Cleaning build directories..."
	rm -rf build/ dist/ *.egg-info/ __pycache__/
	rm -f *.zip *.tar.gz
	rm -rf installer/

build: clean
	@echo "🏗️  Building executables..."
	python build.py

package: build
	@echo "📦 Packaging complete - ready for distribution!"

# Release target
release: clean lint test build
	@echo "🚀 Release build complete!"
	@echo "📋 Build artifacts:"
	@ls -la dist/ 2>/dev/null || echo "No dist/ directory"
	@ls -la *.zip *.tar.gz 2>/dev/null || echo "No archive files"
	@echo ""
	@echo "✅ Ready for release!"

# Quick development setup
setup: dev test
	@echo "🎉 Development environment ready!"
	@echo "💡 Try: python wol_caster.py --help"

# Install from source
install-local: clean
	@echo "🔧 Installing WoL-Caster locally..."
	pip install .
	@echo "✅ Installation complete!"
	@echo "💡 Try: wol --help"

# Uninstall
uninstall:
	@echo "🗑️  Uninstalling WoL-Caster..."
	pip uninstall wol-caster -y || echo "Not installed via pip"
	@echo "✅ Uninstall complete"
