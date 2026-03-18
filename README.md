# Agent Lab - PostgreSQL 17.9 with pgvector & AI Agent

A Docker-based development environment for PostgreSQL with pgvector vector database extension + LangChain AI Agent with multi-provider LLM support.

## 📚 Documentation

All documentation has been organized in the `docs/` directory:

- **[docs/README.md](docs/README.md)** - Main project documentation and database setup
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[docs/AGENT.md](docs/AGENT.md)** - AI Agent documentation and usage guide
- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide
- **[docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)** - Project summary and overview
- **[docs/COPILOT_INSTRUCTIONS.md](docs/COPILOT_INSTRUCTIONS.md)** - Copilot workspace instructions

## 🚀 Quick Start

Start the database:
```bash
docker-compose up -d
```

Run the AI Agent:
```bash
cd agent
python agent.py
```

For detailed instructions, see [docs/README.md](docs/README.md).

## 📦 Project Structure

```
agent-lab/
├── README.md                # This file
├── docs/                    # Documentation
├── agent/                   # AI Agent component
├── Dockerfile               # PostgreSQL 17.9 with pgvector
├── docker-compose.yml       # Service orchestration
├── .env                     # Environment configuration
└── init-scripts/            # Custom SQL initialization
```

## 🔗 Quick Links

| Component | Location |
|-----------|----------|
| Database Setup | [docs/README.md](docs/README.md) |
| Agent Docs | [docs/AGENT.md](docs/AGENT.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Getting Started | [docs/QUICKSTART.md](docs/QUICKSTART.md) |
