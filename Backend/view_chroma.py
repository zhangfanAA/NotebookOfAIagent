"""查看 ChromaDB 向量数据库内容"""
import chromadb

client = chromadb.PersistentClient(path="./data/chroma_db")

# 列出所有集合
collections = client.list_collections()
print(f"集合数量: {len(collections)}")
for c in collections:
    print(f"  - {c.name}")

if not collections:
    print("没有集合，数据库为空")
    exit()

# 默认集合
collection = client.get_collection("learning_assistant")
total = collection.count()
print(f"\n集合: learning_assistant | 总文档数: {total}")

if total == 0:
    print("集合为空")
    exit()

# 获取所有数据
results = collection.get(include=["documents", "metadatas"])

for i, (doc_id, doc, meta) in enumerate(zip(results["ids"], results["documents"], results["metadatas"])):
    print(f"\n{'='*60}")
    print(f"[{i+1}/{total}] ID: {doc_id}")
    print(f"来源: {meta.get('source', '?')} | 页: {meta.get('page', '?')} | 类型: {meta.get('file_type', '?')}")
    print(f"内容: {doc[:200]}...")
