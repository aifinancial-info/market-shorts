#!/usr/bin/env python3
"""前日の米国市場の終値を取得し、動画用の data.json（数値・原稿・字幕）を作る。

- 数値: Yahoo Finance（yfinance）
- 「要因」「解析」「次の焦点」: ANTHROPIC_API_KEY があれば Claude がWeb検索して作成、
  なければ数値だけから機械的に作成
- 米国市場が休場だった日は終了コード 78 で終わる（=その日は投稿しない）
"""
import datetime as dt, json, os, re, sys
from zoneinfo import ZoneInfo
import yfinance as yf

ET, JST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Tokyo")
WD_JA = "月火水木金土日"; WD_EN = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

TICKERS = {
    "dow": "^DJI", "spx": "^GSPC", "ndq": "^IXIC",
    "tnx": "^TNX", "usdjpy": "JPY=X", "eurusd": "EURUSD=X",
    "gold": "GC=F", "wti": "CL=F", "btc": "BTC-USD",
}

# ---------- 読み上げ用の数字 ----------
def yomi_int(n):
    n = int(n); man, rest = divmod(n, 10000)
    return (f"{man}万" + (str(rest) if rest else "")) if man else str(rest)

def yomi_dec(x, d=2):
    s = f"{abs(x):.{d}f}".rstrip("0").rstrip(".")
    return s.replace(".", "点")

def get_series():
    out = {}
    for k, t in TICKERS.items():
        h = yf.Ticker(t).history(period="10d", interval="1d", auto_adjust=False)
        h = h.dropna(subset=["Close"])
        if len(h) < 3: raise RuntimeError(f"データ不足: {t}")
        out[k] = h
    return out

def last_session_date(spx):
    return spx.index[-1].tz_convert(ET).date() if spx.index[-1].tzinfo else spx.index[-1].date()

def rowvals(h):
    c = h["Close"].tolist(); return c[-1], c[-1] - c[-2], (c[-1] / c[-2] - 1) * 100, c[-2] - c[-3]

def headline(idx):
    dirs = [1 if x[1] > 0 else -1 if x[1] < 0 else 0 for x in idx]
    prev = 1 if idx[0][3] > 0 else -1
    if all(v < 0 for v in dirs):
        return {"status": "そろって" + ("続落" if prev < 0 else "反落"), "dir": -1}
    if all(v > 0 for v in dirs):
        return {"status": "そろって" + ("続伸" if prev > 0 else "反発"), "dir": 1}
    return {"status": "まちまち", "dir": 0}

def fallback_ai(v):
    """AIキー未設定時の機械的な解説。"""
    tnx_chg = v["tnx"][1]
    movers = sorted([("金", v["gold"][2]), ("原油", v["wti"][2]), ("ビットコイン", v["btc"][2]),
                     ("ナスダック", v["ndq"][2])], key=lambda x: -abs(x[1]))
    m = movers[0]
    factor = "長期金利の上昇" if tnx_chg > 0.03 else "長期金利の低下" if tnx_chg < -0.03 else ""
    return {
        "factor": factor,
        "analysis": [
            [f"米10年債 {v['tnx'][0]:.2f}%", ("上昇" if tnx_chg > 0 else "低下" if tnx_chg < 0 else "横ばい") + f"（{tnx_chg:+.2f}pt）"],
            [f"ドル円 {v['usdjpy'][0]:.2f}円", ("円安" if v["usdjpy"][1] > 0 else "円高") + "方向"],
            [f"最大の変動：{m[0]}", f"{m[1]:+.1f}%"],
        ],
        "analysis_speech": f"解析結果。米10年債利回りは{yomi_dec(v['tnx'][0])}パーセント。"
                           f"本日、最も大きく動いたのは{m[0]}で、{yomi_dec(m[1],1)}パーセントの{'上昇' if m[1] > 0 else '下落'}でした。",
        "analysis_sub": None,
        "next": ["本日", "米国の経済指標に注目"],
        "next_speech": "次の焦点は、本日発表される米国の経済指標です。",
    }

def claude_ai(v, date_ja):
    """Claude に Web 検索させて、要因・解説・次の焦点を作らせる。"""
    import anthropic
    client = anthropic.Anthropic()
    facts = (f"ダウ {v['dow'][0]:.2f} ({v['dow'][1]:+.2f}), S&P500 {v['spx'][0]:.2f} ({v['spx'][2]:+.2f}%), "
             f"ナスダック {v['ndq'][0]:.2f} ({v['ndq'][2]:+.2f}%), 米10年債 {v['tnx'][0]:.2f}% ({v['tnx'][1]:+.3f}), "
             f"ドル円 {v['usdjpy'][0]:.2f}, 金 {v['gold'][0]:.1f} ({v['gold'][2]:+.2f}%), "
             f"WTI {v['wti'][0]:.2f} ({v['wti'][2]:+.2f}%), BTC {v['btc'][0]:.0f} ({v['btc'][2]:+.2f}%)")
    prompt = f"""あなたは米国市況ショート動画の原稿担当です。{date_ja}のニューヨーク市場について、
Web検索で主な値動きの要因と、今週〜来週の最重要イベントを調べ、次のJSONだけを出力してください。
確認できない事実は書かないこと。数値は下の実データと矛盾させないこと。
実データ: {facts}

{{
 "factor": "株価の主因を10文字以内（例: 長期金利の上昇）",
 "analysis": [["見出し(12文字以内)", "補足(14文字以内)"], ["..","..."], ["..",".."]],
 "analysis_speech": "『解析結果。』で始まる読み上げ原稿、70〜90文字。英略語はカタカナ読み、小数点は『点』",
 "analysis_sub": "analysis_speech と同じ内容の字幕（英略語・数字は通常表記）",
 "next": ["日付 例: 10/2 (金)", "イベント名(10文字以内)"],
 "next_speech": "『次の焦点は、』で始まる一文"
}}"""
    msg = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"), max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    j = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    assert len(j["analysis"]) == 3 and len(j["next"]) == 2
    return j

def main(out="data.json"):
    s = get_series()
    sess = last_session_date(s["spx"])
    today_et = dt.datetime.now(ET).date()
    if os.environ.get("FORCE") != "1" and sess != today_et:
        print(f"米国市場は休場のようです（最終取引日 {sess}）。スキップします。"); sys.exit(78)
    v = {k: rowvals(h) for k, h in s.items()}
    if v["tnx"][0] > 20: v["tnx"] = tuple(x / 10 if i != 2 else x for i, x in enumerate(v["tnx"]))
    date_ja = f"{sess.month}月{sess.day}日"
    idx = [v["dow"], v["spx"], v["ndq"]]
    hl = headline(idx)

    ai = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try: ai = claude_ai(v, date_ja)
        except Exception as e: print("Claude解説の生成に失敗、機械的な解説に切替:", e)
    if not ai: ai = fallback_ai(v)
    hl["factor"] = ai.get("factor", "")

    def pct_word(p): return "上昇" if p > 0 else "下落"
    def small(p): return "小幅に" if abs(p) < 0.3 else ""
    d = {
        "date_label": f"{sess:%Y.%m.%d} ({WD_EN[sess.weekday()]})",
        "date_speech": date_ja,
        "headline": hl,
        "indices": [
            {"name": "NYダウ", "sub": "DOW JONES", "value": v["dow"][0], "chg": v["dow"][1], "pct": v["dow"][2], "dec": 2},
            {"name": "S&P500", "sub": "S&P 500", "value": v["spx"][0], "chg": v["spx"][1], "pct": v["spx"][2], "dec": 2},
            {"name": "ナスダック", "sub": "NASDAQ", "value": v["ndq"][0], "chg": v["ndq"][1], "pct": v["ndq"][2], "dec": 2},
        ],
        "rates_fx": [
            {"name": "米10年債利回り", "sub": "US 10Y", "value": v["tnx"][0], "unit": "%", "chg": round(v["tnx"][1], 3),
             "chg_label": "横ばい" if abs(v["tnx"][1]) < 0.005 else f"{v['tnx'][1]:+.2f}pt", "dec": 2, "pct": v["tnx"][2]},
            {"name": "ドル/円", "sub": "USD/JPY", "value": v["usdjpy"][0], "unit": "円", "chg": v["usdjpy"][1],
             "chg_label": f"{v['usdjpy'][1]:+.2f}円", "dec": 2, "pct": v["usdjpy"][2]},
            {"name": "ユーロ/ドル", "sub": "EUR/USD", "value": v["eurusd"][0], "unit": "", "chg": v["eurusd"][1],
             "chg_label": f"{v['eurusd'][1]:+.4f}", "dec": 4, "pct": v["eurusd"][2]},
        ],
        "commodities": [
            {"name": "NY金先物", "sub": "GOLD", "value": v["gold"][0], "unit": "$", "chg": v["gold"][1],
             "chg_label": f"{v['gold'][1]:+.2f} ({v['gold'][2]:+.2f}%)", "dec": 1, "pct": v["gold"][2]},
            {"name": "WTI原油", "sub": "CRUDE OIL", "value": v["wti"][0], "unit": "$", "chg": v["wti"][1],
             "chg_label": f"{v['wti'][1]:+.2f} ({v['wti'][2]:+.1f}%)", "dec": 2, "pct": v["wti"][2]},
            {"name": "ビットコイン", "sub": "BITCOIN", "value": v["btc"][0], "unit": "$", "chg": v["btc"][1],
             "chg_label": f"{v['btc'][2]:+.1f}% (6時時点)", "dec": 0, "pct": v["btc"][2]},
        ],
        "analysis": ai["analysis"],
        "next": ai["next"],
    }
    dw, sp, nq = v["dow"], v["spx"], v["ndq"]
    tn, fx, gd, wt, bt = v["tnx"], v["usdjpy"], v["gold"], v["wti"], v["btc"]
    fac = f"{hl['factor']}が、相場を左右しました。" if hl["factor"] else ""
    sc = {
        "intro": f"おはようございます。AIナビゲーターです。{date_ja}、ニューヨーク市場の解析結果を報告します。",
        "headline": f"結論から申し上げます。主要3指数は、{hl['status']}。{fac}",
        "indices": f"ダウ平均は{yomi_int(abs(dw[1]))}ドル{'高' if dw[1] > 0 else '安'}の、{yomi_int(dw[0])}ドル。"
                   f"エスアンドピー500は{yomi_dec(sp[2])}パーセント{'高' if sp[2] > 0 else '安'}。"
                   f"ナスダックは{small(nq[2])}{pct_word(nq[2])}しました。",
        "rates_fx": f"米10年債利回りは{yomi_dec(tn[0])}パーセント。"
                    f"ドル円は{int(fx[0])}円{int(round((fx[0] % 1) * 100))}銭。{'円安' if fx[1] > 0 else '円高'}方向です。",
        "commodities": f"金先物は{yomi_int(abs(gd[1]))}ドル{'高' if gd[1] > 0 else '安'}の{yomi_int(gd[0])}ドル。"
                       f"原油は{yomi_dec(wt[2],1)}パーセント{pct_word(wt[2])}。"
                       f"ビットコインは{yomi_int(bt[0] // 1000 * 1000)}ドル台で推移しています。",
        "analysis": ai["analysis_speech"],
        "outro": f"{ai['next_speech']}以上、AIナビゲーターでした。数字は、嘘をつきません。",
    }
    # 字幕（表示用：読み仮名ではなく通常表記）
    sub = dict(sc)
    sub["intro"] = sc["intro"].replace("ニューヨーク", "NY")
    sub["indices"] = (f"ダウ平均は{int(abs(dw[1])):,}ドル{'高' if dw[1] > 0 else '安'}の{int(dw[0]):,}ドル。"
                      f"S&P500は{abs(sp[2]):.2f}%{'高' if sp[2] > 0 else '安'}。ナスダックは{small(nq[2])}{pct_word(nq[2])}しました。")
    sub["rates_fx"] = (f"米10年債利回りは{tn[0]:.2f}%。ドル円は{int(fx[0])}円{int(round((fx[0] % 1) * 100))}銭。"
                       f"{'円安' if fx[1] > 0 else '円高'}方向です。")
    sub["commodities"] = (f"金先物は{int(abs(gd[1])):,}ドル{'高' if gd[1] > 0 else '安'}の{int(gd[0]):,}ドル。"
                          f"原油は{abs(wt[2]):.1f}%{pct_word(wt[2])}。ビットコインは{bt[0] // 1000 * 1000:,.0f}ドル台で推移しています。")
    sub["analysis"] = ai.get("analysis_sub") or sc["analysis"].replace("点", ".").replace("パーセント", "%")
    d["script"], d["subs"] = sc, sub
    json.dump(d, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"{out} を作成（{date_ja}のデータ）")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data.json")
