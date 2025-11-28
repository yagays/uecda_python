# UECda Client

UECda (大富豪/大貧民) のPythonクライアント実装です。

C言語リファレンス実装 (`tndhm_devkit_c-20221111/client/`) をPythonに移植したものです。

## 必要要件

- Python 3.11以上
- uv (パッケージマネージャー)

## インストール

```bash
cd uecda_client
uv sync
```

## 使い方

```bash
uv run python -m uecda_client.main [オプション]
```

### オプション

| オプション | 説明 | デフォルト値 |
|-----------|------|-------------|
| `-H`, `--host` | サーバーのホスト名またはIPアドレス | `127.0.0.1` |
| `-p`, `--port` | サーバーのポート番号 | `42485` |
| `-n`, `--name` | プレイヤー名 (最大14文字) | `PythonClient` |
| `-v`, `--verbose` | 詳細ログを出力 | オフ |

### 実行例

```bash
# ローカルサーバーにデフォルト設定で接続
uv run python -m uecda_client.main

# リモートサーバーにカスタム名で接続
uv run python -m uecda_client.main -H 192.168.1.100 -p 42485 -n "MyBot"

# 詳細ログを有効にして接続
uv run python -m uecda_client.main -v
```

## アーキテクチャ

```
uecda_client/
├── main.py              # エントリーポイント、ゲームループ
├── models/
│   └── card.py          # Card, CardSet, Rank, Suit
├── network/
│   ├── connection.py    # GameConnection (TCP接続管理)
│   └── protocol.py      # TableArray, プロトコル定義
├── game/
│   └── state.py         # GameState (ゲーム状態解析)
└── strategy/
    ├── base.py          # Strategy基底クラス (ABC)
    ├── analyzer.py      # HandAnalyzer (グループ・階段検出)
    └── simple.py        # SimpleStrategy (リファレンスAI)
```

## 戦略AI

`SimpleStrategy` はC言語リファレンス実装と同等の戦略AIです:

- **優先順位**: 階段 > グループ > シングル
- **リード時**: 枚数が多い組み合わせを優先、同枚数なら弱いカードから
- **フォロー時**: 場のパターンに合わせて、出せる中で最も弱いカードを選択
- **革命時**: 強弱が逆転するため、強いカードから出す
- **カード交換**: 最も弱いカードを渡す

### カスタム戦略の実装

独自の戦略を実装する場合は `Strategy` 基底クラスを継承してください:

```python
from uecda_client.strategy.base import Strategy

class MyStrategy(Strategy):
    def select_lead(self, my_cards, state):
        # リード時に出すカードをTableArrayで返す
        pass

    def select_follow(self, my_cards, state):
        # フォロー時に出すカードをTableArrayで返す
        pass

    def select_exchange(self, my_cards, num_cards):
        # 交換するカードをTableArrayで返す
        pass
```

## プロトコル

UECdaプロトコル (version 20070) に準拠:

- **通信方式**: TCP/IP
- **データ形式**: 8x15 整数配列 (480バイト, ビッグエンディアン)
- **ポート番号**: 42485 (デフォルト)
