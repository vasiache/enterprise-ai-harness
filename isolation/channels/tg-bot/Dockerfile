FROM python:3.12-slim

WORKDIR /app

COPY packages/saas-common/ ./packages/saas-common/
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir --no-build-isolation ./packages/saas-common[tool]

COPY channels/tg-bot/pyproject.toml ./
RUN pip install --no-cache-dir \
    "aiogram>=3.13.0" \
    "aiohttp>=3.9.0" \
    "aiohttp-socks>=0.8.0" \
    "asyncpg>=0.29.0"

COPY channels/tg-bot/tg_bot/ ./tg_bot/

EXPOSE 8080

CMD ["python", "-m", "tg_bot.main"]
