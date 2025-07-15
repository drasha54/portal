import os
import json
import argparse
import datetime
import requests
from bs4 import BeautifulSoup

BASE_URL      = "https://www.p-portal.go.jp"
SEARCH_PAGE   = "/pps-web-biz/UAA01/OAA0101"
SEARCH_ACTION = "/pps-web-biz/UAA01/OAA0100"

def get_csrf_and_cookies(session: requests.Session) -> str:
    """検索画面を開いて CSRF トークンを取得"""
    resp = session.get(BASE_URL + SEARCH_PAGE)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "_csrf"})
    if not token_input:
        raise RuntimeError("CSRF token not found")
    return token_input["value"]

def perform_search(
    session: requests.Session,
    token: str,
    case_name: str | None = None,
    start_from: str | None = None,
    start_to: str | None = None,
) -> tuple[str,str]:
    """元の検索ロジックそのまま。検索条件はキーワード or 日付指定から渡す"""
    data = {"_csrf": token, "OAA0102": "\u691c\u7d22"}
    if case_name:
        data["searchConditionBean.articleNm"] = case_name
    if start_from:
        data["searchConditionBean.publicStartDateFrom"] = start_from
    if start_to:
        data["searchConditionBean.publicStartDateTo"] = start_to
    resp = session.post(BASE_URL + SEARCH_ACTION, data=data, allow_redirects=False)
    resp.raise_for_status()
    if resp.status_code == 302 and "Location" in resp.headers:
        location = resp.headers["Location"]
        if not location.startswith("http"):
            location = BASE_URL + location
        result_resp = session.get(location)
        result_resp.raise_for_status()
        return result_resp.text, location
    return resp.text, resp.url

def post_to_slack(rows: list[list[str]], header_lines: list[str]):
    """検索結果およびヘッダー行を Slack Incoming Webhook へ投稿"""
    if not rows:
        return
    # ヘッダー＋タイトルのみを先頭10件分プレビュー
    preview_rows = []
    # ヘッダー行をそのまま
    for h in header_lines:
        preview_rows.append(h)
    # 各案件のタイトル（2列目：r[1]）だけを表示
    for r in rows:
        preview_rows.append(r[1])

    text_block = "\n".join(preview_rows)
    payload = {"text": text_block}
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("環境変数 SLACK_WEBHOOK_URL が設定されていません")
    resp = requests.post(
        webhook_url,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    resp.raise_for_status()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search p-portal with multiple keywords")
    parser.add_argument("--start-from", help="public start date from (YYYY/MM/DD)", default=None)
    parser.add_argument("--start-to",   help="public start date to   (YYYY/MM/DD)", default=None)
    args = parser.parse_args()

    # 日付: 昨日を固定
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y/%m/%d")
    start_from = args.start_from or yesterday
    start_to   = args.start_to   or yesterday

    # 検索キーワードそのまま
    keywords = ["データ", "システム", "AI", "人工知能", "機械学習", "web", "クラウド", "コンピュータ"]
    header_lines = [
        f"Search page URL: {BASE_URL + SEARCH_PAGE}",
        f"検索ワード：{', '.join(keywords)}"
    ]

    print(header_lines[0])
    print(header_lines[1])

    seen = set()
    all_results = []

    with requests.Session() as session:
        token = get_csrf_and_cookies(session)

        for kw in keywords:
            html, _ = perform_search(
                session, token,
                case_name=None,   # ← ここでキーワード検索
                start_from=start_from,
                start_to=start_to,
            )
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", {"class": "main-summit-info"})
            if not table:
                continue

            for row in table.select("tbody tr"):
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if not cells:
                    continue
                case_no = cells[0]
                if case_no in seen:
                    continue
                seen.add(case_no)
                all_results.append(cells)

    # コンソール出力は元のまま
    for r in all_results:
        print("\t".join(r))

    # Slack 投稿
    post_to_slack(all_results, header_lines)
