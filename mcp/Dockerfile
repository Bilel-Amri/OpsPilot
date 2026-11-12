FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Installer les dépendances
COPY mcp/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# Exécuter le serveur avec un utilisateur non-root
RUN groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid mcp --no-create-home --shell /usr/sbin/nologin mcp

COPY --chown=10001:10001 mcp/server.py ./server.py

USER 10001:10001

EXPOSE 8001

CMD ["python", "server.py"]
