# UECda Server Dockerfile
#
# ビルド: docker build -t uecda-server .
# 実行:   docker run -p 42485:42485 uecda-server --num-games 10

FROM python:3.12-slim

# uvをインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 作業ディレクトリ設定
WORKDIR /app

# 依存関係ファイルをコピー（キャッシュ効率化のため先にコピー）
COPY pyproject.toml uv.lock ./

# 依存関係インストール（開発依存は除外）
RUN uv sync --frozen --no-dev

# アプリケーションコードをコピー
COPY uecda_server/ ./uecda_server/
COPY config.yml ./

# ポート公開
EXPOSE 42485

# サーバー起動
ENTRYPOINT ["uv", "run", "python", "-m", "uecda_server.main"]
CMD ["--num-games", "100"]
