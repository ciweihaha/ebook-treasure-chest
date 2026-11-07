#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成 GitHub Pages 搜索功能演示 GIF
使用 playwright 自动化浏览器操作并录制 GIF
"""
import asyncio
import time
import io
from pathlib import Path
from PIL import Image
import subprocess
import sys

ROOT = Path(__file__).parent.parent
OUTPUT_GIF = ROOT / ".github" / "search-demo.gif"
GITHUB_PAGES_URL = "https://ciweihaha.github.io/ebook-treasure-chest/"

def check_dependencies():
    """检查依赖是否安装"""
    missing = []
    
    # 检查 playwright
    try:
        import playwright
    except ImportError:
        missing.append("playwright")
    
    # 检查 Pillow
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    
    if missing:
        print(f"❌ 缺少以下依赖: {', '.join(missing)}")
        print("\n请安装依赖：")
        if "playwright" in missing:
            print("  pip install playwright")
            print("  playwright install chromium")
        if "Pillow" in missing:
            print("  pip install Pillow")
        return False
    
    return True

async def wait_for_search_results(page, timeout=5000):
    """等待搜索结果出现"""
    try:
        # 等待搜索结果容器有内容（不是"正在加载"）
        await page.wait_for_function(
            """() => {
                const results = document.getElementById('search-results');
                if (!results) return false;
                const text = results.innerText || '';
                return text.length > 0 && !text.includes('正在加载');
            }""",
            timeout=timeout
        )
        # 额外等待一下确保渲染完成
        await asyncio.sleep(0.5)
        return True
    except:
        return False

async def scroll_to_search_results(page):
    """滚动到搜索结果区域，确保搜索结果在视口内"""
    try:
        # 获取搜索结果元素
        search_results = page.locator('#search-results')
        if await search_results.count() > 0:
            # 滚动到搜索结果区域
            await search_results.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            # 稍微向上滚动一点，让搜索框也可见
            await page.evaluate("window.scrollBy(0, -100)")
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"  ⚠️  滚动到搜索结果时出错: {e}")

async def generate_gif():
    """生成搜索功能演示 GIF"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 请先安装 playwright: pip install playwright && playwright install chromium")
        return False
    
    print("🚀 开始生成搜索功能演示 GIF...")
    print(f"📡 访问页面: {GITHUB_PAGES_URL}")
    
    screenshots = []
    
    async with async_playwright() as p:
        # 启动浏览器（无头模式）
        browser = await p.chromium.launch(headless=False)  # 设置为 False 以便观察
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            device_scale_factor=1
        )
        page = await context.new_page()
        
        try:
            # 步骤 1: 访问页面
            print("📄 步骤 1: 加载页面...")
            await page.goto(GITHUB_PAGES_URL, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)  # 等待页面完全加载
            screenshots.append(await page.screenshot())
            print("  ✅ 页面加载完成")
            
            # 步骤 2: 等待数据加载
            print("⏳ 步骤 2: 等待数据加载...")
            # 等待搜索框出现，说明页面已加载
            await page.wait_for_selector('input[type="text"]', timeout=10000)
            await asyncio.sleep(3)  # 等待 all-books.json 加载
            # 检查数据是否加载完成
            data_loaded = await page.evaluate("""() => {
                return window.books && window.books.length > 0;
            }""")
            if data_loaded:
                print(f"  ✅ 数据加载完成（已加载书籍数据）")
            else:
                print(f"  ⚠️  数据可能还在加载中，继续...")
            screenshots.append(await page.screenshot())
            
            # 步骤 3: 输入搜索关键词 "文学"
            print("🔍 步骤 3: 搜索 '文学'...")
            search_input = page.locator('input[type="text"]')
            await search_input.fill("文学")
            await asyncio.sleep(0.5)  # 等待输入完成
            # 等待搜索结果出现
            await wait_for_search_results(page, timeout=5000)
            # 滚动到搜索结果
            await scroll_to_search_results(page)
            screenshots.append(await page.screenshot())
            print("  ✅ 搜索完成，已展示搜索结果")
            
            # 步骤 4: 清空并搜索 "文学 钢铁是怎么炼成的"
            print("🔍 步骤 4: 搜索 '文学 钢铁是怎么炼成的'...")
            await search_input.fill("")
            await asyncio.sleep(0.5)
            await search_input.fill("文学 钢铁是怎么炼成的")
            await asyncio.sleep(0.5)
            # 等待搜索结果
            await wait_for_search_results(page, timeout=5000)
            await scroll_to_search_results(page)
            screenshots.append(await page.screenshot())
            print("  ✅ 搜索完成，已展示搜索结果")
            
            # 步骤 5: 多关键词搜索
            print("🔍 步骤 5: 多关键词搜索 '沟通 樊登 职场'...")
            await search_input.fill("")
            await asyncio.sleep(0.5)
            await search_input.fill("沟通 樊登 职场")
            await asyncio.sleep(0.5)
            # 等待搜索结果
            await wait_for_search_results(page, timeout=5000)
            await scroll_to_search_results(page)
            screenshots.append(await page.screenshot())
            print("  ✅ 多关键词搜索完成，已展示搜索结果")
            
            # 步骤 6: 展示最终结果（多停留一会）
            await asyncio.sleep(1)
            await scroll_to_search_results(page)
            screenshots.append(await page.screenshot())
            
        except Exception as e:
            print(f"❌ 录制过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await browser.close()
    
    # 将截图转换为 GIF
    print("\n🎬 步骤 6: 生成 GIF 动画...")
    try:
        # 将截图转换为 PIL Image
        images = [Image.open(io.BytesIO(img)) for img in screenshots]
        
        # 保存为 GIF
        OUTPUT_GIF.parent.mkdir(parents=True, exist_ok=True)
        # 第一帧显示时间稍长，其他帧正常显示
        durations = [2000] + [1500] * (len(images) - 1)  # 第一帧 2 秒，其他 1.5 秒
        
        # 使用 save_all 保存多帧，但需要手动设置每帧的持续时间
        # 由于 PIL 的 save_all 不支持每帧不同 duration，我们使用固定值
        images[0].save(
            OUTPUT_GIF,
            save_all=True,
            append_images=images[1:],
            duration=1500,  # 每帧 1.5 秒
            loop=0,
            optimize=True
        )
        
        file_size = OUTPUT_GIF.stat().st_size / 1024
        print(f"✅ GIF 已生成: {OUTPUT_GIF}")
        print(f"📦 文件大小: {file_size:.1f} KB")
        print(f"🖼️  帧数: {len(images)}")
        return True
        
    except Exception as e:
        print(f"❌ 生成 GIF 时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    if not check_dependencies():
        sys.exit(1)
    
    # 运行异步函数
    success = asyncio.run(generate_gif())
    
    if success:
        print("\n🎉 完成！搜索功能演示 GIF 已生成")
        print(f"📁 文件位置: {OUTPUT_GIF}")
        print("\n💡 提示: 如果 GIF 质量不理想，可以调整以下参数：")
        print("  - duration: 每帧显示时间（毫秒）")
        print("  - viewport: 浏览器窗口大小")
        print("  - 等待时间: asyncio.sleep() 的延迟")
    else:
        print("\n❌ 生成失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    main()
