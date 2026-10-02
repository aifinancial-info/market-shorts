#!/usr/bin/env python3
"""完成した動画をInstagramリールとして投稿する（Instagram API / Instagramログイン方式）。
必要な環境変数: IG_ACCESS_TOKEN, IG_USER_ID
使い方: python3 upload_instagram.py data.json video.mp4
"""
import json, os, sys, time, urllib.parse, urllib.request

API = "https://graph.instagram.com/v25.0"


def call(method, url, data=None, headers=None, body=None):
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {e.code}: {e.read().decode()[:500]}")


def caption(d):
    dow = d["indices"][0]
    sign = "高" if dow["chg"] > 0 else "安"
    lines = [f"【米国市況】{d['date_speech']} NYダウ{int(abs(dow['chg'])):,}ドル{sign}・{d['headline']['status']}", "",
             f"{d['date_speech']}のニューヨーク市場をAIナビゲーターが60秒で解析。", ""]
    for grp in ("indices", "rates_fx", "commodities"):
        for it in d[grp]:
            cl = it.get("chg_label") or f"{it['chg']:+,.2f} ({it['pct']:+.2f}%)"
            lines.append(f"・{it['name']}: {it['value']:,.{it['dec']}f} ({cl})")
    lines += ["", "次の焦点: " + " ".join(d["next"]), "",
              "※情報提供のみを目的としたもので、投資助言ではありません。", "",
              "#米国株 #米国株投資 #投資 #NYダウ #ナスダック #SP500 #ドル円 #為替 #金 #ビットコイン #市況 #資産運用 #株式投資"]
    return "\n".join(lines)[:2100]


def main(dj, video):
    tok, uid = os.environ["IG_ACCESS_TOKEN"].strip(), os.environ["IG_USER_ID"].strip()

    # 長期トークンの有効期限を延長（60日）。発行から24時間以上たっていれば延長される
    try:
        r = call("GET", "https://graph.instagram.com/refresh_access_token?" +
                 urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tok}))
        days = int(r.get("expires_in", 0)) // 86400
        print(f"トークン有効期限: あと約{days}日")
        if r.get("access_token") and r["access_token"] != tok:
            print("::warning::トークンが新しい値に更新されました。IG_ACCESS_TOKEN の更新が必要です。")
            tok = r["access_token"]
    except Exception as e:
        print("トークン延長はスキップ:", str(e)[:200])

    d = json.load(open(dj))
    size = os.path.getsize(video)

    # 1) アップロード用コンテナを作成（再開可能アップロード）
    c = call("POST", f"{API}/{uid}/media", {
        "media_type": "REELS", "upload_type": "resumable", "caption": caption(d),
        "share_to_feed": "true", "access_token": tok})
    cid = c["id"]
    print("コンテナ作成:", cid)

    # 2) 動画ファイル本体を送る
    with open(video, "rb") as f:
        data = f.read()
    up = call("POST", f"https://rupload.facebook.com/ig-api-upload/v25.0/{cid}", body=data, headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
        "Content-Type": "application/octet-stream"})
    print("アップロード:", up)

    # 3) Instagram側の処理完了を待つ（最大約10分）
    for _ in range(60):
        s = call("GET", f"{API}/{cid}?" + urllib.parse.urlencode({"fields": "status_code,status", "access_token": tok}))
        st = s.get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram側の処理でエラー: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram側の処理が10分以内に終わりませんでした")

    # 4) 公開
    p = call("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    m = call("GET", f"{API}/{p['id']}?" + urllib.parse.urlencode({"fields": "permalink", "access_token": tok}))
    print("Instagram投稿完了:", m.get("permalink", p["id"]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
