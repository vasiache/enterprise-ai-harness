FROM python:3.12-slim

WORKDIR /app

COPY tools/ping-tool/pyproject.toml ./
RUN pip install --no-cache-dir "fastmcp>=2.3.0" "uvicorn>=0.30.0" "httpx>=0.27" "python-jose[cryptography]>=3.3" "asyncpg>=0.29" "pydantic>=2.0" "structlog>=24.0"

COPY packages/saas-common/ ./saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-deps --no-build-isolation ./saas-common/

COPY tools/ping-tool/ping_tool/ ./ping_tool/

EXPOSE 8000
CMD ["python", "-m", "ping_tool.server"]
