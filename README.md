# Agent Lab - PostgreSQL 17.9 with pgvector & AI Agent

A Docker-based development environment for PostgreSQL with pgvector vector database extension + LangChain AI Agent with multi-provider LLM support.

## 📚 Documentation

All documentation has been organized in the `docs/` directory:

- **[docs/INDEX.md](docs/INDEX.md)** - Main documentation navigator and entry point
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[docs/AGENT.md](docs/AGENT.md)** - AI Agent documentation and usage guide
- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide
- **[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** - Project summary, metrics, and current status
- **[docs/WEB_UI.md](docs/WEB_UI.md)** - Browser UI guide and behavior notes

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

For detailed instructions, see [docs/INDEX.md](docs/INDEX.md).

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
| Documentation Index | [docs/INDEX.md](docs/INDEX.md) |
| Database Setup | [docs/QUICKSTART.md](docs/QUICKSTART.md) |
| Agent Docs | [docs/AGENT.md](docs/AGENT.md) |
| Project Status | [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Getting Started | [docs/QUICKSTART.md](docs/QUICKSTART.md) |
