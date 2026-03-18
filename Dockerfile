# Dockerfile for PostgreSQL with pgvector extension
FROM pgvector/pgvector:pg17

EXPOSE 5432

CMD ["postgres"]
