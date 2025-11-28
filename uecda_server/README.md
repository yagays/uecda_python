# UECda Server (Python)

UECda（大貧民/大富豪）カードゲームサーバーのPython実装です。
電気通信大学（UEC）が主催する大貧民大会「UECda」のC言語リファレンス実装と互換性があります。

## 特徴

- C言語クライアント（tndhm_devkit）と互換
- プロトコルバージョン 20070 対応
- YAMLによる設定ファイル
- UEC標準ルールに準拠

## 必要条件

- Python 3.11以上
- [uv](https://github.com/astral-sh/uv)

## インストール

```bash
cd uecda_server
uv sync
```

## 使用方法

### サーバーの起動

```bash
# デフォルト設定で起動（100ゲーム）
uv run python -m uecda_server.main

# ゲーム数を指定
uv run python -m uecda_server.main --num-games 10

# 詳細出力を有効化
uv run python -m uecda_server.main --num-games 10 -v

# 手札を表示
uv run python -m uecda_server.main --show-hands
```

### コマンドラインオプション

| オプション | 説明 |
|-----------|------|
| `-c`, `--config` | 設定ファイルのパス（YAML） |
| `-p`, `--port` | サーバーポート（設定を上書き） |
| `-n`, `--num-games` | ゲーム数（設定を上書き） |
| `-v`, `--verbose` | 詳細出力を有効化 |
| `--show-hands` | プレイヤーの手札を表示 |

### Cクライアントとの統合テスト

Cクライアント（tndhm_devkit）との統合テストを実行するスクリプトが用意されています。

```bash
# 事前準備: Cクライアントをビルド
cd ../tndhm_devkit_c-20221111/client
make
cd ../../uecda_server

# テスト実行（デフォルト100ゲーム）
./scripts/test_with_c_clients.sh

# ゲーム数を指定
./scripts/test_with_c_clients.sh 10

# 詳細出力付き
./scripts/test_with_c_clients.sh 5 -v
```

## 設定

`config.yml`で設定を変更できます：

```yaml
server:
  host: "0.0.0.0"
  port: 42485
  protocol_version: 20070

game:
  num_games: 100
  num_players: 5

rules:
  # 必須ルール（常に有効）
  revolution: true      # 革命（4枚ペアまたは5枚階段）
  eight_stop: true      # 8切り
  lock: true            # 縛り
  card_exchange: true   # カード交換
  spade3_joker: true    # スペ3返し
  sennichite: true      # 千日手（20連続パス）

  # オプションルール
  eleven_back: false    # 11バック
  five_skip: false      # 5飛び
  six_reverse: false    # 6リバース
  seat_change: false    # 席替え

logging:
  level: "INFO"
  show_hands: false
```

## プロジェクト構成

```
uecda_server/
├── uecda_server/
│   ├── main.py          # エントリーポイント
│   ├── config.py        # 設定管理
│   ├── game/
│   │   ├── engine.py    # ゲームエンジン
│   │   ├── rules.py     # ルール判定
│   │   └── exchange.py  # カード交換
│   ├── models/
│   │   ├── card.py      # カードモデル
│   │   ├── player.py    # プレイヤーモデル
│   │   └── game_state.py # ゲーム状態
│   ├── network/
│   │   ├── server.py    # TCPサーバー
│   │   └── protocol.py  # プロトコル処理
│   └── utils/
│       └── logger.py    # ログ・表示
├── tests/               # テスト
├── scripts/             # スクリプト
├── config.yml           # 設定ファイル
└── pyproject.toml
```

## 開発

### テスト実行

```bash
uv run pytest
```

### Lintチェック

```bash
uv run ruff check .
```

## ルール

UEC標準ルールに従います：

- **革命**: 4枚ペアまたは5枚階段で発動。カードの強さが逆転
- **8切り**: 8を含む手を出すと場が流れる
- **縛り**: 同じスートが2回連続で出ると、そのスートのみ有効
- **カード交換**: 大富豪/大貧民間で2枚、富豪/貧民間で1枚交換
- **スペ3返し**: ジョーカー単体に対してスペード3で返せる
- **千日手**: 20連続パスで場が流れる

## 互換性

このサーバーは以下と互換性があります：

- **クライアント**: tndhm_devkit_c-20221111（Cクライアント）
- **プロトコル**: UECdaプロトコル バージョン 20070
