# Contributing

Thank you for your interest in contributing to this project! This is a portfolio project demonstrating production-grade ML-based root cause analysis.

## Project Status

This is a **portfolio/demo project** showcasing:
- Microservices architecture
- Event-driven design
- ML/AI integration for root cause analysis
- Modern full-stack development practices

## Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Automated-root-cause-analysis
   ```

2. **Start the services**
   ```bash
   docker compose up -d
   ```

3. **Run the demo**
   ```bash
   # Windows
   .\scripts\demo.ps1
   
   # Linux/Mac
   ./scripts/demo.sh
   ```

## Code Style

- **Python**: Follow PEP 8, use type hints where possible
- **TypeScript**: Follow standard TypeScript conventions
- **Formatting**: Use consistent formatting (black for Python, prettier for TypeScript)

## Testing

Before submitting changes:
- Ensure all services start correctly: `docker compose up -d`
- Run smoke tests: `python scripts/smoke_test.py`
- Verify the demo works: `python scripts/seed_demo_data.py`

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request with a clear description

## Questions?

Feel free to open an issue for questions or suggestions!
