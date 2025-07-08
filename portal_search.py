import argparse
import datetime
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.p-portal.go.jp"
SEARCH_PAGE = "/pps-web-biz/UAA01/OAA0101"
SEARCH_ACTION = "/pps-web-biz/UAA01/OAA0100"
RESULT_PAGE = "/pps-web-biz/UAA01/OAA0106"

def get_csrf_and_cookies(session: requests.Session):
    """Fetch the search page to obtain CSRF token and cookies."""
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
):
    """Send POST request with optional search parameters and CSRF token.
    Returns a tuple of the resulting HTML and the URL of the results page.
    """
    data = {"_csrf": token, "OAA0102": "\u691c\u7d22"}  # 検索ボタン押下値
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search p-portal with multiple keywords")
    parser.add_argument("--start-from", help="public start date from (YYYY/MM/DD)", default=None)
    parser.add_argument("--start-to", help="public start date to (YYYY/MM/DD)", default=None)
    args = parser.parse_args()

    today = datetime.date.today().strftime("%Y/%m/%d")
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y/%m/%d")

    start_from = yesterday
    start_to = yesterday

    # 最初に検索フォームの URL を表示
    print(f"Search page URL: {BASE_URL + SEARCH_PAGE}")

    keywords = ["データ", "システム", "サーバ", "web", "コンピュータ", "ネットワーク", "情報", "セキュリティ", "AI", "人工知能"]
    print(f"検索ワード：{', '.join(keywords)}")
    seen = set()       # 案件番号で重複チェック
    all_results = []   # 重複を除いた結果リスト

    with requests.Session() as session:
        token = get_csrf_and_cookies(session)

        for kw in keywords:
            html, _ = perform_search(
                session,
                token,
                case_name=None,
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
                case_no = cells[0]  # 先頭列を案件番号と仮定
                if case_no in seen:
                    continue
                seen.add(case_no)
                all_results.append(cells)

    # 重複を除いた検索結果のみを表示
    for r in all_results:
        print("\t".join(r))
