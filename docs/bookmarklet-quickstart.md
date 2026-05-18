# Bookmarklet 快速开始指南

## 最简单的方式（推荐）

### 1. 启动 GUI
```powershell
python -m flowscribe.gui
```

### 2. 启用 Server
1. 点击 **Views** → **Queue**
2. 勾选 **☑ Enable Server**
3. 看到绿色提示：`Server: Running on port 8765`

### 3. 安装 Bookmarklet
1. 访问 http://127.0.0.1:8765/bookmarklet.js
2. 复制显示的完整代码
3. 在浏览器中创建书签：
   - 按 `Ctrl+Shift+O` 打开收藏夹管理器
   - 右键 → "添加收藏"
   - 名称：`FlowScribe`
   - URL：粘贴复制的代码

### 4. 使用
1. 打开任意视频网页（YouTube、Bilibili 等）
2. 点击 `FlowScribe` 书签
3. 弹出提示：`✓ Added to FlowScribe queue Position: 1`
4. 返回 GUI，队列自动显示新 URL
5. 点击 **Start Queue** 开始转录

## 完整的 Bookmarklet 代码

如果自动获取失败，可以手动复制：

```javascript
javascript:(function(){var url=window.location.href;var title=document.title;fetch('http://127.0.0.1:8765/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,title:title,timestamp:new Date().toISOString()})}).then(r=>r.json()).then(d=>{if(d.status==='queued'){alert('✓ Added to FlowScribe queue\nPosition: '+d.position);}else if(d.status==='duplicate'){alert('⚠ Already in queue: '+d.existing_status);}else{alert('✗ Error: '+d.message);}}).catch(e=>alert('✗ Connection failed. Is FlowScribe server running?'));})();
```

## 常见问题

**Q: 点击书签显示 "Connection failed"**
- 确保 GUI 中的 Server 已启用（绿色状态）
- 或运行命令：`python -m flowscribe serve`

**Q: 端口被占用怎么办？**
- 在 GUI 的 Port 输入框修改端口号
- 重新勾选 "Enable Server"

**Q: 如何修改输出设置？**
- 在 GUI 主界面修改输出目录、格式、模型、语言
- 新添加的 URL 自动使用新设置

## 详细文档

- [完整使用指南](bookmarklet.md)
- [GUI 集成说明](gui-server-integration.md)
- [命令行配置](server-configuration.md)
