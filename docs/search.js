let books = [];
let searchTimeout = null;
const MAX_RESULTS = 100; // 最多显示100条结果

function retryPendingSearch() {
  // 数据加载完成后补跑一次搜索：加载期间用户已输入关键词时，
  // onSearch 只会显示"正在加载书籍数据"，加载完没人再触发搜索，
  // 用户必须删掉重输才出结果。加载完这里补一次即可。
  const searchBox = document.querySelector('input[type="text"]');
  if (searchBox && String(searchBox.value || '').trim()) {
    onSearch({ target: searchBox });
  }
}

async function loadBooks() {
  console.log("🔄 开始加载书籍数据...");
  
  try {
    // 优先加载 all-books.json（包含所有 md 文件的数据）
    console.log("📥 尝试加载 all-books.json...");
    const res = await fetch("all-books.json");
    
    if (res.ok) {
      const data = await res.json();
      // 数据必须是数组：万一 JSON 被写坏成对象，旧代码会直接 books = data，
      // 之后每次搜索都在 books.filter 上抛 TypeError，页面静默不可用。
      // 这里抛错走降级分支，尝试 books.json。
      if (!Array.isArray(data)) {
        throw new Error("all-books.json 不是数组");
      }
      books = data;
      console.log(`✅ 已加载 ${books.length} 本书籍（来自 all-books.json）`);
      
      // 显示加载成功的提示
      const searchBox = document.querySelector('input[type="text"]');
      if (searchBox) {
        const originalPlaceholder = searchBox.placeholder;
        searchBox.placeholder = `已加载 ${books.length.toLocaleString()} 本书，开始搜索...`;
        setTimeout(() => {
          searchBox.placeholder = originalPlaceholder;
        }, 3000);
      }
      retryPendingSearch();
      return;
    } else {
      console.warn(`⚠️  all-books.json 返回状态码: ${res.status}`);
    }
  } catch (e) {
    console.warn("⚠️  all-books.json 加载失败:", e);
  }
  
  // 降级到 books.json（metadata 数据）
  try {
    console.log("📥 尝试加载 books.json...");
    const res = await fetch("books.json");
    if (res.ok) {
      const data = await res.json();
      if (!Array.isArray(data)) {
        throw new Error("books.json 不是数组");
      }
      books = data;
      console.log(`✅ 已加载 ${books.length} 本书籍（来自 books.json，metadata 数据）`);
      console.warn("💡 提示：建议运行 'python scripts/parse_md_to_json.py' 生成完整的 all-books.json");
      retryPendingSearch();
    } else {
      console.error(`❌ books.json 返回状态码: ${res.status}`);
    }
  } catch (e) {
    console.error("❌ 无法加载书籍数据", e);
    alert("⚠️ 无法加载书籍数据，请检查网络连接或刷新页面重试");
  }
}

function searchBooks(keyword) {
  if (!Array.isArray(books) || !keyword || keyword.trim() === "") {
    return [];
  }
  
  const k = keyword.toLowerCase().trim();
  const keywords = k.split(/\s+/); // 支持多关键词搜索

  return books.filter(b => {
    const title = (b.title || "").toLowerCase();
    const author = (b.author || "").toLowerCase();
    const category = (b.category || "").toLowerCase();
    
    // 多关键词匹配：所有关键词都要匹配
    return keywords.every(keyword => 
      title.includes(keyword) ||
      author.includes(keyword) ||
      category.includes(keyword)
    );
  }).slice(0, MAX_RESULTS); // 限制结果数量
}

// HTML 转义函数
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 正则表达式特殊字符转义
function escapeRegex(str) {
  if (!str) return '';
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlightText(text, keyword) {
  if (!keyword || !text) return escapeHtml(text);

  // 按空格拆成多个关键词逐个高亮：旧代码拿整串短语建正则，
  // 关键词分处标题/作者两处、或在同一字段不相邻时（如搜"三体 刘慈欣"，
  // 标题只有"三体"）整串匹配不到，高亮全丢。按长度降序排，
  // 长词优先，避免短词先吞掉长词的一部分。
  const parts = keyword.split(/\s+/).filter(Boolean).map(escapeRegex);
  if (parts.length === 0) return escapeHtml(text);
  parts.sort((a, b) => b.length - a.length);
  const regex = new RegExp(`(${parts.join('|')})`, 'gi');

  // 先转义 HTML，再添加高亮标记
  const escapedText = escapeHtml(text);
  return escapedText.replace(regex, '<mark>$1</mark>');
}

// 下载链接校验：只接受绝对 http(s) 链接。
// 数据里有 69 本书的 link 是 "链接未找到" 这类占位文本；旧代码用
// new URL(link, origin) 解析会把它拼成站内相对地址
// （https://ciweihaha.github.io/ebook-treasure-chest/%E9%93%BE...），
// 点"下载"就落到本站 404。无效链接返回 null，调用方渲染禁用态。
function getSafeDownloadLink(link) {
  if (!link || typeof link !== 'string') return null;
  if (!/^https?:\/\//i.test(link.trim())) return null;
  try {
    const url = new URL(link.trim());
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      return url.href;
    }
  } catch (e) {
    // 解析失败：无效链接
  }
  return null;
}

function renderResults(results, keyword) {
  const box = document.getElementById("search-results");
  box.innerHTML = "";

  if (results.length === 0) {
    box.innerHTML = "<p style='padding: 20px; text-align: center; color: #93a1a1; background: #073642; border-radius: 6px; border: 1px solid #586e75;'>❌ 没有找到相关书籍</p>";
    return;
  }

  const keywordLower = keyword.toLowerCase();
  
  // 显示结果数量
  const countDiv = document.createElement("div");
  countDiv.style.cssText = "padding: 12px 16px; background: #073642; border-radius: 6px; margin-bottom: 16px; border: 1px solid #586e75; color: #2aa198; font-family: 'SF Mono', 'Monaco', monospace;";
  countDiv.innerHTML = `<strong>找到 ${results.length}${results.length === MAX_RESULTS ? '+' : ''} 条结果</strong>`;
  box.appendChild(countDiv);

  results.forEach(b => {
    const div = document.createElement("div");
    div.style.cssText = "padding: 16px; margin: 12px 0; background: #073642; border: 1px solid #586e75; border-left: 4px solid #268bd2; border-radius: 6px; transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);";
    
    // 添加 hover 效果
    div.addEventListener('mouseenter', function() {
      this.style.borderLeftColor = '#2aa198';
      this.style.background = '#002b36';
      this.style.transform = 'translateX(4px)';
      this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.3)';
    });
    div.addEventListener('mouseleave', function() {
      this.style.borderLeftColor = '#268bd2';
      this.style.background = '#073642';
      this.style.transform = 'translateX(0)';
      this.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
    });
    
    const highlightedTitle = highlightText(b.title || "未知", keywordLower);
    const highlightedAuthor = highlightText(b.author || "未知", keywordLower);
    const highlightedCategory = highlightText(b.category || "", keywordLower);
    
    // 校验下载链接：无效链接（如数据里的"链接未找到"）不生成可点链接，
    // 改为禁用态文字，避免点"下载"落到本站 404
    const safeLink = getSafeDownloadLink(b.link);
    const downloadHtml = safeLink
      ? `<a href="${safeLink}" target="_blank" rel="noopener" style="
          display: inline-block;
          padding: 6px 14px;
          background: #268bd2;
          color: #002b36;
          text-decoration: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 600;
          font-family: 'SF Mono', 'Monaco', monospace;
          transition: all 0.2s ease;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        " onmouseover="this.style.background='#2aa198'; this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(42, 161, 152, 0.4)';"
           onmouseout="this.style.background='#268bd2'; this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0, 0, 0, 0.2)';"
        >📥 下载</a>`
      : `<span style="
          display: inline-block;
          padding: 6px 14px;
          background: #073642;
          color: #586e75;
          border: 1px solid #586e75;
          border-radius: 6px;
          font-size: 14px;
          font-family: 'SF Mono', 'Monaco', monospace;
          cursor: not-allowed;
        ">暂无下载链接</span>`;
    div.innerHTML = `
      <div style="margin-bottom: 10px;">
        <strong style="font-size: 16px; color: #93a1a1; font-weight: 600;">${highlightedTitle}</strong>
      </div>
      <div style="color: #657b83; font-size: 14px; margin-bottom: 10px; font-family: 'SF Mono', 'Monaco', monospace;">
        <span>👤 ${highlightedAuthor}</span>
        <span style="margin: 0 10px; color: #586e75;">|</span>
        <span>📂 ${highlightedCategory}</span>
      </div>
      <div>
        ${downloadHtml}
      </div>
    `;
    box.appendChild(div);
  });
  
  // 添加样式
  if (!document.getElementById('search-results-style')) {
    const style = document.createElement('style');
    style.id = 'search-results-style';
    style.textContent = `
      #search-results mark {
        background: #b58900;
        color: #002b36;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: 600;
      }
    `;
    document.head.appendChild(style);
  }
}

function onSearch(e) {
  const keyword = e.target.value.trim();
  
  // 检查数据是否已加载
  if (books.length === 0) {
    const box = document.getElementById("search-results");
    box.innerHTML = "<p style='padding: 20px; text-align: center; color: #d73a49;'>⏳ 正在加载书籍数据，请稍候...</p>";
    return;
  }
  
  // 清除之前的定时器
  if (searchTimeout) {
    clearTimeout(searchTimeout);
  }
  
  // 如果输入为空，清空结果
  if (!keyword) {
    document.getElementById("search-results").innerHTML = "";
    return;
  }
  
  // 防抖：300ms 后执行搜索
  searchTimeout = setTimeout(() => {
    const results = searchBooks(keyword);
    console.log(`🔍 搜索 "${keyword}" 找到 ${results.length} 条结果`);
    renderResults(results, keyword);
  }, 300);
}

// 页面加载完成后加载数据
(function() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadBooks);
  } else {
    loadBooks();
  }
})();
