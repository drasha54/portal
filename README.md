# portal

Simple script for searching [p-portal](https://www.p-portal.go.jp).
If no dates are provided, the script searches only entries added today.

```
python portal_search.py --case "入札" --start-from 2024/06/01 --start-to 2024/06/30

# search today's entries
python portal_search.py --case "入札"

# search multiple keywords and merge results
python portal_search.py --cases データ システム サーバ web
```
