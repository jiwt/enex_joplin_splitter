# enex_joplin_splitter_fixed.py

Evernote v11 for Windows からエクスポートした `.enex` ファイルを、Joplin に移行しやすいよう前処理・分割・記録する Python スクリプトです。[page:1][code_file:210]

巨大な ENEX をストリーミング処理しつつ、無題ノートの補正、Markdown 向け / HTML 向けへの振り分け、添付ファイル名の補正、CSV ログ出力をまとめて行います。[web:204][web:209][code_file:210]

## 特徴

- 巨大な `.enex` を逐次処理するため、2GB 超級のファイルでも扱いやすいです。[web:204][web:209][code_file:210]
- 複数 `.enex` をワイルドカード指定で一括処理できます。[code_file:210]
- タイトルが `無題のノート` または `Untitled Note` の場合、本文 1 行目をプレーンテキスト化してタイトルに置き換えます。[code_file:210]
- タイトルの HTML 実体参照をデコードし、文字化けしやすい断片や CP932 非対応文字を整理します。[web:245][web:280][code_file:210]
- 置換タイトルが 80 文字を超える場合は、79 文字 + `…` に切り詰めます。[code_file:210]
- Web クリップや HTML 主体ノートを `*_html.enex` に、それ以外を `*_md.enex` に振り分けます。[page:1][code_file:210]
- `--webclip-only-html` を使うと、明示的な Web クリップだけを HTML 側に振り分けられます。[code_file:210]
- 添付 resource の `file-name` を補完・正規化し、重複時は連番化します。[code_file:210]
- ノートごとの判定結果を CSV ログに出力します。[code_file:210]
- 本文中の Evernote 暗号化ブロックや Evernote ノート間リンクの有無も CSV に記録します。[web:79][web:122][code_file:210]
- `<content>` の中身は基本的に保持し、本文 ENML/HTML は変更しません。[web:150][web:211][code_file:210]

## 入力ファイル

このスクリプトが受け取る入力は、Evernote からエクスポートした `.enex` ファイルです。[page:2][code_file:210]

### 対応する入力例

- `input.enex`
- `*.enex`
- `archive/*.enex`
- `D:/Evernote/**/*.enex` `--recursive` 付き

### 入力内容

ENEX は XML 形式で、ノート本文、タグ、添付ファイル、メタ情報などを含みます。[page:2]  
このスクリプトは `<note>` を 1 件ずつ読みながら処理するため、全体を一括でメモリに載せません。[web:204][web:209][code_file:210]

## 出力ファイル

入力が `sample.enex` の場合、次のファイルを出力します。[code_file:210]

| 出力ファイル | 内容 |
|---|---|
| `sample_md.enex` | Markdown 取り込み向けのノートをまとめた ENEX。[page:1][code_file:210] |
| `sample_html.enex` | Web クリップや HTML 主体ノートをまとめた ENEX。[page:1][code_file:210] |
| `enex_split_log_YYYYmmdd_HHMMSS.csv` | ノートごとの判定結果を記録した CSV ログ。[code_file:210] |

### `_md.enex`

比較的シンプルなノートや Markdown 化しやすいノートをまとめたファイルです。[page:1][code_file:210]  
Joplin では「ENEX を Markdown としてインポート」する用途を想定しています。[page:1]

### `_html.enex`

Web クリップや、複雑な書式・表・埋め込みなどを含み、Markdown 化で崩れやすいノートをまとめたファイルです。[page:1][code_file:210]  
Joplin では「ENEX を HTML としてインポート」する用途を想定しています。[page:1]

### CSV ログ

CSV には各ノートごとに 1 行ずつ、変換や判定の結果が記録されます。[code_file:210]  
文字コードは `utf-8-sig` なので、Windows の Excel でも開きやすい形式です。[web:35][web:44][code_file:210]

## CSV 列の説明

| 列名 | 説明 |
|---|---|
| `input_file` | 元になった ENEX ファイルパス。[code_file:210] |
| `note_index` | 入力 ENEX 内でのノート順序。[code_file:210] |
| `original_title` | 元のタイトル。[code_file:210] |
| `final_title` | 補正後タイトル。[code_file:210] |
| `retitled` | 無題ノートを本文 1 行目で置換したか。`yes` / `no`。[code_file:210] |
| `has_encrypted` | 本文に `<en-crypt ` を含むか。`yes` / `no`。[web:79][code_file:210] |
| `has_note_link` | 本文に Evernote ノート間リンクを含むか。`yes` / `no`。[web:122][code_file:210] |
| `bucket` | 振り分け先。`md` または `html`。[code_file:210] |
| `classification_reason` | 判定理由。例: `source=web.clip7`、`body:-evernote-webclip:true`。[code_file:210] |
| `resource_filenames_fixed` | 添付ファイル名を補正したか。`yes` / `no`。[code_file:210] |
| `resource_rename_count` | 補正した添付ファイル名の件数。[code_file:210] |

## 無題ノートの補正

タイトルが `無題のノート` または `Untitled Note` の場合、本文 1 行目をタイトルとして採用します。[code_file:210]  
このとき、太字、斜体、色、`span`、`font`、リンクなどの装飾は除去し、プレーンテキストだけを使います。[code_file:210]

さらに、タイトルには次のクリーンアップを行います。[code_file:210]

- HTML 実体参照のデコード。[web:245][code_file:210]
- `ftfy` が利用可能な場合の文字化け修復。[web:241][code_file:210]
- `cp932` に載らない文字の除去。[web:280][code_file:210]
- `D????` のような壊れた断片の除去。[code_file:210]
- 置換文字 `�` や制御文字の整理。[code_file:210]

## Web クリップ判定

次のいずれかに当てはまるノートは、Web クリップとして `html` 側に振り分けます。[code_file:210]

### 本文側の明示的判定

- `<div style="-evernote-webclip:true` を含む。[code_file:210]
- `<div style="--en-clipped-content:` を含む。[code_file:210]

### note-attributes 側の明示的判定

- `<source>` が `web.clip` で始まる。[code_file:210][web:157]
- `<source-application>` が次のいずれか。 [code_file:210]
  - `webclipper.evernote`
  - `WebClipper for Firefox`
  - `WebClipper`

### 通常モードの補助判定

通常モードでは、上記に当てはまらない場合でも、`source-url` の有無や HTML 要素の多さによって HTML 側へ振り分けることがあります。[code_file:210]  
これは、Markdown 化で崩れやすいノートを事前に分離しやすくするためです。[page:1][code_file:210]

### `--webclip-only-html` モード

`--webclip-only-html` を付けると、明示的な Web クリップ条件に一致したノートだけを HTML 側へ振り分けます。[code_file:210]  
このモードでは、`source-url` があるだけのノートや、本文に HTML タグが大量にあるノートでも、明示的 Web クリップ条件がなければ Markdown 側に残します。[code_file:210]

## 本文 `<content>` の扱い

Evernote ENEX の `<content>` は ENML/HTML を含む重要な部分です。[web:150]  
このスクリプトでは、本文判定やタイトル抽出のために `<content>` を読み取りますが、出力時には元の ENML を基本的に保持します。[web:211][code_file:210]

そのため、本文内の HTML タグが `&lt;` / `&gt;` に変わってしまうのを避けつつ、本文内容そのものは変更しない方針です。[web:211][web:218][code_file:210]

## Evernote から Joplin への移行で役立つ点

Joplin は ENEX を Markdown または HTML として取り込めますが、Markdown 取り込みでは色やフォントなどの複雑な書式が失われることがあります。[page:1]  
そのため、通常ノートは `_md.enex`、Web クリップや装飾が多いノートは `_html.enex` に分ける運用が有効です。[page:1][code_file:210]

また、Evernote ノート間リンクは完全には復元されず、Joplin 側でタイトルベース推定になることがあるため、内部リンクを多く持つノートを CSV で事前確認できるのは有用です。[page:1][web:127][code_file:210]

## 必要環境

- Python 3.9 以降推奨。[code_file:210]
- 追加ライブラリなしでも動作します。[code_file:210]
- `ftfy` をインストールしている場合は、タイトル文字化け補正に自動利用します。[web:241][code_file:210]

### `ftfy` の導入例

```bash
pip install ftfy
```

## 使い方

### 1ファイルだけ処理

```bash
python enex_joplin_splitter_fixed.py input.enex -o out
```

### カレントフォルダの `.enex` を一括処理

```bash
python enex_joplin_splitter_fixed.py "*.enex" -o out
```

### 複数パターンをまとめて処理

```bash
python enex_joplin_splitter_fixed.py "*.enex" "archive/*.enex" -o out
```

### サブフォルダも含めて再帰処理

```bash
python enex_joplin_splitter_fixed.py "D:/Evernote/**/*.enex" --recursive -o out
```

### CSV ログの保存先を指定

```bash
python enex_joplin_splitter_fixed.py "*.enex" -o out --csv-log out/result.csv
```

### 明示的 Web クリップだけを HTML にする

```bash
python enex_joplin_splitter_fixed.py "*.enex" -o out --webclip-only-html
```

## オプション

| オプション | 説明 |
|---|---|
| `-o`, `--output-dir` | 出力先ディレクトリを指定します。[code_file:210] |
| `--recursive` | `**/*.enex` のような再帰ワイルドカードを有効にします。[code_file:210] |
| `--csv-log` | CSV ログの出力先ファイルを指定します。[code_file:210] |
| `--webclip-only-html` | 明示的 Web クリップ条件に一致したノートだけを HTML 側へ振り分けます。[code_file:210] |

## Joplin での取り込み例

1. `*_md.enex` を Joplin へ Markdown としてインポートします。[page:1]
2. `*_html.enex` を Joplin へ HTML としてインポートします。[page:1]
3. CSV ログを見て、暗号化ノートや内部リンク付きノートを確認します。[code_file:210]

## 注意点

- HTML / Markdown の振り分けはヒューリスティックであり、100% 完全ではありません。[code_file:210]
- `--webclip-only-html` では、Web クリップとして明示されていない HTML 主体ノートも Markdown 側へ残ります。[code_file:210]
- 入力 ENEX 自体が壊れている場合は処理できないことがあります。[code_file:210]
- `has_note_link=yes` はリンクの存在確認であり、リンク修復そのものは行いません。[code_file:210][web:127]
- Evernote の暗号化テキストは移行先で扱いにくいことがあるため、`has_encrypted=yes` のノートは事前確認が有用です。[web:76][web:89][code_file:210]
