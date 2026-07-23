FROM python:3.12-slim

WORKDIR /app

# 1. Install saas-common first (shared package, cached layer)
# setuptools needed by pyproject.toml build backend (not in python:3.12-slim)
COPY packages/saas-common/ ./packages/saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-build-isolation ./packages/saas-common[tool]

# 2. Install tg-bot dependencies (cached until pyproject changes)
COPY channels/tg-bot/pyproject.toml ./
RUN pip install --no-cache-dir \
    "aiogram>=3.13.0" \
    "aiohttp>=3.9.0" \
    "aiohttp-socks>=0.8.0" \
    "asyncpg>=0.29.0"

# 3. Copy source
COPY channels/tg-bot/tg_bot/ ./tg_bot/

# aiogram polling - no port needed, but expose for health probes
EXPOSE 8080

CMD ["python", "-m", "tg_bot.main"]
