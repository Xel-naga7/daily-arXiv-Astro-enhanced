import arxiv
import json
import os

# 获取分类列表
categories = os.getenv('CATEGORIES').split(',')
results = []

# 初始化 arxiv Client
client = arxiv.Client(
    page_size=50,
    delay_seconds=3,
    num_retries=3
)

for cat in categories:
    cat = cat.strip()
    if not cat:
        continue
    
    # 构建查询：按分类搜索并按提交时间倒序排列
    search = arxiv.Search(
        query=f'cat:{cat}',
        max_results=50,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    try:
        for result in client.results(search):
            # 格式化论文数据结构，保持与原格式一致
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

# 保存数据
os.makedirs('../data', exist_ok=True)
with open('../data/${today}.jsonl', 'w', encoding='utf-8') as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f'Successfully fetched {len(results)} papers via arxiv Python Client.')
