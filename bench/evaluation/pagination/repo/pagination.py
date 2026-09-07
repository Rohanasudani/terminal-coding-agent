def collect_records(fetch_page):
    records = []
    cursor = None
    while True:
        page = fetch_page(cursor)
        records.extend(page["items"])
        if not page["items"]:
            return records
        cursor = page["next_cursor"]
        if cursor is None:
            return records
