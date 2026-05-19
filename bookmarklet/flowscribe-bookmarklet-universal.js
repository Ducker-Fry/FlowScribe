/**
 * FlowScribe Bookmarklet - Universal Version
 *
 * Features:
 * - Universal video link detection (works on any website)
 * - Platform-specific optimizations (Bilibili, YouTube, Xiaohongshu, Bing, etc.)
 * - Smart filtering and deduplication
 * - Keyboard shortcut (Alt+F)
 * - Queue status sync
 */

(function() {
    'use strict';

    const CONFIG = {
        serverUrl: 'http://127.0.0.1:8765',
        timeout: 5000,
        notificationDuration: 3000,
        maxLinks: 50, // Maximum links to show in dialog
    };

    let isProcessing = false;

    // ============================================================================
    // Universal Video Link Detection
    // ============================================================================

    /**
     * Detect video links universally across any website
     */
    function detectVideoLinks() {
        const hostname = window.location.hostname;

        // Try platform-specific detection first
        let links = [];

        if (hostname.includes('bilibili.com')) {
            links = detectBilibiliLinks();
        } else if (hostname.includes('youtube.com')) {
            links = detectYouTubeLinks();
        } else if (hostname.includes('xiaohongshu.com')) {
            links = detectXiaohongshuLinks();
        } else if (hostname.includes('bing.com')) {
            links = detectBingVideoLinks();
        }

        // If platform-specific detection found links, use them
        if (links.length > 0) {
            return links;
        }

        // Otherwise, use universal detection
        return detectUniversalVideoLinks();
    }

    /**
     * Universal video link detector - works on any website
     */
    function detectUniversalVideoLinks() {
        const links = [];
        const seen = new Set();

        // Video URL patterns
        const videoPatterns = [
            /bilibili\.com\/video\//i,
            /youtube\.com\/watch/i,
            /youtu\.be\//i,
            /xiaohongshu\.com\/explore\//i,
            /xiaohongshu\.com\/discovery\/item\//i,
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

        // Find all links on the page
        const allLinks = document.querySelectorAll('a[href]');

        allLinks.forEach((link, index) => {
            const href = link.href;
            const text = link.textContent.trim();

            // Skip if already seen
            if (seen.has(href)) return;

            // Check if URL matches video patterns
            const isVideoUrl = videoPatterns.some(pattern => pattern.test(href));

            if (isVideoUrl) {
                // Extract thumbnail
                let thumbnail = '';
                const img = link.querySelector('img');
                if (img) {
                    thumbnail = img.src || img.dataset.src || img.dataset.original || '';
                }

                // Extract title
                let title = text || link.getAttribute('title') || link.getAttribute('aria-label') || '';

                // Try to find title in nearby elements
                if (!title || title.length < 5) {
                    const parent = link.closest('div, li, article, section');
                    if (parent) {
                        const titleEl = parent.querySelector('.title, .name, h1, h2, h3, h4, [class*="title"], [class*="Title"]');
                        if (titleEl) {
                            title = titleEl.textContent.trim();
                        }
                    }
                }

                // Extract duration
                let duration = 'Unknown';
                const parent = link.closest('div, li, article, section');
                if (parent) {
                    const durationEl = parent.querySelector('.duration, [class*="duration"], [class*="time"], time');
                    if (durationEl) {
                        duration = durationEl.textContent.trim();
                    }
                }

                // Add to links
                if (title && title.length > 0) {
                    links.push({
                        url: href,
                        title: title.substring(0, 100), // Limit title length
                        duration: duration,
                        thumbnail: thumbnail,
                    });
                    seen.add(href);
                }
            }
        });

        // Limit to maxLinks
        return links.slice(0, CONFIG.maxLinks);
    }

    /**
     * Detect Bilibili video links
     */
    function detectBilibiliLinks() {
        const links = [];
        const cards = document.querySelectorAll('.bili-video-card, .video-card, .small-item, .list-item, .video-item');

        cards.forEach((card, index) => {
            const link = card.querySelector('a[href*="/video/"]');
            const title = card.querySelector('.bili-video-card__info--tit, .title, .name, h3, h4');
            const duration = card.querySelector('.bili-video-card__stats__duration, .duration, [class*="duration"]');
            const img = card.querySelector('img');

            if (link && link.href) {
                const bvMatch = link.href.match(/BV[a-zA-Z0-9]+/);
                if (bvMatch) {
                    links.push({
                        url: `https://www.bilibili.com/video/${bvMatch[0]}`,
                        title: title ? title.textContent.trim() : `Video ${index + 1}`,
                        duration: duration ? duration.textContent.trim() : 'Unknown',
                        thumbnail: img ? (img.src || img.dataset.src || '') : '',
                    });
                }
            }
        });

        return links;
    }

    /**
     * Detect YouTube video links
     */
    function detectYouTubeLinks() {
        const links = [];
        const cards = document.querySelectorAll('ytd-video-renderer, ytd-grid-video-renderer, ytd-playlist-video-renderer, ytd-compact-video-renderer');

        cards.forEach((card, index) => {
            const link = card.querySelector('a#video-title, a.yt-simple-endpoint');
            const duration = card.querySelector('span.ytd-thumbnail-overlay-time-status-renderer, .ytd-thumbnail-overlay-time-status-renderer');
            const img = card.querySelector('img');

            if (link && link.href) {
                const urlObj = new URL(link.href);
                const videoId = urlObj.searchParams.get('v');
                if (videoId) {
                    links.push({
                        url: `https://www.youtube.com/watch?v=${videoId}`,
                        title: link.textContent.trim() || `Video ${index + 1}`,
                        duration: duration ? duration.textContent.trim() : 'Unknown',
                        thumbnail: img ? img.src : '',
                    });
                }
            }
        });

        return links;
    }

    /**
     * Detect Xiaohongshu (小红书) video links
     */
    function detectXiaohongshuLinks() {
        const links = [];
        const cards = document.querySelectorAll('.note-item, .feed-item, [class*="note"], [class*="card"]');

        cards.forEach((card, index) => {
            const link = card.querySelector('a[href*="/explore/"], a[href*="/discovery/item/"]');
            const title = card.querySelector('.title, .note-title, [class*="title"]');
            const img = card.querySelector('img');

            // Check if it's a video (has play icon or video indicator)
            const hasVideoIndicator = card.querySelector('[class*="video"], [class*="play"], .icon-video, .video-icon');

            if (link && link.href && hasVideoIndicator) {
                links.push({
                    url: link.href,
                    title: title ? title.textContent.trim() : `Video ${index + 1}`,
                    duration: 'Unknown',
                    thumbnail: img ? (img.src || img.dataset.src || '') : '',
                });
            }
        });

        return links;
    }

    /**
     * Detect Bing video search results
     */
    function detectBingVideoLinks() {
        const links = [];
        const cards = document.querySelectorAll('.dg_u, .mc_vtvc, [class*="video"]');

        cards.forEach((card, index) => {
            const link = card.querySelector('a[href]');
            const title = card.querySelector('.mc_vtvc_title, .title, h2, h3');
            const duration = card.querySelector('.mc_vtvc_meta_row_item, .duration, [class*="duration"]');
            const img = card.querySelector('img');

            if (link && link.href) {
                links.push({
                    url: link.href,
                    title: title ? title.textContent.trim() : link.textContent.trim() || `Video ${index + 1}`,
                    duration: duration ? duration.textContent.trim() : 'Unknown',
                    thumbnail: img ? (img.src || img.dataset.src || '') : '',
                });
            }
        });

        return links;
    }

    // ============================================================================
    // URL Extraction
    // ============================================================================

    function extractUrl() {
        const url = window.location.href;
        const hostname = window.location.hostname;

        if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) {
            return extractYouTubeUrl(url);
        }

        if (hostname.includes('bilibili.com')) {
            return extractBilibiliUrl(url);
        }

        return url;
    }

    function extractYouTubeUrl(url) {
        if (url.includes('youtu.be/')) {
            const match = url.match(/youtu\.be\/([a-zA-Z0-9_-]+)/);
            if (match) return `https://www.youtube.com/watch?v=${match[1]}`;
        }

        if (url.includes('youtube.com/watch')) {
            const urlObj = new URL(url);
            const videoId = urlObj.searchParams.get('v');
            if (videoId) return `https://www.youtube.com/watch?v=${videoId}`;
        }

        return url;
    }

    function extractBilibiliUrl(url) {
        const bvMatch = url.match(/BV[a-zA-Z0-9]+/);
        if (bvMatch) return `https://www.bilibili.com/video/${bvMatch[0]}`;

        const avMatch = url.match(/av(\d+)/);
        if (avMatch) return `https://www.bilibili.com/video/av${avMatch[1]}`;

        return url;
    }

    function extractTitle() {
        let title = document.title.trim();

        if (!title) {
            const ogTitle = document.querySelector('meta[property="og:title"]');
            if (ogTitle) title = ogTitle.getAttribute('content') || '';
        }

        if (!title) {
            const h1 = document.querySelector('h1');
            if (h1) title = h1.textContent.trim();
        }

        title = cleanTitle(title);
        return title || 'Untitled';
    }

    function cleanTitle(title) {
        const suffixes = [
            / - YouTube$/,
            / - Bilibili$/,
            / - 哔哩哔哩$/,
            / \| Bilibili$/,
            / \| 哔哩哔哩$/,
            /_bilibili$/,
            / - 小红书$/,
            / - Bing$/,
        ];

        for (const suffix of suffixes) {
            title = title.replace(suffix, '');
        }

        return title.trim();
    }

    // ============================================================================
    // Video Link Selection UI
    // ============================================================================

    function showVideoLinkSelectionDialog(links) {
        const existing = document.getElementById('flowscribe-video-dialog');
        if (existing) existing.remove();

        const dialog = document.createElement('div');
        dialog.id = 'flowscribe-video-dialog';
        dialog.innerHTML = `
            <div style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                z-index: 999999;
                background: white;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                max-width: 800px;
                width: 90%;
                max-height: 85vh;
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif;
            ">
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    font-size: 18px;
                    font-weight: 600;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <span>🎬 选择要添加的视频 (${links.length})</span>
                    <div style="display: flex; gap: 10px;">
                        <button id="fs-select-all" style="
                            padding: 6px 12px;
                            border: 1px solid rgba(255,255,255,0.5);
                            border-radius: 4px;
                            background: rgba(255,255,255,0.2);
                            color: white;
                            cursor: pointer;
                            font-size: 13px;
                        ">全选/取消</button>
                        <button id="fs-close" style="
                            padding: 6px 12px;
                            border: 1px solid rgba(255,255,255,0.5);
                            border-radius: 4px;
                            background: rgba(255,255,255,0.2);
                            color: white;
                            cursor: pointer;
                            font-size: 13px;
                        ">✕</button>
                    </div>
                </div>
                <div style="
                    padding: 20px;
                    max-height: 500px;
                    overflow-y: auto;
                " id="flowscribe-video-list">
                    ${links.map((link, idx) => `
                        <label style="
                            display: flex;
                            align-items: flex-start;
                            padding: 12px;
                            margin-bottom: 10px;
                            border: 2px solid #e0e0e0;
                            border-radius: 8px;
                            cursor: pointer;
                            transition: all 0.2s;
                        " onmouseover="this.style.borderColor='#667eea'" onmouseout="this.style.borderColor='#e0e0e0'">
                            <input type="checkbox" checked data-idx="${idx}" style="
                                width: 18px;
                                height: 18px;
                                margin-right: 12px;
                                margin-top: 4px;
                                cursor: pointer;
                                flex-shrink: 0;
                            ">
                            ${link.thumbnail ? `
                                <img src="${link.thumbnail}" style="
                                    width: 120px;
                                    height: 75px;
                                    object-fit: cover;
                                    border-radius: 4px;
                                    margin-right: 12px;
                                    flex-shrink: 0;
                                    background: #f0f0f0;
                                " onerror="this.style.display='none'">
                            ` : ''}
                            <div style="flex: 1; min-width: 0;">
                                <div style="
                                    font-weight: 500;
                                    margin-bottom: 6px;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    display: -webkit-box;
                                    -webkit-line-clamp: 2;
                                    -webkit-box-orient: vertical;
                                    line-height: 1.4;
                                ">
                                    ${link.title}
                                </div>
                                <div style="font-size: 12px; color: #666;">
                                    ${link.duration}
                                </div>
                                <div style="
                                    font-size: 11px;
                                    color: #999;
                                    margin-top: 4px;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    white-space: nowrap;
                                ">
                                    ${link.url}
                                </div>
                            </div>
                        </label>
                    `).join('')}
                </div>
                <div style="
                    padding: 20px;
                    border-top: 1px solid #e0e0e0;
                    display: flex;
                    gap: 10px;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div style="font-size: 13px; color: #666;">
                        已选择: <span id="fs-count">${links.length}</span> / ${links.length}
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button id="fs-cancel" style="
                            padding: 10px 20px;
                            border: 2px solid #e0e0e0;
                            border-radius: 6px;
                            background: white;
                            cursor: pointer;
                            font-size: 14px;
                            font-weight: 500;
                        ">
                            取消
                        </button>
                        <button id="fs-add" style="
                            padding: 10px 20px;
                            border: none;
                            border-radius: 6px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            cursor: pointer;
                            font-size: 14px;
                            font-weight: 500;
                        ">
                            添加选中项
                        </button>
                    </div>
                </div>
            </div>
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 999998;
            " id="fs-backdrop"></div>
        `;

        document.body.appendChild(dialog);

        // Update selected count
        function updateSelectedCount() {
            const checked = dialog.querySelectorAll('input[type="checkbox"]:checked').length;
            document.getElementById('fs-count').textContent = checked;
        }

        // Checkbox change listener
        dialog.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', updateSelectedCount);
        });

        // Select all / deselect all
        document.getElementById('fs-select-all').addEventListener('click', () => {
            const checkboxes = dialog.querySelectorAll('input[type="checkbox"]');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
            updateSelectedCount();
        });

        // Close button
        document.getElementById('fs-close').addEventListener('click', () => {
            dialog.remove();
        });

        // Cancel
        document.getElementById('fs-cancel').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('fs-backdrop').addEventListener('click', () => {
            dialog.remove();
        });

        // Add selected
        document.getElementById('fs-add').addEventListener('click', () => {
            const checkboxes = dialog.querySelectorAll('input[type="checkbox"]:checked');
            const selectedIndices = Array.from(checkboxes).map(cb =>
                parseInt(cb.getAttribute('data-idx'))
            );
            const selectedLinks = selectedIndices.map(idx => links[idx]);
            dialog.remove();
            addLinksToQueue(selectedLinks);
        });
    }

    // ============================================================================
    // Add to Queue
    // ============================================================================

    async function addLinksToQueue(links) {
        try {
            showNotification('正在添加到队列...', 'info');

            const urls = links.map(link => ({
                url: link.url,
                title: link.title,
            }));

            const response = await fetchWithTimeout(
                `${CONFIG.serverUrl}/add-urls`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ urls: urls }),
                },
                CONFIG.timeout
            );

            const data = await response.json();
            const summary = data.summary;

            showNotification(
                `已添加 ${summary.queued} 个视频\n重复: ${summary.duplicates} | 错误: ${summary.errors}`,
                summary.errors > 0 ? 'warning' : 'success'
            );

            setTimeout(() => showQueueStatus(), 1500);

        } catch (error) {
            handleError(error);
        }
    }

    async function addSingleUrl(url, title) {
        try {
            showNotification('正在添加到队列...', 'info');

            const response = await fetchWithTimeout(
                `${CONFIG.serverUrl}/add-url`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: url,
                        title: title,
                        timestamp: new Date().toISOString(),
                    }),
                },
                CONFIG.timeout
            );

            const data = await response.json();

            if (data.status === 'queued') {
                showNotification(
                    `已添加: ${title}\n队列位置: ${data.position}`,
                    'success'
                );
                setTimeout(() => showQueueStatus(), 1500);
            } else if (data.status === 'duplicate') {
                showNotification(
                    `已在队列中: ${data.existing_status}\n${title}`,
                    'warning'
                );
            } else {
                showNotification(`错误: ${data.message}`, 'error');
            }
        } catch (error) {
            handleError(error);
        }
    }

    // ============================================================================
    // Queue Status
    // ============================================================================

    async function getQueueStatus() {
        try {
            const response = await fetchWithTimeout(
                `${CONFIG.serverUrl}/status`,
                { method: 'GET' },
                CONFIG.timeout
            );
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    async function showQueueStatus() {
        const status = await getQueueStatus();
        if (!status) return;

        const queue = status.queue;
        showNotification(
            `队列状态\n总计: ${queue.total} | 待处理: ${queue.pending}\n运行中: ${queue.running} | 已完成: ${queue.completed}`,
            'info'
        );
    }

    // ============================================================================
    // Notification UI
    // ============================================================================

    function showNotification(message, type = 'success') {
        const existing = document.getElementById('flowscribe-notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.id = 'flowscribe-notification';
        notification.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 999999;
                background: ${getBackgroundColor(type)};
                color: white;
                padding: 16px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif;
                font-size: 14px;
                line-height: 1.5;
                max-width: 400px;
                animation: fs-slide-in 0.3s ease-out;
            ">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="font-size: 24px; flex-shrink: 0;">
                        ${getIcon(type)}
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 4px;">
                            FlowScribe
                        </div>
                        <div style="opacity: 0.95; white-space: pre-line;">
                            ${message}
                        </div>
                    </div>
                </div>
            </div>
        `;

        addStyles();
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.firstElementChild.style.animation = 'fs-fade-out 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, CONFIG.notificationDuration);
    }

    function getBackgroundColor(type) {
        const colors = {
            success: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            error: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            warning: 'linear-gradient(135deg, #ffa751 0%, #ffe259 100%)',
            info: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        };
        return colors[type] || colors.info;
    }

    function getIcon(type) {
        const icons = {
            success: '✓',
            error: '✗',
            warning: '⚠',
            info: 'ℹ',
        };
        return icons[type] || icons.info;
    }

    function addStyles() {
        if (!document.getElementById('fs-styles')) {
            const style = document.createElement('style');
            style.id = 'fs-styles';
            style.textContent = `
                @keyframes fs-slide-in {
                    from { transform: translateX(400px); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes fs-fade-out {
                    from { opacity: 1; }
                    to { opacity: 0; transform: translateX(400px); }
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ============================================================================
    // Network Utilities
    // ============================================================================

    function fetchWithTimeout(url, options, timeout) {
        return Promise.race([
            fetch(url, options),
            new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Request timeout')), timeout)
            )
        ]);
    }

    function handleError(error) {
        if (error.message === 'Request timeout') {
            showNotification(
                '连接超时 (5秒)\nFlowScribe 服务器是否正在运行?',
                'error'
            );
        } else if (error.message.includes('Failed to fetch')) {
            showNotification(
                '无法连接到 FlowScribe\n请先启动服务器',
                'error'
            );
        } else {
            showNotification(`意外错误: ${error.message}`, 'error');
        }
    }

    // ============================================================================
    // Main Logic
    // ============================================================================

    async function addToFlowScribe() {
        if (isProcessing) return;
        isProcessing = true;

        try {
            // Try to detect video links
            const videoLinks = detectVideoLinks();

            if (videoLinks.length > 0) {
                // Found video links: show selection dialog
                showVideoLinkSelectionDialog(videoLinks);
            } else {
                // No video links: add current page URL
                const url = extractUrl();
                const title = extractTitle();

                if (!url || !url.startsWith('http')) {
                    showNotification('无效的 URL 格式', 'error');
                    return;
                }

                await addSingleUrl(url, title);
            }
        } catch (error) {
            handleError(error);
        } finally {
            isProcessing = false;
        }
    }

    // ============================================================================
    // Keyboard Shortcut (Alt+F)
    // ============================================================================

    document.addEventListener('keydown', (event) => {
        if (event.altKey && event.key.toLowerCase() === 'f') {
            event.preventDefault();
            addToFlowScribe();
        }
    });

    // Execute
    addToFlowScribe();

})();
