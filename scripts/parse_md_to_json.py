#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 md 目录下的所有 Markdown 文件，生成统一的 JSON 数据文件
"""

import html
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
MD_DIR = ROOT / "md"
OUTPUT_JSON = ROOT / "docs" / "all-books.json"
STATS_FILE = ROOT / "docs" / "parse-stats.json"


def extract_category_from_file(file_path):
    """从文件路径提取分类名"""
    # 从文件名提取（去掉 .md 扩展名）
    category = file_path.stem
    return category


def extract_category_from_content(content):
    """从文件内容提取分类名（备用方法）"""
    # 查找 # 分类名 格式
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        # 跳过版权声明，找第二个 # 标题
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# ') and '版权' not in line and '声明' not in line:
                return line[2:].strip()
    return None


def parse_markdown_table(content):
    """解析 Markdown 表格，提取书籍信息"""
    books = []
    lines = content.split('\n')
    
    # 找到表格开始位置（包含 "书名" 的行）
    table_start = -1
    for i, line in enumerate(lines):
        if '| 书名' in line or '书名 |' in line:
            table_start = i
            break
    
    if table_start == -1:
        return books
    
    # 跳过表头分隔行（---）
    data_start = table_start + 2
    
    # 解析数据行
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if not line or not line.startswith('|'):
            continue
        
        # 解析表格行：| 书名 | 作者 | [下载](链接) |
        # 使用正则表达式提取
        pattern = r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*\[下载\]\((.+?)\)\s*\|'
        match = re.match(pattern, line)
        
        if match:
            title = match.group(1).strip()
            author = match.group(2).strip()
            link = match.group(3).strip()

            # 清理数据
            title = title.replace('**', '').strip()
            author = author.replace('**', '').strip()
            # 上游 md 里混有 HTML 数字实体（如 &#8211;、&#038;、&#8217;），
            # 不解码会原样进 JSON：搜索页 escapeHtml 后显示成字面 "&#8211;"，
            # 且搜真实字符（–、&、'）匹配不到。链接不含实体，不动。
            title = html.unescape(title)
            author = html.unescape(author)
            
            if title and link:  # 确保有书名和链接
                books.append({
                    'title': title,
                    'author': author if author else '未知',
                    'link': link
                })
    
    return books


def parse_single_file(file_path):
    """解析单个 Markdown 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  读取文件失败 {file_path}: {e}")
        return None, []
    
    # 提取分类名
    category = extract_category_from_file(file_path)
    category_from_content = extract_category_from_content(content)
    
    # 优先使用文件内容中的分类名（更准确）
    if category_from_content and category_from_content != category:
        category = html.unescape(category_from_content)
    
    # 解析表格
    books = parse_markdown_table(content)
    
    # 为每本书添加分类信息
    for book in books:
        book['category'] = category
        # 默认值
        book['language'] = 'ZH'  # 默认中文，后续可优化
        book['level'] = 'Unknown'
        book['formats'] = ['epub', 'mobi', 'azw3']  # 从表格列名推断
    
    return category, books


def main():
    """主函数"""
    print("🚀 开始解析 md 文件...")
    
    all_books = []
    category_stats = defaultdict(int)
    total_files = 0
    success_files = 0
    error_files = []
    
    # 获取所有 md 文件
    md_files = list(MD_DIR.glob("*.md"))
    total_files = len(md_files)
    
    print(f"📁 找到 {total_files} 个 md 文件")
    
    # 解析每个文件
    for i, md_file in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"⏳ 处理进度: {i}/{total_files} ({i*100//total_files}%)")
        
        category, books = parse_single_file(md_file)
        
        if category is None:
            error_files.append(str(md_file))
            continue
        
        if books:
            all_books.extend(books)
            category_stats[category] = len(books)
            success_files += 1
        else:
            error_files.append(str(md_file))
            print(f"⚠️  未找到数据: {md_file.name}")
    
    # 保存结果
    OUTPUT_JSON.parent.mkdir(exist_ok=True)
    
    print(f"\n📊 解析统计:")
    print(f"  - 总文件数: {total_files}")
    print(f"  - 成功解析: {success_files}")
    print(f"  - 失败文件: {len(error_files)}")
    print(f"  - 总书籍数: {len(all_books)}")
    print(f"  - 分类数量: {len(category_stats)}")
    
    # 保存 JSON 文件
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_books, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ JSON 文件已生成: {OUTPUT_JSON}")
    print(f"📦 文件大小: {OUTPUT_JSON.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 保存统计信息
    stats = {
        'total_files': total_files,
        'success_files': success_files,
        'error_files': len(error_files),
        'total_books': len(all_books),
        'categories_count': len(category_stats),
        'top_categories': dict(sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:20]),
        'error_file_list': error_files[:10]  # 只保存前10个错误文件
    }
    
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"📈 统计信息已保存: {STATS_FILE}")
    
    # 显示前10个分类
    print(f"\n🏆 前10个分类（按书籍数量）:")
    for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {cat}: {count} 本")


if __name__ == "__main__":
    main()
