# Build from the repository root:
#   docker build -f deploy-templates/docker/Dockerfile -t vectorsmith .
#
# Public HTTP: --auth jwt or builtin with https PUBLIC_URL.
# --auth none is refused off localhost.

FROM python:3.12-slim
WORKDIR /app
COPY packages/core /app/packages/core
COPY packages/cli /app/packages/cli
COPY examples/enterprise /app/examples/enterprise
RUN pip install --no-cache-dir \
      "./packages/core[qdrant,embed]" \
      "./packages/cli[qdrant,auth-jwt,auth-redis]"
EXPOSE 8080
ENV TOOLS_FILE=/app/examples/enterprise/tools.yaml
ENV SERVER_NAME=vectorsmith
ENV AUTH_MODE=jwt
CMD ["sh", "-c", "vectorsmith serve \"$TOOLS_FILE\" --name \"$SERVER_NAME\" --http 0.0.0.0:8080 --auth \"$AUTH_MODE\" --jwks-url \"$JWKS_URL\" --shutdown-grace-s 30 --log-format json"]
