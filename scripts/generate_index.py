import json
import re
from collections import defaultdict
from pathlib import Path

# 路径定义
ROOT = Path(__file__).parent.parent
ALL_BOOKS_FILE = ROOT / "docs" / "all-books.json"
STATS_FILE = ROOT / "docs" / "parse-stats.json"
OUTPUT_HTML = ROOT / "docs" / "index.html"
OUTPUT_JSON = ROOT / "docs" / "books.json"


def load_books():
    """从 all-books.json 加载真实数据"""
    if ALL_BOOKS_FILE.exists():
        try:
            with open(ALL_BOOKS_FILE, "r", encoding="utf-8") as f:
                books = json.load(f)
                print(f"✅ 从 all-books.json 加载了 {len(books)} 本书籍")
                return books
        except Exception as e:
            print(f"❌ 加载 all-books.json 失败: {e}")
            print(f"💡 提示：请先运行 'python scripts/parse_md_to_json.py' 生成 all-books.json")
            return []
    
    print("⚠️  未找到 all-books.json 文件")
    print(f"💡 提示：请先运行 'python scripts/parse_md_to_json.py' 生成 all-books.json")
    return []


def load_stats():
    """加载统计信息"""
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  加载统计信息失败: {e}")
    return None


def group_books(books):
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    categories, languages, levels = set(), set(), set()

    for b in books:
        c = b["category"]
        l = b["language"]
        lv = b["level"]

        categories.add(c)
        languages.add(l)
        levels.add(lv)

        grouped[c][l][lv].append(b)

    return grouped, categories, languages, levels


def render_overview(total_books, total_categories, languages, levels):
    # 格式化数字
    books_display = f"{total_books:,}" if total_books > 1000 else str(total_books)
    cats_display = f"{total_categories:,}" if total_categories > 1000 else str(total_categories)
    
    # 语言显示
    lang_display = " / ".join(sorted(languages)) if languages else "中文 / 英文"
    
    return f"""## 📊 统计概览

<div class="overview-stats">
<div class="stat-item">
<span>📘 总书籍数</span>
<strong id="total-books">{books_display}</strong>
</div>
<div class="stat-item">
<span>📂 分类数量</span>
<strong id="total-categories">{cats_display}</strong>
</div>
<div class="stat-item">
<span>🌍 支持语言</span>
<strong>{lang_display}</strong>
</div>
<div class="stat-item">
<span>📥 支持格式</span>
<strong>EPUB / MOBI / AZW3</strong>
</div>
</div>
"""


def render_search_ui():
    # 直接写 HTML（GitHub Pages 支持）
    return """## 🔍 搜索书籍

<div class="search-container">
  <input
    type="text"
    id="search-input"
    placeholder="搜索 书名 / 作者 / 分类（支持多关键词，用空格分隔）"
    oninput="onSearch(event)"
    aria-label="搜索书籍"
    autocomplete="off"
  />
  <div class="search-hint">
    <span>💡</span>
    <span>支持搜索书名、作者、分类，可输入多个关键词（用空格分隔）</span>
  </div>
</div>

<div id="search-results" role="region" aria-live="polite" aria-label="搜索结果">
  <div class="loading-indicator">正在加载书籍数据...</div>
</div>

<script src="search.js"></script>
"""


def render_content(grouped, stats=None):
    lines = []
    
    # 计算每个分类的书籍数量
    category_counts = {}
    for category, languages in grouped.items():
        count = sum(len(books) for lang_dict in languages.values() for books in lang_dict.values())
        category_counts[category] = count
    
    # 按书籍数量排序，优先显示热门分类
    sorted_categories = sorted(category_counts.keys(), key=lambda x: category_counts[x], reverse=True)
    
    # 优先显示用户指定的热门分类
    priority_categories = ["文学", "沟通", "励志", "经典", "历史", "科普", "管理", "社会", "推理", "经济", "哲学", "传记"]
    
    # 重新排序：优先分类在前，然后按数量排序
    priority_set = set(priority_categories)
    priority_list = [cat for cat in priority_categories if cat in sorted_categories]
    other_list = [cat for cat in sorted_categories if cat not in priority_set]
    sorted_categories = priority_list + other_list
    
    # 限制显示的分类数量（避免页面过长）
    max_categories = 20
    if len(sorted_categories) > max_categories:
        lines.append(f"<p class=\"note-text\">💡 注：共 {len(category_counts)} 个分类，以下显示前 {max_categories} 个热门分类的书籍。使用搜索功能可查找所有书籍。</p>\n\n")
        sorted_categories = sorted_categories[:max_categories]

    for category in sorted_categories:
        lines.append(f"<div class=\"category-section\">\n")
        lines.append(f"## 📂 {category}\n")

        for language in sorted(grouped[category].keys()):
            lines.append(f"### 🌍 Language: {language}\n")

            for level in sorted(grouped[category][language].keys()):
                lines.append(f"#### ⭐ Level: {level}\n")

                books_list = grouped[category][language][level]
                # 每个分类-语言-级别组合最多显示10本书
                max_books_per_section = 10
                if len(books_list) > max_books_per_section:
                    books_list = books_list[:max_books_per_section]
                    lines.append(f"<p class=\"note-text\">*（共 {len(grouped[category][language][level])} 本，显示前 {max_books_per_section} 本）*</p>\n")

                for b in books_list:
                    formats = ", ".join(b.get("formats", []))
                    author = b.get('author', '未知')
                    lines.append(
                        f"<div class=\"book-item\">\n"
                        f"<strong>{b['title']}</strong>\n"
                        f"<div class=\"book-meta\">👤 {author} ｜ 📥 {formats}</div>\n"
                        f"<a href=\"{b['link']}\" target=\"_blank\" rel=\"noopener\" class=\"book-link\">📥 下载</a>\n"
                        f"</div>\n"
                    )

                lines.append("")
        
        lines.append("</div>\n\n")

    if len(sorted_categories) < len(grouped.keys()):
        lines.append(f"\n<hr>\n\n<p class=\"note-text\">💡 还有 {len(grouped.keys()) - len(sorted_categories)} 个分类未显示，请使用搜索功能查找。</p>\n")

    return "\n".join(lines)


def markdown_to_html(md_content):
    """简单的 Markdown 转 HTML 转换"""
    lines = md_content.split('\n')
    result_lines = []
    in_list = False
    in_paragraph = False
    paragraph_lines = []
    in_html_block = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测 HTML 块开始/结束
        if '<div' in stripped or '<script' in stripped:
            in_html_block = True
        if '</div>' in stripped or '</script>' in stripped:
            in_html_block = False
        
        # HTML 块内的内容直接保留
        if in_html_block or ('<' in stripped and '>' in stripped and not stripped.startswith('#')):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(line)
            i += 1
            continue
        
        # 空行
        if not stripped:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append('')
            i += 1
            continue
        
        # 标题
        if stripped.startswith('#### '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(f'<h4>{stripped[5:]}</h4>')
        elif stripped.startswith('### '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(f'<h3>{stripped[4:]}</h3>')
        elif stripped.startswith('## '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(f'<h2>{stripped[3:]}</h2>')
        elif stripped.startswith('# '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(f'<h1>{stripped[2:]}</h1>')
        # 水平线
        elif stripped == '---':
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append('<hr>')
        # 引用
        elif stripped.startswith('> '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            result_lines.append(f'<blockquote>{stripped[2:]}</blockquote>')
        # 列表项
        elif stripped.startswith('- '):
            if in_paragraph:
                result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
                paragraph_lines = []
                in_paragraph = False
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            content = stripped[2:]
            # 处理内联格式
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', content)
            result_lines.append(f'<li>{content}</li>')
        # 普通段落
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            # 处理内联格式
            processed_line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            processed_line = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', processed_line)
            paragraph_lines.append(processed_line)
            in_paragraph = True
        
        i += 1
    
    # 处理结尾
    if in_list:
        result_lines.append('</ul>')
    if in_paragraph:
        result_lines.append('<p>' + ' '.join(paragraph_lines) + '</p>')
    
    return '\n'.join(result_lines)


def generate_html(md_content):
    """生成完整的 HTML 页面"""
    html_body = markdown_to_html(md_content)
    
    # 尝试加载统计信息并生成更新脚本
    stats_info = ""
    try:
        stats_file = ROOT / "docs" / "parse-stats.json"
        if stats_file.exists():
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                stats_info = f"""
<script>
// 更新统计信息（从 parse-stats.json）
(function() {{
    const stats = {json.dumps(stats, ensure_ascii=False)};
    const totalBooksEl = document.getElementById('total-books');
    const totalCatsEl = document.getElementById('total-categories');
    if (totalBooksEl && stats.total_books) {{
        totalBooksEl.textContent = stats.total_books.toLocaleString() + ' 本';
    }}
    if (totalCatsEl && stats.categories_count) {{
        totalCatsEl.textContent = stats.categories_count.toLocaleString() + ' 个';
    }}
}})();
</script>"""
    except Exception as e:
        print(f"⚠️  生成统计信息脚本失败: {e}")
    
    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="电子书下载宝库 - 汇聚24,000+本电子书，涵盖文学、历史、科普、管理、技术等各个领域。支持epub、mobi、azw3格式，完全免费。">
    <meta name="keywords" content="电子书下载,免费电子书,epub下载,mobi下载,azw3下载,电子书资源,文学电子书,历史电子书">
    <meta name="author" content="ebook-treasure-chest">
    <meta name="robots" content="index, follow">
    
    <!-- Open Graph -->
    <meta property="og:title" content="📚 电子书下载宝库 - Ebook Treasure Chest">
    <meta property="og:description" content="汇聚24,000+本电子书，涵盖文学、历史、科普、管理、技术等各个领域">
    <meta property="og:type" content="website">
    
    <!-- Preload critical resources -->
    <link rel="preload" href="all-books.json" as="fetch" crossorigin>
    <link rel="preload" href="search.js" as="script">
    
    <title>📚 电子书下载宝库 - Ebook Treasure Chest</title>
    <style>
        /* Solarized Dark Color Palette */
        :root {{
            --base03: #002b36;  /* darkest background */
            --base02: #073642;  /* dark background */
            --base01: #586e75;  /* dark content */
            --base00: #657b83;  /* content */
            --base0: #839496;   /* main content */
            --base1: #93a1a1;   /* comments */
            --base2: #eee8d5;   /* light background */
            --base3: #fdf6e3;   /* lightest background */
            --yellow: #b58900;
            --orange: #cb4b16;
            --red: #dc322f;
            --magenta: #d33682;
            --violet: #6c71c4;
            --blue: #268bd2;
            --cyan: #2aa198;
            --green: #859900;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: "SF Mono", "Monaco", "Inconsolata", "Fira Code", "Roboto Mono", "Source Code Pro", "Consolas", "Courier New", monospace, "Microsoft YaHei", sans-serif;
            line-height: 1.7;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: var(--base0);
            background: var(--base03);
            min-height: 100vh;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 15px;
            }}
        }}
        
        header {{
            background: var(--base02);
            padding: 30px;
            border-radius: 8px;
            border: 1px solid var(--base01);
            margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }}
        
        h1 {{
            font-size: 2.5em;
            margin: 0 0 16px 0;
            color: var(--cyan);
            font-weight: 700;
            text-align: center;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            letter-spacing: -0.5px;
        }}
        
        h2 {{
            font-size: 1.75em;
            margin: 32px 0 20px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--blue);
            color: var(--base1);
            font-weight: 600;
            position: relative;
            font-family: "SF Mono", "Monaco", monospace;
        }}
        
        h2::before {{
            content: "";
            position: absolute;
            left: 0;
            bottom: -2px;
            width: 60px;
            height: 2px;
            background: var(--cyan);
            border-radius: 1px;
        }}
        
        h3 {{
            font-size: 1.3em;
            margin: 24px 0 12px 0;
            color: var(--base0);
            font-weight: 500;
            font-family: "SF Mono", "Monaco", monospace;
        }}
        
        h4 {{
            font-size: 1.1em;
            margin: 16px 0 8px 0;
            color: var(--base00);
            font-weight: 500;
            font-family: "SF Mono", "Monaco", monospace;
        }}
        
        a {{
            color: var(--blue);
            text-decoration: none;
            transition: all 0.2s ease;
            font-weight: 500;
        }}
        
        a:hover {{
            color: var(--cyan);
            text-decoration: underline;
        }}
        
        a:focus {{
            outline: 2px solid var(--blue);
            outline-offset: 2px;
            border-radius: 2px;
        }}
        
        blockquote {{
            padding: 16px 20px;
            color: var(--base1);
            border-left: 4px solid var(--yellow);
            margin: 20px 0;
            background: var(--base02);
            border-radius: 6px;
            font-style: italic;
            box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.2);
        }}
        
        hr {{
            height: 1px;
            margin: 40px 0;
            background: linear-gradient(90deg, transparent, var(--base01), transparent);
            border: 0;
        }}
        
        .search-container {{
            margin: 30px 0;
            position: relative;
            background: var(--base02);
            padding: 24px;
            border-radius: 8px;
            border: 1px solid var(--base01);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }}
        
        input[type="text"] {{
            width: 100%;
            padding: 14px 18px;
            font-size: 16px;
            border: 2px solid var(--base01);
            border-radius: 6px;
            box-sizing: border-box;
            transition: all 0.3s ease;
            background-color: var(--base03);
            color: var(--base0);
            font-family: "SF Mono", "Monaco", monospace;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }}
        
        input[type="text"]:hover {{
            border-color: var(--base00);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
        }}
        
        input[type="text"]:focus {{
            outline: none;
            border-color: var(--blue);
            box-shadow: 0 0 0 3px rgba(38, 139, 210, 0.2), inset 0 2px 4px rgba(0, 0, 0, 0.2);
            background-color: var(--base02);
        }}
        
        input[type="text"]::placeholder {{
            color: var(--base01);
        }}
        
        .search-hint {{
            margin-top: 12px;
            color: var(--base1);
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--base03);
            border-radius: 6px;
            border: 1px solid var(--base01);
        }}
        
        #search-results {{
            margin-top: 24px;
            min-height: 50px;
        }}
        
        .loading-indicator {{
            text-align: center;
            padding: 40px 20px;
            color: var(--base1);
            font-size: 16px;
            background: var(--base02);
            border-radius: 8px;
            border: 1px solid var(--base01);
        }}
        
        .loading-indicator::before {{
            content: "⏳ ";
            animation: pulse 1.5s ease-in-out infinite;
            color: var(--yellow);
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        ul {{
            padding-left: 0;
            margin: 16px 0;
            list-style: none;
        }}
        
        li {{
            margin: 12px 0;
            padding: 12px 16px;
            background: var(--base02);
            border-left: 3px solid var(--blue);
            border-radius: 6px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            border: 1px solid var(--base01);
        }}
        
        li:hover {{
            transform: translateX(4px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            border-left-width: 4px;
            border-left-color: var(--cyan);
            background: var(--base03);
        }}
        
        li strong {{
            color: var(--base1);
            font-size: 1.05em;
            font-weight: 600;
        }}
        
        p {{
            margin: 16px 0;
            line-height: 1.7;
            color: var(--base0);
        }}
        
        .overview-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-item {{
            padding: 20px 18px;
            background: var(--base02);
            border-radius: 8px;
            border: 1px solid var(--base01);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            text-align: center;
        }}
        
        .stat-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
            border-color: var(--cyan);
            background: var(--base03);
        }}
        
        .stat-item span {{
            display: block;
            font-size: 13px;
            color: var(--base1);
            margin-bottom: 10px;
            font-weight: 500;
            font-family: "SF Mono", "Monaco", monospace;
            opacity: 0.9;
        }}
        
        .stat-item strong {{
            display: block;
            font-size: 1.4em;
            color: var(--cyan);
            font-weight: 600;
            margin-top: 6px;
            font-family: "SF Mono", "Monaco", monospace;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
            line-height: 1.3;
        }}
        
        @media (max-width: 600px) {{
            .overview-stats {{
                grid-template-columns: 1fr;
                gap: 16px;
            }}
            
            h1 {{
                font-size: 2em;
            }}
            
            h2 {{
                font-size: 1.5em;
            }}
        }}
        
        .category-section {{
            background: var(--base02);
            padding: 24px;
            margin: 24px 0;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border: 1px solid var(--base01);
            transition: all 0.3s ease;
        }}
        
        .category-section:hover {{
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
            border-color: var(--cyan);
        }}
        
        .book-item {{
            padding: 16px;
            margin: 12px 0;
            background: var(--base03);
            border-radius: 6px;
            border-left: 4px solid var(--blue);
            border: 1px solid var(--base01);
            border-left-width: 4px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }}
        
        .book-item:hover {{
            background: var(--base02);
            transform: translateX(4px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            border-left-color: var(--cyan);
        }}
        
        .book-item strong {{
            color: var(--base1);
            font-size: 1.05em;
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
        }}
        
        .book-item .book-meta {{
            color: var(--base00);
            font-size: 0.9em;
            margin: 8px 0;
            font-family: "SF Mono", "Monaco", monospace;
        }}
        
        .book-item .book-link {{
            display: inline-block;
            margin-top: 8px;
            padding: 6px 14px;
            background: var(--blue);
            color: var(--base03) !important;
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.2s ease;
            text-decoration: none !important;
            font-family: "SF Mono", "Monaco", monospace;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }}
        
        .book-item .book-link:hover {{
            background: var(--cyan);
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(42, 161, 152, 0.4);
            color: var(--base03) !important;
        }}
        
        .note-text {{
            padding: 12px 16px;
            background: var(--base02);
            border-left: 4px solid var(--yellow);
            border-radius: 6px;
            color: var(--yellow);
            font-size: 14px;
            margin: 20px 0;
            border: 1px solid var(--base01);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            font-family: "SF Mono", "Monaco", monospace;
        }}
        
        .footer-note {{
            margin-top: 60px;
            padding: 24px;
            background: var(--base02);
            border-radius: 8px;
            text-align: center;
            color: var(--base1);
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border-top: 3px solid var(--cyan);
            border: 1px solid var(--base01);
            border-top-width: 3px;
        }}
        
        .footer-note a {{
            margin: 0 8px;
            padding: 4px 8px;
            border-radius: 4px;
            color: var(--blue);
        }}
        
        .footer-note a:hover {{
            background: var(--base03);
            text-decoration: none;
            color: var(--cyan);
        }}
        
        /* 滚动条样式 - Solarized Dark */
        ::-webkit-scrollbar {{
            width: 12px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--base03);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: var(--base01);
            border-radius: 6px;
            border: 2px solid var(--base03);
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--base00);
        }}
        
        /* 代码风格字体优化 */
        code {{
            background: var(--base02);
            color: var(--green);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "SF Mono", "Monaco", monospace;
            font-size: 0.9em;
            border: 1px solid var(--base01);
        }}
        
        /* 强调文本 */
        strong {{
            color: var(--base1);
            font-weight: 600;
        }}
        
        /* 链接特殊样式 */
        a[href^="http"] {{
            color: var(--blue);
        }}
        
        a[href^="http"]:hover {{
            color: var(--cyan);
        }}
    </style>
</head>
<body>
<header>
{content}
</header>

<footer class="footer-note">
    <p>📚 电子书下载宝库 </p>
    <p style="margin-top: 8px; font-size: 12px;">
        <a href="https://github.com/ciweihaha/ebook-treasure-chest" target="_blank" rel="noopener">GitHub 仓库</a> |
        <a href="README.md" target="_blank">使用说明</a>
    </p>
</footer>
{stats_script}
</body>
</html>"""
    
    return html_template.format(content=html_body, stats_script=stats_info)


def main():
    books = load_books()
    stats = load_stats()
    
    # 如果有统计信息，使用统计信息中的数据
    if stats:
        total_books = stats.get("total_books", len(books))
        total_categories = stats.get("categories_count", len(set(b.get("category", "") for b in books)))
    else:
        total_books = len(books)
        total_categories = len(set(b.get("category", "") for b in books))
    
    grouped, categories, languages, levels = group_books(books)
    
    # 使用统计信息中的分类数量（如果可用）
    if stats and "categories_count" in stats:
        categories_count = stats["categories_count"]
    else:
        categories_count = len(categories)

    md_parts = []
    md_parts.append("# 📚 Ebook Treasure Chest\n")
    md_parts.append(render_overview(total_books, categories_count, languages, levels))
    md_parts.append("\n---\n")
    md_parts.append(render_search_ui())
    md_parts.append("\n---\n")
    md_parts.append(render_content(grouped, stats))

    md_content = "\n".join(md_parts)
    
    OUTPUT_HTML.parent.mkdir(exist_ok=True)

    # 写 index.html（GitHub Pages 优先查找）
    html_content = generate_html(md_content)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")

    # 写 books.json（给前端搜索用，作为 metadata 数据的备份）
    OUTPUT_JSON.write_text(
        json.dumps(books, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("✅ index.html & books.json generated")
    
    # 检查 all-books.json
    if ALL_BOOKS_FILE.exists():
        print(f"ℹ️  检测到 all-books.json ({ALL_BOOKS_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
    else:
        print("⚠️  警告：未找到 all-books.json")
        print("💡 提示：运行 'python scripts/parse_md_to_json.py' 生成 all-books.json")


if __name__ == "__main__":
    main()
