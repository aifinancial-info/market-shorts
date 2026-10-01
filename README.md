# 米国市況ショート 自動投稿セット

毎週 火〜土 の朝6時20分ごろ（日本時間）に、前日の米国市場の終値を取ってきて60秒の縦型動画を作り、YouTubeへ自動投稿します。
動かす場所は GitHub Actions（無料）です。PCの電源が切れていても動きます。

## ファイル
| ファイル | 役割 |
|---|---|
| `fetch_data.py` | 終値の取得（Yahoo Finance）と、原稿・字幕の作成。米国が休場の日はスキップ |
| `make_video.py` | 動画の作成（1080×1920、ぴったり60秒、AI音声ナレーション付き） |
| `upload_youtube.py` | YouTubeへの投稿（タイトル・説明文・タグは自動作成） |
| `get_token.py` | 初回だけ自分のPCで実行し、YouTube投稿の許可をもらう |
| `.github/workflows/daily.yml` | 毎朝の自動実行のスケジュール |
| `data.json` | サンプルデータ（9/29分） |

## セットアップ手順

### 1. YouTubeチャンネルを作る
1. 投稿用のGoogleアカウントでYouTubeにログインし、右上のアイコンから「チャンネルを作成」
2. 個人名と分けたいときは「ブランドアカウント」でチャンネル名を付けて作成
3. 電話番号の確認を済ませておく（15分を超える動画やカスタムサムネイルに必要）

### 2. Google Cloud で YouTube API を使えるようにする
1. https://console.cloud.google.com/ で新しいプロジェクトを作る（例: market-shorts）
2. 「APIとサービス」→「ライブラリ」→ **YouTube Data API v3** を有効にする
3. 「OAuth同意画面」を作成（外部／アプリ名・メールを入力）し、自分をテストユーザーに追加
4. **公開ステータスを「本番環境」にする**（「テスト」のままだと許可が7日で切れて投稿が止まります）
5. 「認証情報」→「OAuthクライアントID」→ 種類「デスクトップアプリ」で作成し、JSONをダウンロード

### 3. 投稿の許可（リフレッシュトークン）を取る ※自分のPCで1回だけ
1. ダウンロードしたJSONを `client_secret.json` という名前でこのフォルダに置く
2. `pip install google-auth-oauthlib` → `python get_token.py`
3. ブラウザでチャンネルのアカウントを選んで許可（「確認されていないアプリ」と出たら「詳細」→「移動」）
4. 表示された3つの値を控える（**他人に見せない**）

### 4. GitHub に置いて Secrets を登録
1. GitHubで**非公開（Private）**リポジトリを作り、このフォルダの中身を全部アップロード
   （`client_secret.json` はアップロードしない）
2. Settings → Secrets and variables → Actions → New repository secret で登録
   - `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN`
   - `ANTHROPIC_API_KEY`（任意。入れるとClaudeがニュースを調べて「要因」「解析」「次の焦点」を書きます。
     入れない場合は数値だけから機械的に作ります）

### 5. テスト実行
Actions タブ →「米国市況ショート 毎朝自動投稿」→ Run workflow（公開設定 `private`、休場判定の無視 `1`）
→ 数分後、YouTube Studio に非公開で上がっていれば成功。以後は毎朝自動で動きます。

## 注意点
- **APIの審査について**: 審査前のGoogle Cloudプロジェクトから投稿した動画は、YouTube側で自動的に「非公開」に固定されます。
  一般公開するには、YouTube API Services の監査（Audit）フォームを申請して承認を受けてください（無料・数日〜数週間）。
  承認されるまでは、毎朝非公開で上がった動画を YouTube Studio で「公開」に切り替えれば運用できます。
- 実行時刻は GitHub の混雑で数分〜十数分遅れることがあります。
- 米国市場の終値確定は日本時間で夏時間 5:00／冬時間 6:00（11月〜3月）。6:20実行なので両方に対応しています。
- 為替・金・原油・ビットコインは24時間動いているため「実行時点の値」です。
- 読み上げ音声は Open JTalk（無料・商用可）を使用。声を変えたい場合は `make_video.py` の `synth()` を差し替えます。
