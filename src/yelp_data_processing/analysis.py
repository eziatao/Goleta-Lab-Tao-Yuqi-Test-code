"""Query records and summarize sentiment/aspects without counting 999."""
from collections import Counter
from .common import DataError, Table, require


def query_table(table, review_id=None, business=None, limit=20):
    require(table, ["ID"])
    if limit < 1:
        raise DataError("limit must be positive")
    if business is not None:
        require(table, ["business_name"])
    matches = [r for r in table.rows if (review_id is None or r["ID"] == review_id) and (business is None or r.get("business_name") == business)]
    return Table(table.columns[:], matches[:limit]), len(matches)


def analyze_table(table):
    require(table, ["ID", "business_name", "sentiment"])
    require(table, ["date" if "date" in table.columns else "Date"])
    aspects = [c for c in table.columns if c not in {"ID", "business_name", "sentiment", "date", "Date", "Positive", "Negative", "Neutral", "consistency", "business_aspect_consistency", "average_sentiment_10"} and not c.startswith("quads-")]
    businesses = Counter(r["business_name"] for r in table.rows)
    values = [r["sentiment"] for r in table.rows]
    summary = {
        "reviews": len(table.rows), "businesses": len(businesses),
        "positive_reviews": sum(v > 0 for v in values),
        "negative_reviews": sum(v < 0 for v in values),
        "zero_sentiment_reviews": sum(v == 0 for v in values),
        "mean_sentiment": sum(values) / len(values) if values else None,
        "business_counts": dict(sorted(businesses.items(), key=lambda item: (-item[1], item[0]))),
        "aspects": {},
    }
    for aspect in aspects:
        involved = [r[aspect] for r in table.rows if r.get(aspect) is not None and r[aspect] != 999]
        summary["aspects"][aspect] = {"involved_reviews": len(involved), "missing_reviews": len(table.rows) - len(involved), "net_count": sum(involved), "mean_net_count_when_involved": sum(involved) / len(involved) if involved else None}
    return summary
