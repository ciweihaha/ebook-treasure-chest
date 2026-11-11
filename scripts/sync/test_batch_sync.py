#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量测试脚本：根据书籍ID批量处理并生成md文件
测试范围：ID 1-1000
"""

import asyncio
import aiohttp
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
import json
import sys

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from parse_book_detail_enhanced import parse_book_detail_enhanced

# 尝试导入配置文件，如果不存在则使用环境变量
import os
try:
    from config import BOOK_SITE_DOMAIN
except ImportError:
    # 如果配置文件不存在，尝试从环境变量读取（GitHub Actions会使用这种方式）
    BOOK_SITE_DOMAIN = os.getenv("BOOK_SITE_DOMAIN", "")
    if not BOOK_SITE_DOMAIN:
        print("⚠️  警告：未找到配置文件 config.py，也未设置环境变量 BOOK_SITE_DOMAIN")
        print("   本地运行：请复制 config.py.example 为 config.py 并配置 BOOK_SITE_DOMAIN")
        print("   GitHub Actions：请在 Repository Settings > Secrets 中添加 BOOK_SITE_DOMAIN")
        print("   或设置环境变量: export BOOK_SITE_DOMAIN='https://www.dushupai.com'")
        sys.exit(1)

# 配置
BASE_URL = f"{BOOK_SITE_DOMAIN}/book-content-{{}}.html"
# 输出目录：根据环境变量决定是测试目录还是正式目录
OUTPUT_DIR_ENV = os.getenv("OUTPUT_DIR", "md_test")
if OUTPUT_DIR_ENV == "md":
    OUTPUT_DIR = Path(__file__).parent.parent.parent / "md"  # 正式目录
else:
    OUTPUT_DIR = Path(__file__).parent.parent.parent / "md_test"  # 测试目录
PROCESSED_IDS_FILE = OUTPUT_DIR / "processed_ids.json"
STATS_FILE = OUTPUT_DIR / "stats.json"
MAX_BOOK_ID_FILE = OUTPUT_DIR / "max_book_id.json"  # 记录最大书籍ID

# 并发配置
MAX_CONCURRENT = 20  # 最大并发数
REQUEST_DELAY = 0.5  # 请求延迟（秒）


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不合法字符
    
    Args:
        filename: 原始文件名
    
    Returns:
        清理后的文件名
    """
    # 替换不合法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # 移除首尾空格和点
    filename = filename.strip(' .')
    
    # 限制长度
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename or "未命名"


def generate_md_file(tag_name: str, books: List[Dict], output_dir: Path) -> Path:
    """
    生成Markdown文件
    
    Args:
        tag_name: 标签名称
        books: 书籍列表
        output_dir: 输出目录
    
    Returns:
        生成的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 清理文件名
    safe_filename = sanitize_filename(tag_name)
    file_path = output_dir / f"{safe_filename}.md"
    
    # 过滤有效书籍（必须有书名和下载链接）
    valid_books = []
    for book in books:
        title = book.get('title', '').strip()
        # 优先使用实际下载链接（诚通网盘链接），避免使用下载页面链接（包含敏感域名）
        download_url = book.get('download_url', '').strip()
        
        # 如果没有实际下载链接，跳过该书（不包含下载页面链接以保护隐私）
        if not download_url:
            continue
        
        if title and download_url:
            valid_books.append({
                'title': title,
                'author': book.get('author', '未知').strip() or '未知',
                'download_url': download_url
            })
    
    if not valid_books:
        return None
    
    # 生成Markdown内容
    lines = []
    lines.append("| 书名 | 作者 | epub/mobi/azw3 |")
    lines.append("| --- | --- | --- |")
    
    for book in valid_books:
        # 转义Markdown特殊字符
        title_escaped = book['title'].replace('|', '\\|')
        author_escaped = book['author'].replace('|', '\\|')
        # 修改下载链接：将 ?pwd= 改成 ?p=
        download_url = book['download_url'].replace('?pwd=', '?p=')
        
        # 隐私保护：如果下载链接包含敏感域名，移除该书籍（不生成到md文件）
        # 这样可以确保GitHub仓库中不包含敏感域名
        if download_url and BOOK_SITE_DOMAIN in download_url:
            # 跳过包含敏感域名的链接（通常是下载页面链接）
            # 只保留诚通网盘的实际下载链接
            continue
        
        download_link = f"[下载]({download_url})"
        
        lines.append(f"| {title_escaped} | {author_escaped} | {download_link} |")
    
    # 写入文件
    file_path.write_text('\n'.join(lines), encoding='utf-8')
    return file_path


async def fetch_book_async(session: aiohttp.ClientSession, book_id: int, semaphore: asyncio.Semaphore) -> Dict:
    """
    异步获取书籍信息
    
    Args:
        session: aiohttp会话
        book_id: 书籍ID
        semaphore: 信号量控制并发
    
    Returns:
        书籍信息字典，失败返回None
    """
    async with semaphore:
        url = BASE_URL.format(book_id)
        
        try:
            # 添加延迟避免请求过快
            await asyncio.sleep(REQUEST_DELAY)
            
            # 使用同步请求（因为parse_book_detail_enhanced是同步的）
            # 在实际生产环境中，可以改为异步版本
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, parse_book_detail_enhanced, url)
            
            # 检查是否成功获取到书名（判断书籍是否存在）
            if result.get('title'):
                result['book_id'] = str(book_id)
                return result
            else:
                # 页面存在但无书名：该 ID 永久缺失（如下架/404），
                # 用标记返回，调用方记为已处理、不再重试。
                # 注意与下面异常返回的 None 区分：None 表示 transient 失败，
                # 下次同步要重试，不能记为已处理。
                return {'book_id': str(book_id), '_not_found': True}
                
        except Exception as e:
            print(f"❌ 处理书籍ID {book_id} 时出错: {e}")
            return None


async def batch_process_books(book_ids: List[int]):
    """
    批量处理书籍

    Args:
        book_ids: 书籍ID列表

    Returns:
        三元组 (按标签分类的书籍字典, 成功处理的ID集合, 永久缺失的ID集合)。
        transient 失败（异常）的 ID 不在任何一个集合里，调用方不得记为已处理，
        否则下次同步不会重试，该书永久漏掉。
    """
    # 按标签分类的书籍
    books_by_tag = defaultdict(list)
    succeeded_ids = set()
    missing_ids = set()
    
    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    # 创建aiohttp会话
    async with aiohttp.ClientSession() as session:
        # 创建任务列表
        tasks = [fetch_book_async(session, book_id, semaphore) for book_id in book_ids]
        
        # 处理结果
        completed = 0
        total = len(tasks)
        
        for coro in asyncio.as_completed(tasks):
            book_data = await coro
            completed += 1
            
            if book_data and book_data.get('_not_found'):
                # 永久缺失：记下，不进书库，下次不再重试
                missing_ids.add(int(book_data['book_id']))
            elif book_data:
                succeeded_ids.add(int(book_data['book_id']))
                # 按标签分类
                tags = book_data.get('tags', [])
                if tags:
                    for tag in tags:
                        books_by_tag[tag].append(book_data)
                else:
                    # 如果没有标签，使用分类作为标签
                    category = book_data.get('category', '未分类')
                    if category:
                        books_by_tag[category].append(book_data)
                    else:
                        books_by_tag['未分类'].append(book_data)
                
                # 显示进度
                if completed % 10 == 0 or completed == total:
                    print(f"📊 进度: {completed}/{total} ({completed*100//total}%) - 已找到 {len(books_by_tag)} 个标签")
            else:
                if completed % 50 == 0 or completed == total:
                    print(f"📊 进度: {completed}/{total} ({completed*100//total}%)")
    
    return dict(books_by_tag), succeeded_ids, missing_ids


def save_processed_ids(book_ids: Set[int]):
    """保存已处理的ID列表"""
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_IDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted(book_ids), f, ensure_ascii=False, indent=2)


def load_processed_ids() -> Set[int]:
    """加载已处理的ID列表"""
    if PROCESSED_IDS_FILE.exists():
        with open(PROCESSED_IDS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_stats(stats: Dict):
    """保存统计信息"""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def save_max_book_id(max_id: int):
    """保存最大书籍ID"""
    with open(MAX_BOOK_ID_FILE, 'w', encoding='utf-8') as f:
        json.dump({'max_book_id': max_id, 'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')}, 
                 f, ensure_ascii=False, indent=2)


def load_max_book_id() -> int:
    """加载最大书籍ID"""
    if MAX_BOOK_ID_FILE.exists():
        with open(MAX_BOOK_ID_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('max_book_id', 0)
    return 0


def generate_hot_categories_index(books_by_tag: Dict[str, List[Dict]], output_dir: Path) -> Path:
    """
    生成热门分类索引文件（按照README.md格式）
    
    Args:
        books_by_tag: 按标签分类的书籍字典
        output_dir: 输出目录
    
    Returns:
        生成的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / "热门分类.md"
    
    # 按书籍数量排序
    sorted_tags = sorted(books_by_tag.items(), key=lambda x: len(x[1]), reverse=True)
    
    # 生成内容
    lines = []
    lines.append("# 📚 热门分类")
    lines.append("")
    lines.append("> **💡 使用 Ctrl+F 快速搜索关键词，或点击下方标签直接进入分类页面**")
    lines.append("")
    lines.append("## 🔥 热门分类")
    lines.append("")
    
    # 每行8个标签
    items_per_line = 8
    for i in range(0, len(sorted_tags), items_per_line):
        batch = sorted_tags[i:i + items_per_line]
        line_items = []
        
        for tag, books in batch:
            count = len(books)
            # 清理文件名（与generate_md_file中的逻辑一致）
            safe_filename = sanitize_filename(tag)
            link = f"- [{tag}({count})]({safe_filename}.md)"
            line_items.append(link)
        
        # 用 | 分隔，每行8个
        line = "  | ".join(line_items)
        lines.append(line)
    
    # 写入文件
    file_path.write_text('\n'.join(lines), encoding='utf-8')
    return file_path


async def main(start_id: int = 1, end_id: int = 1000):
    """
    主函数
    
    Args:
        start_id: 起始书籍ID（默认：1）
        end_id: 结束书籍ID（默认：1000）
    """
    print("=" * 80)
    print(f"🚀 开始批量处理书籍（ID: {start_id}-{end_id}）")
    print("=" * 80)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 输出目录: {OUTPUT_DIR}")
    
    # 生成书籍ID列表
    book_ids = list(range(start_id, end_id + 1))
    print(f"📚 待处理书籍数量: {len(book_ids)}")
    
    # 加载已处理的ID（用于断点续传）
    processed_ids = load_processed_ids()
    if processed_ids:
        print(f"📋 已处理ID数量: {len(processed_ids)}")
        book_ids = [bid for bid in book_ids if bid not in processed_ids]
        print(f"📚 剩余待处理: {len(book_ids)}")
    
    if not book_ids:
        print("✅ 所有书籍已处理完成！")
        return
    
    # 开始处理
    start_time = time.time()
    books_by_tag, succeeded_ids, missing_ids = await batch_process_books(book_ids)
    elapsed_time = time.time() - start_time
    
    # 统计信息
    total_books = sum(len(books) for books in books_by_tag.values())
    total_tags = len(books_by_tag)
    
    print(f"\n📊 处理完成！")
    print(f"  - 总耗时: {elapsed_time:.2f} 秒")
    print(f"  - 成功处理: {total_books} 本书")
    print(f"  - 标签数量: {total_tags} 个")
    
    # 生成md文件
    print(f"\n📝 开始生成Markdown文件...")
    generated_files = []
    
    for tag, books in sorted(books_by_tag.items()):
        file_path = generate_md_file(tag, books, OUTPUT_DIR)
        if file_path:
            generated_files.append(str(file_path))
            # 如果文件数量很多，减少输出频率
            if len(generated_files) <= 50 or len(generated_files) % 50 == 0:
                print(f"  ✅ {tag}: {len(books)} 本书 -> {file_path.name}")
    
    print(f"\n✅ 共生成 {len(generated_files)} 个Markdown文件")
    
    # 保存统计信息
    stats = {
        'total_processed': total_books,
        'total_tags': total_tags,
        'generated_files': len(generated_files),
        'elapsed_time': elapsed_time,
        'tags': {tag: len(books) for tag, books in sorted(books_by_tag.items())}
    }
    save_stats(stats)
    
    # 保存已处理的ID：只记成功和永久缺失的，transient 失败的不记，
    # 下次运行会重试。旧代码把全部尝试过的 ID 都记上，失败的书永久漏掉。
    all_processed = processed_ids | succeeded_ids | missing_ids
    save_processed_ids(all_processed)
    
    # 保存最大书籍ID：只推进到连续已处理（成功或永久缺失）的边界。
    # 旧代码直接取 max(book_ids)，会跳过中间失败的 ID，增量同步再也不会回来补。
    contiguous_max = load_max_book_id()
    done_ids = succeeded_ids | missing_ids
    while contiguous_max + 1 in done_ids:
        contiguous_max += 1
    save_max_book_id(contiguous_max)
    print(f"\n📊 最大书籍ID: {contiguous_max}（已保存，用于增量更新）")
    
    # 生成热门分类索引文件
    print(f"\n📝 生成热门分类索引文件...")
    hot_categories_file = generate_hot_categories_index(books_by_tag, OUTPUT_DIR)
    print(f"  ✅ 热门分类索引: {hot_categories_file.name}")
    
    print(f"\n📈 统计信息已保存: {STATS_FILE}")
    print("=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='批量处理书籍并生成md文件')
    parser.add_argument('--start-id', type=int, default=1, help='起始书籍ID（默认：1）')
    parser.add_argument('--end-id', type=int, default=1000, help='结束书籍ID（默认：1000）')
    args = parser.parse_args()
    
    asyncio.run(main(args.start_id, args.end_id))
