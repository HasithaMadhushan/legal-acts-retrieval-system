# Third-Party Model Notices

## sentence-transformers/all-MiniLM-L6-v2

LexAtlas packages the following model in the backend Docker image for offline
semantic-embedding inference:

- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Pinned revision:** `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- **Declared license:** Apache License 2.0
- **Model metadata:**
  <https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2/revision/1110a243fdf4706b3f48f1d95db1a4f5529b4d41>
- **License text in the backend image:** `/licenses/Apache-2.0.txt`
- **This notice in the backend image:** `/licenses/THIRD_PARTY_NOTICES.md`

The pinned Hugging Face revision was inspected on 2026-08-29. Its model-card
metadata declares `apache-2.0`; its file manifest contains no separate
`LICENSE` or `NOTICE` file. LexAtlas therefore packages the complete Apache
License 2.0 text itself and records this manifest check here. This verifies the
published metadata and packaged notice boundary; it is not a legal opinion on
all upstream training-data or dependency rights.

Distributing the Docker image also distributes the packaged model artifact.
Release and university-submission images must include a copy of the Apache
License 2.0 and retain applicable copyright, attribution, patent, and NOTICE
materials. If LexAtlas modifies redistributed model files, the modified files
must carry prominent change notices. Upstream names and trademarks must not be
used to imply endorsement, and the Apache-2.0 warranty and liability disclaimer
must be preserved in the accompanying distribution materials.

Before publishing an image, inspect the pinned model revision and packaged
runtime dependencies for additional third-party notices. Release evidence must
record the model ID, exact revision, declared license, and the location of all
license and notice files in the image. Repeat this review whenever the model or
revision changes; a matching vector dimension does not establish license
compatibility.

This file records project distribution requirements and is not legal advice.
