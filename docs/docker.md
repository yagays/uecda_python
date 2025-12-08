# Docker環境ガイド

UECdaをDocker環境で実行するためのガイドです。

## 前提条件

- Docker 20.10以上
- Docker Compose v2以上

## クイックスタート

### デフォルト5人対戦

```bash
# リポジトリをクローン
git clone https://github.com/your-org/open-uecda.git
cd open-uecda

# 対戦実行（10ゲーム）
docker compose up --build

# ゲーム数を指定
UECDA_NUM_GAMES=100 docker compose up --build
```

### サーバーのみ起動

```bash
# サーバーをバックグラウンドで起動
docker compose up -d uecda-server

# ログ確認
docker compose logs -f uecda-server

# 停止
docker compose down
```

## 参加者向け: 独自クライアントの作成

### Step 1: リポジトリのフォーク・クローン

```bash
git clone https://github.com/your-org/open-uecda.git my-uecda-client
cd my-uecda-client/uecda_client
```

### Step 2: 戦略クラスの実装

`uecda_client/strategy/` に新しい戦略ファイルを作成:

```python
# uecda_client/strategy/my_strategy.py
from uecda_client.strategy.base import Strategy
from uecda_client.game.state import GameState
from uecda_client.network.protocol import TableArray

class MyStrategy(Strategy):
    """独自の戦略AI"""

    def select_lead(self, my_cards: TableArray, state: GameState) -> TableArray:
        """リード時のカード選択"""
        # TODO: 実装
        pass

    def select_follow(self, my_cards: TableArray, state: GameState) -> TableArray:
        """フォロー時のカード選択"""
        # TODO: 実装
        pass

    def select_exchange(self, my_cards: TableArray, num_cards: int) -> TableArray:
        """カード交換時の選択"""
        # TODO: 実装
        pass
```

### Step 3: main.pyの修正

`uecda_client/main.py` で使用する戦略クラスを変更:

```python
# 変更前
from uecda_client.strategy.simple import SimpleStrategy
strategy = SimpleStrategy()

# 変更後
from uecda_client.strategy.my_strategy import MyStrategy
strategy = MyStrategy()
```

### Step 4: ローカルテスト

```bash
# uecda_clientディレクトリで実行
cd uecda_client

# イメージをビルド
docker build -t my-uecda-client .

# サーバーを起動（別ターミナル）
cd ../uecda_server
docker build -t uecda-server .
docker run -p 42485:42485 uecda-server --num-games 3

# 自分のクライアントをテスト
docker run --network host my-uecda-client -H localhost -p 42485 -n "MyBot"
```

### Step 5: コードの提出

以下のいずれかの方法で開催者に提出:

1. **GitHubで公開**: リポジトリをpushしてURLを開催者に共有
2. **コード送付**: zipファイルなどで開催者に直接送付

## 開催者向け: トーナメントの実行

### Step 1: 参加者のリポジトリを取得

```bash
cd open-uecda

# participantsディレクトリを作成
mkdir -p participants

# 各参加者のリポジトリをクローン
git clone https://github.com/participant1/their-client ./participants/team-alpha
git clone https://github.com/participant2/their-client ./participants/team-beta
# ... 他の参加者も同様
```

### Step 2: docker-compose.tournament.ymlの編集

`docker-compose.tournament.yml` を編集して、各参加者のパスとチーム名を設定:

```yaml
services:
  team-alpha:
    build:
      context: ./participants/team-alpha  # 参加者のリポジトリパス
    command: ["-H", "uecda-server", "-p", "42485", "-n", "TeamAlpha"]
    # ...
```

### Step 3: トーナメント実行

```bash
# 対戦実行
docker compose -f docker-compose.tournament.yml up --build

# ゲーム数を指定して実行
UECDA_NUM_GAMES=1000 docker compose -f docker-compose.tournament.yml up --build
```

### Step 4: 結果の確認

```bash
# ログ確認
docker compose -f docker-compose.tournament.yml logs uecda-server

# ゲームログファイル（JSONL形式）
cat logs/game_log.jsonl
```

## ゲームログ

対戦結果は `logs/` ディレクトリにJSONL形式で保存されます。ファイル名は自動生成され、以下の形式になります：

```
{実行時刻}_{クライアント1}_{クライアント2}_..._{クライアントN}.jsonl
```

例: `20231115T143052_Client1_Client2_Client3_Client4_Client5.jsonl`

```bash
# ログファイル一覧
ls -la logs/

# 最新のログを確認
cat logs/*.jsonl | jq .

# ログビューアで確認
cd uecda_server
uv run python -m uecda_server.log_viewer ../logs/{ファイル名}.jsonl
```

詳細は [docs/game-log.md](game-log.md) を参照してください。

## トラブルシューティング

### クライアントがサーバーに接続できない

- サーバーのヘルスチェックが完了するまで待機してください
- `docker compose logs uecda-server` でサーバーの状態を確認

### ビルドが失敗する

- `uv.lock` ファイルが存在することを確認
- `pyproject.toml` の依存関係が正しいことを確認

### 参加者のDockerfileがない場合

参加者が `uecda_client` をベースにしている場合、以下のDockerfileを使用:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY uecda_client/ ./uecda_client/
ENTRYPOINT ["uv", "run", "python", "-m", "uecda_client.main"]
CMD ["-H", "uecda-server", "-p", "42485", "-n", "Client"]
```

## ファイル構成

```
open-uecda/
├── docker-compose.yml              # デフォルト5人対戦用
├── docker-compose.tournament.yml   # トーナメント用テンプレート
├── logs/                           # ゲームログ出力先
│   └── {timestamp}_{players}.jsonl
├── uecda_server/
│   ├── Dockerfile
│   └── .dockerignore
├── uecda_client/
│   ├── Dockerfile
│   └── .dockerignore
└── participants/                   # トーナメント時に参加者のコードを配置
    ├── team-alpha/
    ├── team-beta/
    └── ...
```
