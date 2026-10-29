import arxiv
import json
import os
import re
import subprocess
import sys
from datetime import datetime


# ============================================================
# Configuration
# ============================================================

categories_env = os.environ.get("CATEGORIES", "").strip()
today_env = os.environ.get("TODAY", "").strip()

if not categories_env:
    print("ERROR: CATEGORIES environment variable is empty.")
    sys.exit(1)

if not today_env:
    print("ERROR: TODAY environment variable is empty.")
    sys.exit(1)

try:
    target_date = datetime.strptime(today_env, "%Y-%m-%d").date()
except ValueError:
    print(f"ERROR: Invalid TODAY format: {today_env}")
    print("Expected format: YYYY-MM-DD")
    sys.exit(1)


categories = [
    category.strip()
    for category in categories_env.split(",")
    if category.strip()
]

if not categories:
    print("ERROR: No valid arXiv categories found.")
    sys.exit(1)


print("=" * 60)
print("arXiv Daily Crawler")
print("=" * 60)
print(f"Target date : {target_date}")
print(f"Categories  : {', '.join(categories)}")
print("=" * 60)


# ============================================================
# Historical deduplication
# ============================================================

def load_historical_paper_ids():
    """Return base arXiv IDs already published in earlier daily files."""
    git_ref = os.environ.get("HISTORICAL_DATA_REF", "").strip()
    if not git_ref:
        return set()

    try:
        file_list = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                git_ref,
                "data",
            ],
            text=True,
        ).splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            f"WARNING: Could not inspect historical data from {git_ref}: "
            f"{type(exc).__name__}: {exc}"
        )
        return set()

    historical_ids = set()
    daily_file_pattern = re.compile(r"^data/\d{4}-\d{2}-\d{2}\.jsonl$")

    for file_path in file_list:
        if not daily_file_pattern.match(file_path):
            continue

        try:
            content = subprocess.check_output(
                ["git", "show", f"{git_ref}:{file_path}"],
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(
                f"WARNING: Could not read historical file {file_path}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue

            try:
                item = json.loads(line)
                paper_id = item.get("id", "").strip()
                if paper_id:
                    historical_ids.add(paper_id.split("v")[0])
            except json.JSONDecodeError as exc:
                print(
                    f"WARNING: Ignoring invalid JSON in {file_path}:{line_number}: "
                    f"{exc}"
                )

    print(
        f"Historical deduplication: found {len(historical_ids)} "
        "previously crawled papers."
    )
    return historical_ids


# ============================================================
# arXiv client
# ============================================================

client = arxiv.Client(
    page_size=100,
    delay_seconds=3,
    num_retries=5,
)


# ============================================================
# Crawl
# ============================================================

papers = {}
historical_ids = load_historical_paper_ids()
skipped_historical_count = 0
failed_categories = []

# Safety limit PER CATEGORY.
#
# Normally the crawler stops as soon as it reaches papers older
# than target_date. This exists only to prevent runaway crawling
# if something unexpected happens.
MAX_RESULTS_PER_CATEGORY = 1000


for category in categories:

    print()
    print(f"[{category}] Fetching...")

    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=MAX_RESULTS_PER_CATEGORY,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    category_count = 0
    inspected_count = 0
    category_target_date = None

    try:

        for result in client.results(search):

            inspected_count += 1

            published_date = result.published.date()

            if published_date > target_date:
                continue

            if category_target_date is None:
                category_target_date = published_date
                print(
                    f"[{category}] Using latest available date: "
                    f"{category_target_date}"
                )

            if published_date < category_target_date:
                print(
                    f"[{category}] Reached older papers "
                    f"({published_date}). Stop."
                )
                break

            paper_id = result.entry_id.rsplit("/", 1)[-1]

            # Remove version suffix for deduplication:
            #
            # 2609.12345v1 -> 2609.12345
            # 2609.12345v2 -> 2609.12345
            #
            # The stored ID itself is left unchanged.
            base_id = paper_id.split("v")[0]

            if base_id in historical_ids:
                skipped_historical_count += 1
                continue

            if base_id in papers:

                # Merge categories in case the same paper appears
                # in multiple configured category searches.
                existing_categories = set(
                    papers[base_id]["categories"]
                )

                existing_categories.update(result.categories)

                papers[base_id]["categories"] = sorted(
                    existing_categories
                )

                continue

            paper = {
                "id": paper_id,
                "title": result.title.replace("\n", " ").strip(),
                "summary": result.summary.replace("\n", " ").strip(),
                "published": result.published.strftime(
                    "%Y-%m-%d"
                ),
                "authors": [
                    author.name
                    for author in result.authors
                ],
                "categories": list(result.categories),
            }

            papers[base_id] = paper
            category_count += 1

        print(
            f"[{category}] "
            f"Inspected: {inspected_count}, "
            f"new unique papers: {category_count}"
        )

    except Exception as exc:

        failed_categories.append(category)

        print(
            f"ERROR fetching category {category}: "
            f"{type(exc).__name__}: {exc}"
        )


# ============================================================
# Fail if every category failed
# ============================================================

if len(failed_categories) == len(categories):

    print()
    print("ERROR: All arXiv category requests failed.")
    print(
        "Failed categories: "
        + ", ".join(failed_categories)
    )

    sys.exit(1)


# Partial failure should also be visible.
#
# Otherwise you could silently publish an incomplete daily file.
if failed_categories:

    print()
    print(
        "ERROR: Some categories failed. "
        "Refusing to publish incomplete data."
    )

    print(
        "Failed categories: "
        + ", ".join(failed_categories)
    )

    sys.exit(1)


# ============================================================
# Sort
# ============================================================

results = list(papers.values())

results.sort(
    key=lambda item: item["id"],
    reverse=True,
)


# ============================================================
# Write output
# ============================================================

output_dir = "../data"
os.makedirs(output_dir, exist_ok=True)

file_path = os.path.join(
    output_dir,
    f"{today_env}.jsonl"
)

# Write to temporary file first.
#
# This prevents a failed/incomplete crawl from destroying an
# already valid daily file.
temporary_path = file_path + ".tmp"

try:

    with open(
        temporary_path,
        "w",
        encoding="utf-8"
    ) as file:

        for item in results:

            file.write(
                json.dumps(
                    item,
                    ensure_ascii=False
                )
                + "\n"
            )

    os.replace(
        temporary_path,
        file_path
    )

except Exception as exc:

    if os.path.exists(temporary_path):
        os.remove(temporary_path)

    print(
        f"ERROR writing output file: {exc}"
    )

    sys.exit(1)


# ============================================================
# Summary
# ============================================================

print()
print("=" * 60)
print("Crawl completed")
print("=" * 60)

print(
    f"Date             : {target_date}"
)

print(
    f"Unique papers    : {len(results)}"
)

print(
    f"Skipped historical duplicates: {skipped_historical_count}"
)

print(
    f"Output           : {file_path}"
)

print("=" * 60)
