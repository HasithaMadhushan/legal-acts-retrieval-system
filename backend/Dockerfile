FROM debian:bookworm-slim AS pdf-ocr-assets

ARG TARGETARCH
ARG PDFIUM_VERSION=native-v7988
ARG ONNXRUNTIME_VERSION=1.27.0
ARG OAR_OCR_VERSION=v0.7.0

RUN test "$TARGETARCH" = "amd64"
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/pdf-inspector/pdfium /opt/pdf-inspector/onnxruntime \
    && curl -fL "https://github.com/firecrawl/pdfium-rs/releases/download/${PDFIUM_VERSION}/firecrawl-pdfium-linux-x64.tgz" -o /tmp/pdfium.tgz \
    && echo "6248189e07bbc33cdeb31976c539a88614307c8a19f3276dbd018efbe5b4a2a2  /tmp/pdfium.tgz" | sha256sum -c - \
    && tar -xzf /tmp/pdfium.tgz -C /opt/pdf-inspector/pdfium \
    && curl -fL "https://github.com/microsoft/onnxruntime/releases/download/v${ONNXRUNTIME_VERSION}/onnxruntime-linux-x64-${ONNXRUNTIME_VERSION}.tgz" -o /tmp/onnxruntime.tgz \
    && echo "547e40a48f1fe73e3f812d7c88a948612c23f896b91e4e2ee1e232d7b468246f  /tmp/onnxruntime.tgz" | sha256sum -c - \
    && tar -xzf /tmp/onnxruntime.tgz -C /opt/pdf-inspector/onnxruntime --strip-components=1 \
    && rm /tmp/pdfium.tgz /tmp/onnxruntime.tgz

RUN mkdir -p /opt/pdf-inspector/models \
    && curl -fL "https://github.com/GreatV/oar-ocr/releases/download/${OAR_OCR_VERSION}/pp-ocrv6_small_det.onnx" -o /opt/pdf-inspector/models/pp-ocrv6_small_det.onnx \
    && curl -fL "https://github.com/GreatV/oar-ocr/releases/download/${OAR_OCR_VERSION}/pp-ocrv6_small_rec.onnx" -o /opt/pdf-inspector/models/pp-ocrv6_small_rec.onnx \
    && curl -fL "https://github.com/GreatV/oar-ocr/releases/download/${OAR_OCR_VERSION}/ppocrv6_dict.txt" -o /opt/pdf-inspector/models/ppocrv6_dict.txt \
    && echo "d73e0058b7a8086bbd57f3d10b8bcd4ff95363f67e06e2762b5e814fe9c9410e  /opt/pdf-inspector/models/pp-ocrv6_small_det.onnx" | sha256sum -c - \
    && echo "5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634  /opt/pdf-inspector/models/pp-ocrv6_small_rec.onnx" | sha256sum -c - \
    && echo "b5f2bfe2bdd9448429e3e82b51c789775d9b42f2403d082b00662eb77e401c5d  /opt/pdf-inspector/models/ppocrv6_dict.txt" | sha256sum -c -


FROM python:3.13-slim

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG EMBEDDING_MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
ARG HF_HOME=/opt/huggingface

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
ENV EMBEDDING_MODEL_REVISION=${EMBEDDING_MODEL_REVISION}
ENV HF_HOME=${HF_HOME}
ENV PDFIUM_LIB_PATH=/opt/pdf-inspector/pdfium/lib/libpdfium.so
ENV ORT_DYLIB_PATH=/opt/pdf-inspector/onnxruntime/lib/libonnxruntime.so.1.27.0
ENV PDF_INSPECTOR_MODEL_CACHE=/opt/pdf-inspector/model-cache-disabled

COPY --from=pdf-ocr-assets /opt/pdf-inspector /opt/pdf-inspector

COPY requirements.txt .
COPY THIRD_PARTY_NOTICES.md /licenses/THIRD_PARTY_NOTICES.md
COPY licenses/Apache-2.0.txt /licenses/Apache-2.0.txt
RUN test -s /licenses/THIRD_PARTY_NOTICES.md \
    && test -s /licenses/Apache-2.0.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.13.0+cpu torchvision==0.28.0+cpu
RUN pip install --no-cache-dir -r requirements.txt

# Bake the configured embedding model into the image while network access is
# available. Runtime model loading is offline and therefore reproducible.
RUN python -c 'import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ["EMBEDDING_MODEL"], revision=os.environ["EMBEDDING_MODEL_REVISION"])'
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Exercise the exact offline OCR path during the image build. Runtime parsing
# always passes offline=True and therefore never downloads model artifacts.
RUN python -c 'import fitz, pdf_inspector; p="/tmp/ocr-smoke.pdf"; d=fitz.open(); d.new_page(); d.save(p); d.close(); pdf_inspector.process_pdf_with_ocr(p, mode="force", page_numbers=[1], model_directory="/opt/pdf-inspector/models", offline=True)'

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000
# The app also auto-migrates at startup (see app.db.migrate), but running the
# migration explicitly here first gives a clear, separate log step and fails
# fast before the server starts accepting traffic.
#
# Gunicorn supervises one or more uvicorn workers (async, so a slow PDF-processing
# background task in one request doesn't block others on the same worker). Override
# WEB_CONCURRENCY to size workers for the host (a common rule of thumb is 2 x CPU
# cores + 1); it defaults to 2 for small single-instance deployments.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --workers ${WEB_CONCURRENCY:-2} --timeout 120 --access-logfile - --error-logfile -"]
