# UECda Client Dockerfile
#
# ビルド: docker build -t uecda-client .
# 実行:   docker run uecda-client -H <server_host> -p 42485 -n "MyBot"

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
COPY uecda_client/ ./uecda_client/

# クライアント起動
ENTRYPOINT ["uv", "run", "python", "-m", "uecda_client.main"]
CMD ["-H", "uecda-server", "-p", "42485", "-n", "Client"]
