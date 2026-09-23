# Contributing to ApplyFlow AI

Thank you for your interest in contributing to **ApplyFlow AI**! 🚀

We welcome contributions from developers, recruiters, data scientists, and automation enthusiasts worldwide.

---

## 🛠️ How to Contribute

1. **Fork the Repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/<your-username>/applyflow-ai.git
   cd applyflow-ai
   ```
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/smart-portal-integrations
   ```
4. **Set up your local virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```
5. **Commit your changes** with descriptive commit messages:
   ```bash
   git commit -m "feat: add multi-country telephone prefix resolver"
   ```
6. **Push to your fork** and submit a Pull Request!

---

## 📜 Code Guidelines
- Follow **PEP 8** standards for Python backend code.
- Keep the frontend minimalist, fast, and dependency-light (pure Tailwind / modern ES6+).
- Ensure all automation actions include human-like jitter delays to respect platform security policies.

---

## 🛡️ Responsible Automation Philosophy
ApplyFlow AI is built to empower job seekers by eliminating repetitive administrative form filling. We do not encourage bot spamming. Features that enforce rate limiting, blacklist screening, and quality matching will always be prioritized.
