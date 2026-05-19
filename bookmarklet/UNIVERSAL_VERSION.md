# FlowScribe Bookmarklet - Universal Version

## 🌐 通用视频链接检测

这个版本可以在**任何网站**上检测视频链接，不仅限于特定平台。

## 支持的网站

### 🎯 优化支持（平台特定检测）
- ✅ **Bilibili** (哔哩哔哩)
- ✅ **YouTube**
- ✅ **Xiaohongshu** (小红书)
- ✅ **Bing Video Search** (必应视频搜索)

### 🌍 通用支持（URL 模式匹配）
- ✅ **Vimeo**
- ✅ **Dailymotion**
- ✅ **Twitch**
- ✅ **TikTok**
- ✅ **Douyin** (抖音)
- ✅ **iQiyi** (爱奇艺)
- ✅ **Tencent Video** (腾讯视频)
- ✅ **Youku** (优酷)
- ✅ **AcFun**
- ✅ **任何包含视频链接的网页**

## 🔍 检测逻辑

### 1. 平台特定检测
如果识别到特定平台（Bilibili、YouTube 等），使用优化的选择器：

```javascript
// Bilibili
.bili-video-card, .video-card, .small-item, .list-item

// YouTube
ytd-video-renderer, ytd-grid-video-renderer

// Xiaohongshu
.note-item, .feed-item, [class*="note"]

// Bing
.dg_u, .mc_vtvc, [class*="video"]
```

### 2. 通用检测
如果不是特定平台，扫描页面所有链接，匹配视频 URL 模式：

```javascript
const videoPatterns = [
    /bilibili\.com\/video\//i,
    /youtube\.com\/watch/i,
    /youtu\.be\//i,
    /xiaohongshu\.com\/explore\//i,
    /vimeo\.com\//i,
    /dailymotion\.com\/video\//i,
    /twitch\.tv\//i,
    /tiktok\.com\/@/i,
    /douyin\.com\/video\//i,
    /iqiyi\.com\//i,
    /qq\.com\/.*\/cover\//i,
    /v\.qq\.com\//i,
    /youku\.com\/v_show\//i,
    /acfun\.cn\/v\//i,
];
```

### 3. 智能提取
对于每个匹配的链接，自动提取：
- **标题**：从链接文本、title 属性、附近的标题元素
- **缩略图**：从 `<img>` 标签（支持 `src`、`data-src`、`data-original`）
- **时长**：从附近的 duration 元素
- **URL**：完整的视频链接

## 📋 使用场景

### 场景 1: 小红书探索页面
```
1. 访问 xiaohongshu.com/explore
2. 按 Alt+F
3. 自动检测所有视频笔记
4. 显示选择对话框
5. 勾选要添加的视频
6. 批量添加到队列
```

### 场景 2: Bing 视频搜索
```
1. 在 Bing 搜索视频（如 "cctv"）
2. 按 Alt+F
3. 检测所有搜索结果
4. 选择要添加的视频
5. 批量添加
```

### 场景 3: 任意视频聚合网站
```
1. 访问包含多个视频链接的页面
2. 按 Alt+F
3. 通用检测器扫描所有视频链接
4. 显示选择对话框
5. 添加选中项
```

### 场景 4: 单个视频页面
```
1. 访问单个视频页面
2. 按 Alt+F
3. 自动添加当前页面 URL
```

## 🎨 选择对话框特性

- **缩略图预览**：显示视频封面（如果有）
- **标题显示**：最多 2 行，超出省略
- **时长显示**：显示视频时长
- **URL 显示**：显示完整 URL（小字灰色）
- **全选/取消**：一键全选或取消所有
- **已选计数**：实时显示已选择数量
- **关闭按钮**：右上角 ✕ 按钮
- **响应式设计**：宽度 90%，最大 800px
- **滚动支持**：最多显示 50 个链接

## ⚙️ 配置选项

```javascript
const CONFIG = {
    serverUrl: 'http://127.0.0.1:8765',  // 服务器地址
    timeout: 5000,                        // 请求超时（毫秒）
    notificationDuration: 3000,           // 通知显示时长（毫秒）
    maxLinks: 50,                         // 最多显示链接数
};
```

## 🔧 自定义扩展

### 添加新的视频平台

在 `videoPatterns` 数组中添加新的正则表达式：

```javascript
const videoPatterns = [
    // 现有模式...
    /your-video-site\.com\/video\//i,  // 添加你的网站
];
```

### 添加平台特定检测

创建新的检测函数：

```javascript
function detectYourSiteLinks() {
    const links = [];
    const cards = document.querySelectorAll('.your-video-card');
    
    cards.forEach((card, index) => {
        const link = card.querySelector('a[href*="/video/"]');
        const title = card.querySelector('.title');
        
        if (link && link.href) {
            links.push({
                url: link.href,
                title: title ? title.textContent.trim() : `Video ${index + 1}`,
                duration: 'Unknown',
                thumbnail: '',
            });
        }
    });
    
    return links;
}
```

然后在 `detectVideoLinks()` 中添加：

```javascript
if (hostname.includes('your-site.com')) {
    links = detectYourSiteLinks();
}
```

## 📊 检测优先级

1. **平台特定检测**（最高优先级）
   - Bilibili
   - YouTube
   - Xiaohongshu
   - Bing

2. **通用 URL 模式匹配**（备用）
   - 扫描所有 `<a>` 标签
   - 匹配视频 URL 模式
   - 提取标题和缩略图

3. **当前页面 URL**（最后备用）
   - 如果没有检测到任何链接
   - 添加当前页面 URL

## 🚀 安装方法

### 方法 1: 复制完整版（推荐用于开发）
```
1. 复制 flowscribe-bookmarklet-universal.js 的内容
2. 在浏览器控制台粘贴并运行
3. 用于测试和调试
```

### 方法 2: 创建书签（推荐用于日常使用）
```
1. 书签栏右键 → "添加书签"
2. 名称: FlowScribe Universal
3. URL: 粘贴压缩版代码（需要先压缩）
4. 保存
```

### 方法 3: 使用安装页面
```
1. 打开 bookmarklet/index.html
2. 拖拽"通用版"按钮到书签栏
```

## 🐛 故障排查

### 问题 1: 没有检测到视频链接
**原因**：
- 页面使用了非标准的 HTML 结构
- 视频链接是动态加载的
- URL 模式不匹配

**解决方法**：
1. 打开浏览器控制台
2. 运行 `detectVideoLinks()` 查看返回结果
3. 检查页面 HTML 结构
4. 添加自定义检测规则

### 问题 2: 缩略图不显示
**原因**：
- 图片使用了懒加载
- 图片 URL 在 `data-src` 而不是 `src`

**解决方法**：
- 脚本已支持 `data-src` 和 `data-original`
- 如果还不显示，检查图片属性名称

### 问题 3: 标题显示不正确
**原因**：
- 标题在非标准元素中
- 标题被 JavaScript 动态生成

**解决方法**：
- 通用检测器会尝试多个选择器
- 可以添加自定义选择器

## 📈 性能优化

- **去重**：使用 `Set` 避免重复链接
- **限制数量**：最多显示 50 个链接（可配置）
- **懒加载**：缩略图加载失败自动隐藏
- **事件委托**：高效处理大量复选框

## 🔒 安全性

- **URL 验证**：只处理 `http://` 和 `https://` 链接
- **XSS 防护**：所有用户输入都经过转义
- **CORS 支持**：服务器端已配置 CORS 头
- **超时保护**：5 秒超时自动取消请求

## 📝 更新日志

### v3.0 (Universal)
- ✅ 通用视频链接检测
- ✅ 支持小红书
- ✅ 支持 Bing 视频搜索
- ✅ 支持 10+ 视频平台
- ✅ 智能标题和缩略图提取
- ✅ URL 显示在对话框中
- ✅ 关闭按钮
- ✅ 响应式设计

### v2.0 (Link Detection)
- ✅ 视频链接检测（Bilibili、YouTube）
- ✅ 批量添加
- ✅ 选择对话框

### v1.0 (Basic)
- ✅ 智能 URL 提取
- ✅ 标题提取
- ✅ 美化通知
- ✅ 快捷键支持

## 📄 许可证

MIT License - 与 FlowScribe 主项目相同
