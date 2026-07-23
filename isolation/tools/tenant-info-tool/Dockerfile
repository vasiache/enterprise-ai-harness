FROM python:3.12-slim

WORKDIR /app

COPY packages/saas-common/ ./packages/saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-build-isolation ./packages/saas-common[tool]

COPY tools/tenant-info-tool/pyproject.toml ./
RUN pip install --no-cache-dir "fastmcp>=2.3.0" "asyncpg>=0.29.0" "uvicorn>=0.30.0"

COPY tools/tenant-info-tool/tenant_info_tool/ ./tenant_info_tool/

EXPOSE 8000
CMD ["python", "-m", "tenant_info_tool.server"]
