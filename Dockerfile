# AI駆動開発ワークショップ用Dockerイメージ
# YouTube長尺動画 → 縦型ショート動画生成パイプライン

FROM ubuntu:24.04

# 非対話モード
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# 基本パッケージ
RUN apt-get update && apt-get install -y \
    # ビルドツール
    build-essential \
    curl \
    wget \
    git \
    sudo \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # Node.js (Claude Code用)
    nodejs \
    npm \
    # 動画処理
    ffmpeg \
    # 日本語形態素解析
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    # その他
    locales \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 日本語ロケール設定
RUN locale-gen ja_JP.UTF-8
ENV LANG=ja_JP.UTF-8
ENV LC_ALL=ja_JP.UTF-8

# Node.js 20.x にアップグレード（Claude Code要件）
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv インストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Claude Code インストール
RUN npm install -g @anthropic-ai/claude-code

# workshopユーザー作成（sudo権限付き）
RUN useradd -m -s /bin/bash workshop \
    && echo "workshop ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ユーザー用にuvを再インストール
USER workshop
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/workshop/.local/bin:$PATH"

WORKDIR /home/workshop

# CLAUDE.md と参考資料をコピー
COPY --chown=workshop:workshop CLAUDE.md /home/workshop/CLAUDE.md
COPY --chown=workshop:workshop docs/ai-driven-dev-workshop.md /home/workshop/reference.md

# ディレクトリ作成
RUN mkdir -p /home/workshop/output

# 環境変数
ENV GROQ_API_KEY=""

# デフォルトシェル
CMD ["/bin/bash"]
