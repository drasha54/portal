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


def perform_search(session: requests.Session, keyword: str, token: str):
    """Send POST request with search keyword and CSRF token."""
    data = {
        "_csrf": token,
        "searchConditionBean.articleNm": keyword,
        "OAA0102": "\u691c\u7d22",  # '検索' in Unicode
    }
    resp = session.post(BASE_URL + SEARCH_ACTION, data=data, allow_redirects=False)
    resp.raise_for_status()
    # Expect redirect to result page
    if resp.status_code == 302 and "Location" in resp.headers:
        location = resp.headers["Location"]
        if not location.startswith("http"):
            location = BASE_URL + location
        result_resp = session.get(location)
        result_resp.raise_for_status()
        return result_resp.text
    return resp.text


if __name__ == "__main__":
    # Example keyword. Modify as needed.
    keyword = "テスト"  # "test" in Japanese
    with requests.Session() as session:
        token = get_csrf_and_cookies(session)
        html = perform_search(session, keyword, token)
        soup = BeautifulSoup(html, "html.parser")
        results = []
        table = soup.find("table", {"class": "main-summit-info"})
        if table:
            for row in table.select("tbody tr"):
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if cells:
                    results.append(cells)
        for r in results:
            print("\t".join(r))
