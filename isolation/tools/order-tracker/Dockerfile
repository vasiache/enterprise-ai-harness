FROM python:3.12-slim

WORKDIR /app

# Install saas-common (workspace package) and tool dependencies
# setuptools needed by pyproject.toml build backend (not in python:3.12-slim)
COPY packages/saas-common/ ./packages/saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-build-isolation ./packages/saas-common[tool]

# Install tool-specific dependencies
COPY tools/order-tracker/pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastmcp>=2.3.0" \
        "asyncpg>=0.29.0" \
        "uvicorn>=0.30.0"

# Copy source
COPY tools/order-tracker/order_tracker/ ./order_tracker/

EXPOSE 8000
CMD ["python", "-m", "order_tracker.server"]
