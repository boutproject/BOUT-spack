FROM spack/ubuntu-noble:1.2.0

RUN apt update && \
    apt install -y --no-install-recommends \
    git \
    jq \
    nodejs && \
    rm -rf /var/lib/apt/lists/*