#!/usr/bin/env python3
"""完成した動画をYouTubeに投稿する。
必要な環境変数: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
任意: YT_PRIVACY (public / unlisted / private, 既定 public)
使い方: python3 upload_youtube.py data.json video.mp4
"""
import json, os, sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def main(dj, video):
    d = json.load(open(dj))
    dow = d["indices"][0]
    sign = "高" if dow["chg"] > 0 else "安"
    title = f"【米国市況】{d['date_speech']} NYダウ{int(abs(dow['chg'])):,}ドル{sign}・{d['headline']['status']} #shorts"
    lines = [f"{d['date_speech']}のニューヨーク市場をAIナビゲーターが60秒で解析。", ""]
    for grp in ("indices", "rates_fx", "commodities"):
        for it in d[grp]:
            cl = it.get("chg_label") or f"{it['chg']:+,.2f} ({it['pct']:+.2f}%)"
            lines.append(f"・{it['name']}: {it['value']:,.{it['dec']}f} ({cl})")
    lines += ["", "次の焦点: " + " ".join(d["next"]), "",
              "※本動画は情報提供のみを目的としたもので、投資助言ではありません。",
              "※データ: Yahoo Finance ほか。数値は取得時点のもので、正確性を保証するものではありません。", "",
              "#米国株 #NYダウ #ナスダック #ドル円 #ビットコイン #市況 #shorts"]
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title[:100], "description": "\n".join(lines)[:4900],
                    "tags": ["米国株", "市況", "NYダウ", "ナスダック", "S&P500", "ドル円", "金", "ビットコイン", "AI"],
                    "categoryId": "25", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
        "status": {"privacyStatus": os.environ.get("YT_PRIVACY", "public"), "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, mimetype="video/mp4", resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    print("投稿完了: https://youtube.com/shorts/" + res["id"])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
