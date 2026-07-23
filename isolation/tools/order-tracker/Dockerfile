FROM python:3.12-slim

WORKDIR /app

COPY packages/saas-common/ ./packages/saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-build-isolation ./packages/saas-common[tool]

COPY tools/order-tracker/pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastmcp>=2.3.0" \
        "asyncpg>=0.29.0" \
        "uvicorn>=0.30.0"

COPY tools/order-tracker/order_tracker/ ./order_tracker/

EXPOSE 8000
CMD ["python", "-m", "order_tracker.server"]
