# enex_joplin_splitter.py

Evernote v11 for Windows からエクスポートした `.enex` ファイルを、Joplin に移行しやすいよう前処理・分割・記録する Python スクリプト。

巨大な ENEX をストリーミング処理しつつ、無題ノートの補正、Markdown 向け / HTML 向けへの振り分け、添付ファイル名の補正、CSV ログ出力をまとめて行います。

## 特徴

- 巨大な `.enex` を逐次処理するため、2GB 超級のファイルでも扱いやすいです。
- 複数 `.enex` をワイルドカード指定で一括処理できます。
- タイトルが `無題のノート` または `Untitled Note` の場合、本文 1 行目をプレーンテキスト化してタイトルに置き換えます。
- 置換タイトルが 80 文字を超える場合は、79 文字 + `…` に切り詰めます。
- Web クリップや HTML 主体ノートを `*_html.enex` に、それ以外を `*_md.enex` に振り分けます。
- 添付 resource の `file-name` を補完・正規化し、重複時は連番化します。
- ノートごとの判定結果を CSV ログに出力します。
- 本文中の Evernote 暗号化ブロックや Evernote ノート間リンクの有無も CSV に記録します。

## 入力ファイル

このスクリプトが受け取る入力は、Evernote からエクスポートした `.enex` ファイルです。

### 対応する入力例

- `input.enex`
- `*.enex`
- `archive/*.enex`
- `D:/Evernote/**/*.enex` `--recursive` 付き

### 入力内容

ENEX は XML 形式で、ノート本文、タグ、添付ファイル、メタ情報などを含みます。
このスクリプトは `<note>` を 1 件ずつ読みながら処理するため、全体を一括でメモリに載せません。

## 出力ファイル

入力が `sample.enex` の場合、次のファイルを出力します。

| 出力ファイル | 内容 |
|---|---|
| `sample_md.enex` | Markdown 取り込み向けのノートをまとめた ENEX。 |
| `sample_html.enex` | Web クリップや HTML 主体ノートをまとめた ENEX。 |
| `enex_split_log_YYYYmmdd_HHMMSS.csv` | ノートごとの判定結果を記録した CSV ログ。 |

### `_md.enex`

比較的シンプルなノートや Markdown 化しやすいノートをまとめたファイルです。 
Joplin では「ENEX を Markdown としてインポート」する用途を想定しています。

### `_html.enex`

Web クリップや、複雑な書式・表・埋め込みなどを含み、Markdown 化で崩れやすいノートをまとめたファイルです。 
Joplin では「ENEX を HTML としてインポート」する用途を想定しています。

### CSV ログ

CSV には各ノートごとに 1 行ずつ、変換や判定の結果が記録されます。  
文字コードは `utf-8-sig` なので、Windows の Excel でも開きやすい形式です。

## CSV 列の説明

| 列名 | 説明 |
|---|---|
| `input_file` | 元になった ENEX ファイルパス。 |
| `note_index` | 入力 ENEX 内でのノート順序。 |
| `original_title` | 元のタイトル。 |
| `final_title` | 補正後タイトル。 |
| `retitled` | 無題ノートを本文 1 行目で置換したか。`yes` / `no`。 |
| `has_encrypted` | 本文に `<en-crypt ` を含むか。`yes` / `no`。 |
| `has_note_link` | 本文に Evernote ノート間リンクを含むか。`yes` / `no`。 |
| `bucket` | 振り分け先。`md` または `html`。 |
| `classification_reason` | 判定理由。例: `source=web.clip7`、`body:-evernote-webclip:true`。 |
| `resource_filenames_fixed` | 添付ファイル名を補正したか。`yes` / `no`。 |
| `resource_rename_count` | 補正した添付ファイル名の件数。 |

## 無題ノートの補正

タイトルが `無題のノート` または `Untitled Note` の場合、本文 1 行目をタイトルとして採用します。
このとき、太字、斜体、色、`span`、`font`、リンクなどの装飾は除去し、プレーンテキストだけを使います。

## Web クリップ判定

次のいずれかに当てはまるノートは、Web クリップまたは HTML 主体ノートとして `html` 側に振り分けます。

### 本文側の判定

- `<div style="-evernote-webclip:true` を含む。
- `<div style="--en-clipped-content:` を含む。

### note-attributes 側の判定

- `<source>` が `web.clip` で始まる。
- `<source-application>` が次のいずれか。
  - `webclipper.evernote`
  - `WebClipper for Firefox`
  - `WebClipper`

### 補助判定

上記に当てはまらない場合でも、`source-url` の有無や HTML 要素の多さによって HTML 側へ振り分けることがあります。 
これは、Markdown 化で崩れやすいノートを事前に分離しやすくするためです。

## Evernote から Joplin への移行で役立つ点

Joplin は ENEX を Markdown または HTML として取り込めますが、Markdown 取り込みでは色やフォントなどの複雑な書式が失われることがあります。  
そのため、通常ノートは `_md.enex`、Web クリップや装飾が多いノートは `_html.enex` に分ける運用が有効です。

また、Evernote ノート間リンクは完全には復元されず、Joplin 側でタイトルベース推定になることがあるため、内部リンクを多く持つノートを CSV で事前確認できるのは有用です。

## 必要環境

- Python 3.9 以降推奨。
- 追加ライブラリ不要、標準ライブラリのみで動作します。

## 使い方

### 1ファイルだけ処理

```bash
python enex_joplin_splitter.py input.enex -o out
```

### カレントフォルダの `.enex` を一括処理

```bash
python enex_joplin_splitter.py "*.enex" -o out
```

### 複数パターンをまとめて処理

```bash
python enex_joplin_splitter.py "*.enex" "archive/*.enex" -o out
```

### サブフォルダも含めて再帰処理

```bash
python enex_joplin_splitter.py "D:/Evernote/**/*.enex" --recursive -o out
```

### CSV ログの保存先を指定

```bash
python enex_joplin_splitter.py "*.enex" -o out --csv-log out/result.csv
```

## オプション

| オプション | 説明 |
|---|---|
| `-o`, `--output-dir` | 出力先ディレクトリを指定します。 |
| `--recursive` | `**/*.enex` のような再帰ワイルドカードを有効にします。 |
| `--csv-log` | CSV ログの出力先ファイルを指定します。 |

## Joplin での取り込み例

1. `*_md.enex` を Joplin へ Markdown としてインポートします。
2. `*_html.enex` を Joplin へ HTML としてインポートします。
3. CSV ログを見て、暗号化ノートや内部リンク付きノートを確認します。

## 注意点

- HTML / Markdown の振り分けはヒューリスティックであり、100% 完全ではありません。
- 入力 ENEX 自体が壊れている場合は処理できないことがあります。
- `has_note_link=yes` はリンクの存在確認であり、リンク修復そのものは行いません。
- Evernote の暗号化テキストは移行先で扱いにくいことがあるため、`has_encrypted=yes` のノートは事前確認が有用です。

