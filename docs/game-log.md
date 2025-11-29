# ゲームログ仕様

サーバーが出力する詳細なゲームログの形式と使い方を説明します。

## 概要

ゲームログは**JSONL (JSON Lines)** 形式で出力されます。1行が1つのイベントを表すJSONオブジェクトになっており、ゲームの進行を1ステップずつ再現できます。

## 使い方

### コマンドライン引数で指定

```bash
cd uecda_server
uv run python -m uecda_server.main --num-games 100 --game-log game_log.jsonl
```

### 設定ファイルで指定

`config.yaml`:
```yaml
game_log:
  enabled: true
  output_path: "game_log.jsonl"
```

コマンドライン引数が設定ファイルより優先されます。

## カード表記

ログ内のカードは以下の形式で表記されます：

| 表記 | 意味 |
|------|------|
| `S3` | スペード3 |
| `H10` | ハート10 |
| `DJ` | ダイヤJ |
| `CQ` | クラブQ |
| `SK` | スペードK |
| `HA` | ハートA |
| `D2` | ダイヤ2 |
| `Jo` | ジョーカー |

スート記号：
- `S` = Spade（スペード）
- `H` = Heart（ハート）
- `D` = Diamond（ダイヤ）
- `C` = Club（クラブ）

ランク記号：
- `3`〜`10` = 数字
- `J` = ジャック（11）
- `Q` = クイーン（12）
- `K` = キング（13）
- `A` = エース（14）
- `2` = 2（最強）

複数カードはカンマ区切り：`S8,H8,D8`

## イベント一覧

### session_start

セッション開始時に出力。プレイヤー情報を記録。

```json
{
  "type": "session_start",
  "timestamp": "2025-11-29T10:00:00.000000",
  "players": [
    {"id": 0, "name": "Alice"},
    {"id": 1, "name": "Bob"},
    {"id": 2, "name": "Carol"},
    {"id": 3, "name": "Dave"},
    {"id": 4, "name": "Eve"}
  ]
}
```

### game_start

各ゲーム開始時に出力。初期手札を記録。

```json
{
  "type": "game_start",
  "game": 1,
  "hands": {
    "0": "S3,S7,H5,HJ,D4,D9,C6,CK,Jo",
    "1": "S4,S8,H6,HQ,D5,D10,C7,CA",
    "2": "S5,S9,H7,HK,D6,DJ,C8,C2",
    "3": "S6,S10,H8,HA,D7,DQ,C9",
    "4": "SJ,SQ,H9,H2,D8,DK,C10"
  },
  "ranks": {
    "0": "heimin",
    "1": "heimin",
    "2": "heimin",
    "3": "heimin",
    "4": "heimin"
  },
  "first_player": 0
}
```

| フィールド | 説明 |
|-----------|------|
| `game` | ゲーム番号（1から開始） |
| `hands` | プレイヤーIDをキーとした初期手札 |
| `ranks` | 前ゲームの順位（1ゲーム目は全員heimin） |
| `first_player` | 先攻プレイヤーID |

ランク値：
- `daifugo` = 大富豪（1位）
- `fugo` = 富豪（2位）
- `heimin` = 平民（3位）
- `hinmin` = 貧民（4位）
- `daihinmin` = 大貧民（5位）

### exchange

カード交換時に出力（ゲーム2以降のみ）。

```json
{
  "type": "exchange",
  "game": 2,
  "exchanges": [
    {"from": 0, "to": 4, "cards": "S3,H4"},
    {"from": 1, "to": 3, "cards": "C5"}
  ],
  "hands_after": {
    "0": "S7,S10,...",
    "1": "S8,SJ,...",
    "2": "...",
    "3": "...",
    "4": "..."
  }
}
```

| フィールド | 説明 |
|-----------|------|
| `exchanges` | 交換の配列 |
| `exchanges[].from` | カードを渡したプレイヤーID |
| `exchanges[].to` | カードを受け取ったプレイヤーID |
| `exchanges[].cards` | 交換されたカード |
| `hands_after` | 交換後の各プレイヤーの手札 |

### turn

各ターンで出力。プレイまたはパスを記録。

```json
{
  "type": "turn",
  "game": 1,
  "turn": 5,
  "player": 2,
  "action": "play",
  "cards": "H8,D8",
  "card_type": "pair",
  "field": "H8,D8",
  "hands": {
    "0": "S3,S7,...",
    "1": "S4,S8,...",
    "2": "H5,HJ,...",
    "3": "S6,S10,...",
    "4": "SJ,SQ,..."
  },
  "state": {
    "revolution": false,
    "eleven_back": false,
    "locked": false
  }
}
```

| フィールド | 説明 |
|-----------|------|
| `game` | ゲーム番号 |
| `turn` | ターン番号 |
| `player` | 行動したプレイヤーID |
| `action` | `"play"` または `"pass"` |
| `cards` | 出されたカード（パス時は空文字） |
| `card_type` | カードの種類 |
| `field` | 行動後のフィールド状態 |
| `hands` | 行動後の各プレイヤーの手札 |
| `state` | ゲーム状態 |

card_type値：
- `empty` = 空（パス）
- `single` = シングル
- `pair` = ペア（同じランクの複数枚）
- `sequence` = 階段（同じスートの連番）
- `joker_single` = ジョーカー単体

### special

特殊イベント発生時に出力。

```json
{
  "type": "special",
  "game": 1,
  "turn": 5,
  "event": "eight_stop",
  "player": 2
}
```

```json
{
  "type": "special",
  "game": 1,
  "turn": 12,
  "event": "revolution",
  "player": 1,
  "detail": {"is_revolution": true}
}
```

| event | 説明 |
|-------|------|
| `eight_stop` | 8切り（場が流れる） |
| `revolution` | 革命発動 |
| `eleven_back` | 11バック発動 |
| `lock` | 縛り発動 |
| `field_clear` | 全員パスで場が流れる |
| `player_finish` | プレイヤーが上がり |

### game_end

ゲーム終了時に出力。

```json
{
  "type": "game_end",
  "game": 1,
  "finish_order": [2, 0, 1, 4, 3],
  "new_ranks": {
    "0": "fugo",
    "1": "heimin",
    "2": "daifugo",
    "3": "daihinmin",
    "4": "hinmin"
  }
}
```

| フィールド | 説明 |
|-----------|------|
| `finish_order` | 上がり順のプレイヤーID配列 |
| `new_ranks` | 更新後のランク |

### session_end

セッション終了時に出力。

```json
{
  "type": "session_end",
  "total_games": 100,
  "final_points": {
    "0": 320,
    "1": 310,
    "2": 350,
    "3": 280,
    "4": 290
  },
  "ranking": [2, 0, 1, 4, 3]
}
```

| フィールド | 説明 |
|-----------|------|
| `total_games` | 総ゲーム数 |
| `final_points` | 各プレイヤーの最終ポイント |
| `ranking` | ポイント順のプレイヤーID配列 |

## サイズ目安

| ゲーム数 | ファイルサイズ目安 |
|----------|-------------------|
| 10 | 約500KB |
| 100 | 約5MB |
| 1000 | 約50MB |

※毎ターン全プレイヤーの手札を記録するため、サイズは大きめです。

## Pythonでの読み込み例

```python
import json

def read_game_log(path):
    """ログファイルを読み込むジェネレータ"""
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

# 使用例
for event in read_game_log("game_log.jsonl"):
    if event["type"] == "turn":
        print(f"Game {event['game']} Turn {event['turn']}: "
              f"Player {event['player']} {event['action']}")
```

## 特定のゲームを抽出

```python
def extract_game(path, game_num):
    """特定のゲーム番号のイベントを抽出"""
    events = []
    for event in read_game_log(path):
        if event.get("game") == game_num:
            events.append(event)
        elif event["type"] == "session_start":
            events.append(event)  # プレイヤー情報は常に含める
    return events
```

## ログビューアー

ログファイルをインタラクティブに表示するCLIツールが用意されています。

### 使い方

```bash
python scripts/log_viewer.py logs/game_log.jsonl
```

### キー操作

| キー | 動作 |
|------|------|
| `n` | 次のステップへ |
| `p` | 前のステップへ |
| `c` | 連続再生（1秒間隔）、任意のキーで停止 |
| `g` | 特定のゲーム番号へジャンプ |
| `t` | 特定のターン番号へジャンプ（現在のゲーム内） |
| `q` | 終了 |

### 画面表示

```
================================================================================
Game 1 / Turn 15                                    [REV] [LOCK]    Step 42/354
================================================================================

Field: [H8,D8] (pair)
Last: Player 2 played H8,D8

--------------------------------------------------------------------------------
Player 0 (Alice) [大富豪]        | Player 1 (Bob) [富豪]
  S3,S7,H5,HJ,D4,D9,C6,CK,Jo     |   S4,S8,H6,HQ,D5,D10,C7,CA
  (9 cards)                      |   (8 cards)
--------------------------------------------------------------------------------
Player 2 (Carol) [平民] <<<      | Player 3 (Dave) [貧民]
  H5,HJ,D4,D9,C6                 |   S6,S10,H8,HA,D7,DQ,C9
  (5 cards)                      |   (7 cards)
--------------------------------------------------------------------------------
Player 4 (Eve) [大貧民]          |
  SJ,SQ,H9,H2,D8,DK,C10          |
  (7 cards)                      |
================================================================================
[n]ext [p]rev [c]ontinuous [g]ame [t]urn [q]uit
```

- `[REV]`: 革命中
- `[LOCK]`: 縛り中
- `[11B]`: 11バック中
- `<<<`: 現在のプレイヤー
- `[済]`: 上がり済み
