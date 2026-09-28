import arxiv
import feedparser
import json
import os

# 1. 关键修复：全局设置 feedparser 的 User-Agent，防止 arXiv API 返回 406 错误
feedparser.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# 获取分类列表
categories = os.getenv('CATEGORIES', 'astro-ph.HE,gr-qc').split(',')
results = []

# 2. 初始化 arxiv Client
client = arxiv.Client(
    page_size=50,
    delay_seconds=3,
    num_retries=3
)

for cat in categories:
    cat = cat.strip()
    if not cat:
        continue
    
    # 构建查询
    search = arxiv.Search(
        query=f'cat:{cat}',
        max_results=50,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    try:
        for result in client.results(search):
            paper_id = result.entry_id.split('/')[-1]
            title = result.title.replace('\n', ' ')
            summary = result.summary.replace('\n', ' ')
            published = result.published.strftime('%Y-%m-%d')
            authors = [author.name for author in result.authors]

            item = {
                'id': paper_id,
                'title': title,
                'summary': summary,
                'published': published,
                'authors': authors,
                'categories': [cat]
            }
            results.append(item)
    except Exception as e:
        print(f'Error fetching category {cat}: {e}')

# 保存结果
os.makedirs('../data', exist_ok=True)
with open('../data/${today}.jsonl', 'w', encoding='utf-8') as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f'Successfully fetched {len(results)} papers via arxiv Python Client.')
