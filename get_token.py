#!/usr/bin/env python3
"""【初回だけ・自分のPCで実行】YouTube投稿用のリフレッシュトークンを取得する。
1. Google Cloud でダウンロードした OAuth クライアントのJSONを client_secret.json としてこのフォルダに置く
2. pip install google-auth-oauthlib
3. python get_token.py  → ブラウザが開くので、投稿先チャンネルのGoogleアカウントで許可
4. 表示された3つの値を GitHub の Secrets に登録
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
cs = json.load(open("client_secret.json"))
cs = cs.get("installed") or cs.get("web")
print("\n=== GitHub Secrets に登録する値 ===")
print("YT_CLIENT_ID     =", cs["client_id"])
print("YT_CLIENT_SECRET =", cs["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
