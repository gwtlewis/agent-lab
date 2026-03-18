# Documentation Index

**Last Updated**: March 16, 2026

---

## 📚 Documentation Overview

Complete documentation for the xVA RAG Pipeline project.

### 🚀 Getting Started
- **[README.md](README.md)** - Project overview and features
- **[QUICKSTART.md](QUICKSTART.md)** - Setup guide (5 minutes)
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)** - Current state & achievements ⭐

### 🏗️ System Design
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture & diagrams
- **[AGENT.md](AGENT.md)** - Agent design and functionality

### 🛠️ Implementation Guides
- **[CLI_USAGE.md](CLI_USAGE.md)** - Command-line tool documentation
- **[XVA_RAG_TESTING.md](XVA_RAG_TESTING.md)** - Testing guide & test suite

---

## 📖 Documentation Guide

### For New Users
**Start here:**
1. [README.md](README.md) - Understand what this project does
2. [QUICKSTART.md](QUICKSTART.md) - Get it running locally
3. [AGENT.md](AGENT.md) - Learn how the agent works

### For Developers
**Implementation details:**
1. [ARCHITECTURE.md](ARCHITECTURE.md) - System design
2. [AGENT.md](AGENT.md) - Agent components
3. [CLI_USAGE.md](CLI_USAGE.md) - CLI tools
4. [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) - Testing approach

### For Operations
**Deployment & management:**
1. [QUICKSTART.md](QUICKSTART.md) - Environment setup
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Infrastructure requirements
3. [CLI_USAGE.md](CLI_USAGE.md) - Running the tools

### For Project Managers
**Project overview:**
1. [PROJECT_STATUS.md](PROJECT_STATUS.md) - Current state & progress
2. [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Detailed breakdown

---

## 📋 Quick Reference

### Files by Purpose

| File | Purpose | Audience | Read Time |
|------|---------|----------|-----------|
| README.md | Project overview | Everyone | 5 min |
| QUICKSTART.md | Setup guide | Developers/Ops | 5 min |
| ARCHITECTURE.md | System design | Developers/Architects | 15 min |
| AGENT.md | Agent functionality | Developers | 10 min |
| CLI_USAGE.md | CLI tools | Users/Developers | 10 min |
| PROJECT_SUMMARY.md | Detailed breakdown | Project Managers | 20 min |
| PROJECT_STATUS.md | Current achievements | Leadership/Teams | 10 min |
| XVA_RAG_TESTING.md | Testing suite | QA/Developers | 10 min |

---

## 🎯 Common Tasks

### I want to...

#### Setup Project
→ Go to [QUICKSTART.md](QUICKSTART.md)
1. Install dependencies
2. Start services
3. Initialize database
4. Run tests

#### Ingest a PDF
→ Go to [CLI_USAGE.md](CLI_USAGE.md) → Ingest Command
```bash
python -m ingest_pdf ingest <pdf_path>
```

#### Query Knowledge Base
→ Go to [AGENT.md](AGENT.md) → RAG Agent Usage
```python
from agent_with_rag import RAGAgent
agent = RAGAgent(provider="ollama", db_url="...", enable_rag=True)
response = agent.chat("Your question")
```

#### Understand the Architecture
→ Go to [ARCHITECTURE.md](ARCHITECTURE.md)
- System diagram
- Component descriptions
- Data flow

#### Run Tests
→ Go to [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md)
```bash
python -m pytest agent/test_*.py -v
```

#### Deploy to Production
→ Go to [QUICKSTART.md](QUICKSTART.md) → Docker Setup
→ Also see [ARCHITECTURE.md](ARCHITECTURE.md) → Infrastructure

---

## 🔍 Topic Guide

### Key Topics by Documentation

#### Vector Databases & pgvector
- [ARCHITECTURE.md](ARCHITECTURE.md) - Database schema
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Technical stack

#### LangChain Integration
- [AGENT.md](AGENT.md) - Agent implementation
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Technology stack

#### PDF Processing
- [CLI_USAGE.md](CLI_USAGE.md) - Ingestion process
- [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) - PDF tests

#### Embeddings & Semantic Search
- [ARCHITECTURE.md](ARCHITECTURE.md) - Data flow
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Capabilities

#### xVA Financial Concepts
- [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) - Domain coverage
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - xVA explained

#### Testing & Quality
- [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) - Complete test guide
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - QA metrics

---

## 📊 Project Statistics

### Documentation Coverage
- **8 markdown files**
- **~90 KB total**
- **300+ key topics**
- **40+ code examples**
- **Multiple architecture diagrams**

### Code Base
- **4 core modules**
- **2 CLI tools**
- **12 test files**
- **95+ test cases**
- **100% pass rate** ✅

---

## 🗺️ File Descriptions

### [README.md](README.md)
**Project Overview**
- Features
- Getting started
- Technology stack
- Quick examples

### [QUICKSTART.md](QUICKSTART.md)
**Setup Guide**
- Environment setup
- Docker configuration
- Database initialization
- First run walkthrough

### [ARCHITECTURE.md](ARCHITECTURE.md)
**System Design**
- Component diagram
- Data flow
- Database schema
- Integration points

### [AGENT.md](AGENT.md)
**Agent Implementation**
- Base agent design
- RAG agent features
- API references
- Usage examples

### [CLI_USAGE.md](CLI_USAGE.md)
**Command-Line Tools**
- ingest_pdf commands
- Options and parameters
- Batch processing
- Provider selection

### [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
**Detailed Breakdown**
- Comprehensive overview
- Implementation details
- Design decisions
- Lessons learned

### [PROJECT_STATUS.md](PROJECT_STATUS.md)
**Current State** ⭐
- What we have now
- Statistics and metrics
- Achievements
- Future enhancements

### [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md)
**Testing Guide**
- Test suite overview
- Test coverage
- xVA domain tests
- Integration scenarios

---

## 🚀 Navigation Tips

### By Experience Level

**Beginner:**
1. Start with README.md
2. Follow QUICKSTART.md
3. Try CLI_USAGE.md examples

**Intermediate:**
1. Read AGENT.md
2. Study ARCHITECTURE.md
3. Run XVA_RAG_TESTING.md examples

**Advanced:**
1. Review PROJECT_SUMMARY.md
2. Study source code comments
3. Contribute improvements

### By Goal

**"I want to understand RAG"**
→ ARCHITECTURE.md → PROJECT_STATUS.md (How It Works)

**"I want to use the tool"**
→ QUICKSTART.md → CLI_USAGE.md

**"I want to develop features"**
→ ARCHITECTURE.md → AGENT.md → Source code

**"I want project metrics"**
→ PROJECT_STATUS.md

---

## 💡 Tips

### Search Effectively
- Use Ctrl+F in your editor to search documentation
- Key terms: CVA, DVA, RAG, ingestion, retrieval, pgvector

### Find Examples
- CLI_USAGE.md - Command examples
- AGENT.md - Code snippets
- XVA_RAG_TESTING.md - Test examples
- QUICKSTART.md - Setup examples

### Learn Concepts
- ARCHITECTURE.md - System concepts
- PROJECT_STATUS.md - Technical explanations
- AGENT.md - Implementation details

---

## 🔗 Related Resources

### External Documentation
- [LangChain Docs](https://python.langchain.com/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Ollama Models](https://ollama.ai/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

### Internal Resources
- Code in `/agent/` with detailed comments
- Tests in `test_*.py` files
- SQL schema in `init-scripts/01-vectors.sql`
- Configuration examples in `.env` files

---

## ❓ FAQ

**Q: Where do I start?**  
A: Begin with [README.md](README.md), then [QUICKSTART.md](QUICKSTART.md)

**Q: How do I ingest a PDF?**  
A: See [CLI_USAGE.md](CLI_USAGE.md) → Ingest Command section

**Q: How do I query the knowledge base?**  
A: See [AGENT.md](AGENT.md) → RAG Agent Usage

**Q: What are the xVA concepts?**  
A: See [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) → xVA Content Coverage

**Q: How do I run tests?**  
A: See [XVA_RAG_TESTING.md](XVA_RAG_TESTING.md) → Test Execution

**Q: What's the current project status?**  
A: See [PROJECT_STATUS.md](PROJECT_STATUS.md)

---

## 📞 Support

### Issues & Questions
1. Check relevant documentation file
2. Search in source code comments
3. Review test files for examples
4. Check troubleshooting sections

### File Organization
- Documentation: `/docs/` (this folder)
- Code: `/agent/`
- Tests: `/agent/test_*.py`
- Database: `/init-scripts/`
- Deployment: `docker-compose.yml`, `Dockerfile`

---

**Happy exploring! 🚀**

*Start with [README.md](README.md) if you're new to the project.*
