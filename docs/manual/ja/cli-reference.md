# CLI リファレンス

すべてのサブコマンドは以下の共通規約に従います:

- **stdout**: コマンド本来の出力（テーブル / profile 名 / プロンプト用エスケープ等）
- **stderr**: 進捗メッセージ・警告・エラー
- **exit code**:
  - `0` 成功 / 一致
  - `1` 期待条件未達（ミスマッチ / 該当 profile なし 等の予期される失敗）
  - `2` ツールエラー（config 不在、不正な YAML、外部ツール失敗 等）

`prompt` のみ例外で、シェル動作を止めないため常に exit 0 を返します。

## 共通

```
gospelo-identity --help        # サブコマンド一覧
gospelo-identity --version     # バージョン
```

設定ファイルパスは `GOSPELO_IDENTITY_CONFIG` 環境変数で上書きできます（テスト用）。

---

## init

```
gospelo-identity init [--force] [--from-template] [--show-example]
```

`~/.config/gospelo-identity/config.yml` を作成します。

オプションなしの場合は対話的に profile を入力します。既存ファイルがある場合は上書き確認のプロンプトが出ます。`--force` で確認をスキップ。

非対話モード:

- `--from-template` — 同梱テンプレート (`gospelo_identity/templates/config.template.yml`) を `~/.config/gospelo-identity/config.yml` にコピーし、`$EDITOR` (未設定時は `vi`) で開きます。対話入力はスキップ。既存ファイルがある場合は `Overwrite? [y/N]` で確認 (`--force` でスキップ)。コピー後にプレースホルダ (`<your-name>` 等) を実値に置き換えてください。
- `--show-example` — 同梱テンプレートの内容を stdout に出力します。`gospelo-identity init --show-example > my-config.yml` のようにリダイレクトでカスタムパスへ書き出せます。常に exit 0。

`--from-template` と `--show-example` は同時指定できません (exit 2)。

サンプル設定は [examples/](https://github.com/gospelo-dev/identity/tree/main/examples) にも 3 種 (basic / minimal / advanced) 用意しています。

| 終了コード | 意味 |
|---|---|
| 0 | 保存成功、または既存ファイルを残して中断、または `--show-example` 成功 |
| 1 | 中断（Ctrl-C / EOF / 上書き拒否）、または profile 未入力 |
| 2 | 保存時の I/O エラー、テンプレート不在、`--from-template` と `--show-example` の併用、`$EDITOR` バイナリ不在 |

---

## list

```
gospelo-identity list
```

登録済み profile をテーブルで表示します。

| 終了コード | 意味 |
|---|---|
| 0 | 1 つ以上の profile が登録済み |
| 1 | profile が空（理論上は init が防ぎますが念のため） |
| 2 | config 不在・不正 |

---

## detect

```
gospelo-identity detect [--cwd PATH]
```

現在のディレクトリ（または `--cwd` で指定したディレクトリ）にマッチする profile 名を 1 行で出力します。スクリプトから profile 名だけを取りたい場合に使用。

| 終了コード | 意味 |
|---|---|
| 0 | profile を解決できた |
| 1 | どの profile にもマッチせず、`default_profile` も未設定 |
| 2 | config 不在・不正 |

---

## check

```
gospelo-identity check [--cwd PATH]
```

期待 profile と実状態（`git config user.name` / `user.email` / `gh` CLI のアクティブログイン）を比較してテーブル表示します。

出力例:

```
=== Identity Check ===
Working dir: /Users/you/projects/gospelo-dev/review
Matched profile: oss (via pattern: ~/projects/gospelo-dev/**)

[git]
  user.name  : your-oss-login  (expected: your-oss-login )  OK
  user.email : you@example.com (expected: you@example.com)  OK
[gh CLI]
  login      : your-work-login (expected: your-oss-login )  NG

WARNING: gh CLI account does not match expected profile.
Run `gospelo-identity switch oss` to fix.
```

| 終了コード | 意味 |
|---|---|
| 0 | すべて一致 |
| 1 | 1 つ以上 mismatch、または profile が解決できず |
| 2 | config 不在・不正、外部ツール失敗 |

---

## switch

```
gospelo-identity switch <profile> [--global] [--dry-run] [--cwd PATH]
```

指定 profile のために `git config user.name` / `user.email` を設定し、`gh auth switch -u <account>` を実行します。

- デフォルトは `git config --local`（カレントリポジトリのみ）
- `--global` でユーザー全体
- `--dry-run` は副作用なしで予定だけ表示

| 終了コード | 意味 |
|---|---|
| 0 | git config と gh switch の両方が成功 |
| 1 | 部分成功（片方だけ失敗） |
| 2 | profile 不在、両方失敗、外部ツール不在 |

`--local`（既定）で `cwd` が git work tree の外にある場合は exit 2 で停止します。`--global` を使うか、リポジトリに移動してください。

---

## prompt

```
gospelo-identity prompt [--format {plain,color,ps1}] [--show-mismatch] [--cwd PATH]
```

シェルプロンプト統合用 helper。マッチした profile 名を `[name]` の形式で出力します。マッチしない・config 未作成のときは空文字列を返します。常に exit 0。

`--format`:

- `plain` (既定) — `[oss]`
- `color` — ANSI エスケープ付き（`\033[33m[oss]\033[0m`）
- `ps1` — bash の `PS1` 用に readline 非印字マーカー `\[ \]` で囲む

`--show-mismatch` を付けると、git/gh 状態が profile と不一致の場合に `[oss !]` のように `!` を付与し、`color` / `ps1` では赤色で表示します。

bash の例:

```bash
PS1='$(gospelo-identity prompt --format=ps1 --show-mismatch) \w \$ '
```

zsh の例（`PROMPT` で使う場合は `setopt PROMPT_SUBST` が必要）:

```zsh
setopt PROMPT_SUBST
PROMPT='%F{yellow}$(gospelo-identity prompt --format=plain --show-mismatch)%f %~ %# '
```
