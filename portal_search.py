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
) -> tuple[str, str]:
    """Send POST request with optional search parameters and CSRF token.

    Returns a tuple of the resulting HTML and the URL of the results page.
    """
    data = {"_csrf": token, "OAA0102": "\u691c\u7d22"}
    if case_name:
        data["searchConditionBean.articleNm"] = case_name
    if start_from:
        data["searchConditionBean.publicStartDateFrom"] = start_from
    if start_to:
        data["searchConditionBean.publicStartDateTo"] = start_to
    resp = session.post(BASE_URL + SEARCH_ACTION, data=data, allow_redirects=False)
    resp.raise_for_status()
    # Expect redirect to result page
    if resp.status_code == 302 and "Location" in resp.headers:
        location = resp.headers["Location"]
        if not location.startswith("http"):
            location = BASE_URL + location
        result_resp = session.get(location)
        result_resp.raise_for_status()
        return result_resp.text, location
    return resp.text, resp.url


def parse_results(html: str) -> list[list[str]]:
    """Extract rows from the results table."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "main-summit-info"})
    rows: list[list[str]] = []
    if table:
        for row in table.select("tbody tr"):
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if cells:
                rows.append(cells)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search p-portal with detailed conditions")
    parser.add_argument("--case", help="procurement case name keyword", default=None)
    parser.add_argument(
        "--cases",
        nargs="*",
        help="list of keywords to search separately",
        default=[],
    )
    parser.add_argument(
        "--start-from", help="public start date from (YYYY/MM/DD)", default=None
    )
    parser.add_argument("--start-to", help="public start date to (YYYY/MM/DD)", default=None)
    args = parser.parse_args()

    # If no date parameters are provided, use today's date for both
    today = datetime.date.today().strftime("%Y/%m/%d")
    start_from = args.start_from or today
    start_to = args.start_to or today

    case_keywords: list[str] = []
    if args.case:
        case_keywords.append(args.case)
    if args.cases:
        case_keywords.extend(args.cases)
    if not case_keywords:
        case_keywords.append(None)

    with requests.Session() as session:
        token = get_csrf_and_cookies(session)
        seen: set[tuple[str, ...]] = set()
        combined: list[list[str]] = []
        for kw in case_keywords:
            html, results_url = perform_search(
                session,
                token,
                case_name=kw,
                start_from=start_from,
                start_to=start_to,
            )
            print(f"Results URL for '{kw or ''}': {results_url}")
            for row in parse_results(html):
                key = tuple(row)
                if key not in seen:
                    seen.add(key)
                    combined.append(row)

        for r in combined:
            print("\t".join(r))
