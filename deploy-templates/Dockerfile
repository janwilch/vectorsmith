# Build from the repository root:
#   docker build -f deploy-templates/Dockerfile -t vectorsmith .
#
# Public HTTP requires builtin OAuth and an https URL:
#   docker run --rm -p 8080:8080 \
#     -e QDRANT_URL=https://your-qdrant \
#     -e PUBLIC_URL=https://your.example.com \
#     vectorsmith
#
# --auth none is refused off localhost; do not use 0.0.0.0 with none.

FROM python:3.12-slim
WORKDIR /app
COPY packages/core /app/packages/core
COPY packages/cli /app/packages/cli
COPY examples/qdrant_invoices /app/examples/qdrant_invoices
RUN pip install --no-cache-dir \
      "./packages/core[qdrant,embed]" \
      "./packages/cli[qdrant]"
EXPOSE 8080
ENV TOOLS_FILE=/app/examples/qdrant_invoices/tools.invoices.yaml
ENV SERVER_NAME=invoices
CMD ["sh", "-c", "vectorsmith serve \"$TOOLS_FILE\" --name \"$SERVER_NAME\" --http 0.0.0.0:8080 --auth builtin --public-url \"$PUBLIC_URL\""]
