import urllib.request
import xml.etree.ElementTree as ET
import json
import os

categories = os.getenv('CATEGORIES', 'cs.AI').split(',')
base_url = 'http://export.arxiv.org/api/query?'
results = []

for cat in categories:
    cat = cat.strip()
    query = f'search_query=cat:{cat}&max_results=50&sortBy=submittedDate&sortOrder=descending'
    url = base_url + query
    try:
        with urllib.request.urlopen(url) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
                paper_id = entry.find('atom:id', ns).text.split('/')[-1]
                published = entry.find('atom:published', ns).text[:10]
                authors = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)]
                
                # 仅保留当天或符合条件的数据（根据项目需求，这里写入解析项）
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

# 写入目标 jsonl 文件
os.makedirs('../data', exist_ok=True)
with open(f'../data/${{today}}.jsonl', 'w', encoding='utf-8') as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
print(f'Successfully fetched {len(results)} papers via arXiv API.')
