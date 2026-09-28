import arxiv
import feedparser
import urllib.request
import json
import os

# 1. 强行全局设置 User-Agent，绕过 arXiv 的 HTTP 406 限制
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
feedparser.USER_AGENT = USER_AGENT

# 修改 urllib 默认请求头
opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', USER_AGENT)]
urllib.request.install_opener(opener)

# 2. 读取环境变量或分类列表
categories = os.getenv('CATEGORIES').split(',')
results = []

client = arxiv.Client(
    page_size=50,
    delay_seconds=3,
    num_retries=3
)

for cat in categories:
    cat = cat.strip()
    if not cat:
        continue
    
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

# 3. 只有当确实抓取到数据时才写入文件，确保 Workflow 不会因为空数据报错
if results:
    os.makedirs('../data', exist_ok=True)
    today = os.getenv('TODAY', 'today') # 根据你的文件名变量配置
    file_path = f'../data/{today}.jsonl'
    
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    print(f'Successfully fetched {len(results)} papers via arxiv Python Client.')
else:
    print('No papers were fetched from any category.')
    exit(1) # 如果一个论文都没抓到，显式抛出错误供 Workflow 拦截
