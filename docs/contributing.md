# Contributing to GIAE

We welcome contributions from computational biologists, bioinformaticians, and software engineers!

---

## 🛠️ Development Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Ayo-Cyber/GIAE.git
   cd GIAE
   ```

2. **Create a Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Install Pre-commit Hooks:**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

---

## 🧪 Running Tests

We use `pytest` for all verification.

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=giae --cov-report=term-missing
```

---

## 📝 Coding Standards

- **Formatting**: We use `ruff` for linting and formatting.
- **Typing**: Use `mypy` for static type checking.
- **Documentation**: All new features must include docstrings and an update to the `docs/` folder.

---

## 🚀 Pull Request Process

1. **Create a Branch**: `git checkout -b feature/your-feature-name`
2. **Commit Changes**: Use clear, descriptive commit messages.
3. **Run CI Locally**: Ensure all tests and linting pass.
4. **Submit PR**: Describe the scientific rationale and technical implementation.
