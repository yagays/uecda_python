# open-uecda

UECda（大貧民/大富豪）ゲームのPython実装です。

電気通信大学（UEC）が主催する大貧民大会「UECda」のC言語リファレンス実装をPythonに移植したものです。サーバーとクライアントの両方をPythonで実装しています。

## 概要

- **サーバー**: 5人対戦の大富豪ゲームサーバー
- **クライアント**: 戦略AIを実装したゲームクライアント
- **互換性**: C言語リファレンス実装（tndhm_devkit）と相互運用可能

## 必要要件

- Python 3.11以上
- [uv](https://github.com/astral-sh/uv) (パッケージマネージャー)

**Docker環境の場合:**
- Docker 20.10以上
- Docker Compose v2以上

## クイックスタート

### Docker環境（推奨）

```bash
# リポジトリをクローン
git clone https://github.com/your-org/open-uecda.git
cd open-uecda

# 5人対戦を実行（10ゲーム）
docker compose up --build

# ゲーム数を指定
UECDA_NUM_GAMES=100 docker compose up --build
```

詳細は [docs/docker.md](docs/docker.md) を参照してください。

### ローカル環境

#### 1. インストール

```bash
# サーバーとクライアントの依存関係をインストール
cd uecda_server && uv sync && cd ..
cd uecda_client && uv sync && cd ..
```

#### 2. ゲーム実行

スクリプトを使用して、サーバーと5台のクライアントを一括起動できます：

```bash
# デフォルト: 3ゲーム
./scripts/run_game.sh

# ゲーム数を指定
./scripts/run_game.sh 10
```

#### 3. 個別起動

サーバーとクライアントを個別に起動する場合：

```bash
# ターミナル1: サーバー起動
cd uecda_server
uv run python -m uecda_server.main --num-games 10

# ターミナル2-6: クライアント起動（5台必要）
cd uecda_client
uv run python -m uecda_client.main -n "Player1"
uv run python -m uecda_client.main -n "Player2"
# ... 以下同様
```

## リポジトリ構成

```
open-uecda/
├── README.md                    # このファイル
├── docker-compose.yml           # Docker対戦用設定
├── docker-compose.tournament.yml # トーナメント用テンプレート
├── docs/
│   └── docker.md                # Docker環境ガイド
├── uecda_server/                # Pythonサーバー実装
│   ├── Dockerfile
│   ├── README.md                # サーバー詳細ドキュメント
│   └── ...
├── uecda_client/                # Pythonクライアント実装
│   ├── Dockerfile
│   ├── README.md                # クライアント詳細ドキュメント
│   └── ...
└── scripts/                     # 実行スクリプト
    └── run_game.sh              # サーバー+クライアント一括実行
```

## 詳細ドキュメント

各コンポーネントの詳細は、それぞれのREADMEを参照してください：

- [サーバー詳細](uecda_server/README.md) - 設定オプション、ルール、アーキテクチャ
- [クライアント詳細](uecda_client/README.md) - コマンドライン引数、戦略AI、カスタム戦略の実装
- [Docker環境](docs/docker.md) - Docker環境でのセットアップ、トーナメント開催

## C言語実装との互換性

Python実装はC言語リファレンス実装と相互運用可能です：

```bash
# C言語リファレンス実装のダウンロードと展開
curl -O https://flute.u-shizuoka-ken.ac.jp/daihinmin/2023/files/tndhm_devkit_c-20221111.tar.gz
tar xzf tndhm_devkit_c-20221111.tar.gz

# Cクライアントのビルド
cd tndhm_devkit_c-20221111/client
make

# PythonサーバーとCクライアントの組み合わせ
cd uecda_server
./scripts/test_with_c_clients.sh 10
```

## 技術仕様

- **プロトコル**: UECda プロトコル バージョン 20070
- **通信方式**: TCP/IP
- **データ形式**: 8×15 整数配列 (480バイト, ビッグエンディアン)
- **デフォルトポート**: 42485

## 開発

### テスト実行

```bash
# サーバーのテスト
cd uecda_server && uv run pytest

# クライアントのテスト
cd uecda_client && uv run pytest
```

### Lintチェック

```bash
cd uecda_server && uv run ruff check .
cd uecda_client && uv run ruff check .
```

## オリジナル実装

本プロジェクトは、電気通信大学（UEC）コンピュータ大貧民大会実行委員会および西野研究室が開発・公開しているC言語リファレンス実装（tndhm_devkit）を参考に、プロトコル仕様に基づいてPythonで再実装したものです。


- [UECda 公式サイト](https://flute.u-shizuoka-ken.ac.jp/daihinmin/)

## ライセンス

MIT License
