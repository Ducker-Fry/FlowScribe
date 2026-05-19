/**
 * FlowScribe Bookmarklet - Advanced Version
 *
 * Features:
 * - Multi-video detection and selection
 * - Smart filtering (duration, ads, hidden elements)
 * - Keyboard shortcut support (Alt+F)
 * - Queue status synchronization
 * - Batch URL submission
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        serverUrl: 'http://127.0.0.1:8765',
        timeout: 5000,
        notificationDuration: 3000,
        minVideoDuration: 10, // seconds
        adKeywords: ['ad', 'promo', 'advertisement', 'sponsor'],
    };

    // Global state
    let isProcessing = false;

    // ============================================================================
    // Video Detection and Filtering
    // ============================================================================

    /**
     * Detect all video elements on the page
     */
    function detectVideos() {
        const videos = Array.from(document.querySelectorAll('video'));
        const filtered = videos
            .map((video, index) => ({
                element: video,
                index: index,
                src: getVideoSource(video),
                duration: video.duration || 0,
                width: video.videoWidth || video.offsetWidth,
                height: video.videoHeight || video.offsetHeight,
                visible: isVideoVisible(video),
            }))
            .filter(video => isValidVideo(video));

        return filtered;
    }

    /**
     * Get video source URL
     */
    function getVideoSource(video) {
        // Try video.src first
        if (video.src && video.src.startsWith('http')) {
            return video.src;
        }

        // Try source elements
        const sources = video.querySelectorAll('source');
        for (const source of sources) {
            if (source.src && source.src.startsWith('http')) {
                return source.src;
            }
        }

        // Fallback to current page URL
        return window.location.href;
    }

    /**
     * Check if video is visible
     */
    function isVideoVisible(video) {
        const style = window.getComputedStyle(video);
        return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            video.offsetWidth > 0 &&
            video.offsetHeight > 0
        );
    }

    /**
     * Validate video based on filtering rules
     */
    function isValidVideo(video) {
        // Filter by visibility
        if (!video.visible) {
            return false;
        }

        // Filter by duration (skip very short videos)
        if (video.duration > 0 && video.duration < CONFIG.minVideoDuration) {
            return false;
        }

        // Filter by URL keywords (ads, promos)
        const src = video.src.toLowerCase();
        if (CONFIG.adKeywords.some(keyword => src.includes(keyword))) {
            return false;
        }

        // Filter by size (skip tiny videos)
        if (video.width < 200 || video.height < 150) {
            return false;
        }

        return true;
    }

    // ============================================================================
    // Smart URL Extraction
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

        if (url.includes('youtube.com/embed/')) {
            const match = url.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]+)/);
            if (match) return `https://www.youtube.com/watch?v=${match[1]}`;
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
        ];

        for (const suffix of suffixes) {
            title = title.replace(suffix, '');
        }

        return title.trim();
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

    // ============================================================================
    // Multi-Video Selection UI
    // ============================================================================

    function showVideoSelectionDialog(videos) {
        // Remove existing dialog
        const existing = document.getElementById('flowscribe-video-dialog');
        if (existing) existing.remove();

        // Create dialog
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
                max-width: 600px;
                max-height: 80vh;
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            ">
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    font-size: 18px;
                    font-weight: 600;
                ">
                    🎬 Select Videos to Add
                </div>
                <div style="
                    padding: 20px;
                    max-height: 400px;
                    overflow-y: auto;
                " id="flowscribe-video-list">
                    ${videos.map((video, idx) => `
                        <label style="
                            display: flex;
                            align-items: center;
                            padding: 12px;
                            margin-bottom: 8px;
                            border: 2px solid #e0e0e0;
                            border-radius: 8px;
                            cursor: pointer;
                            transition: all 0.2s;
                        " onmouseover="this.style.borderColor='#667eea'" onmouseout="this.style.borderColor='#e0e0e0'">
                            <input type="checkbox" checked data-video-index="${idx}" style="
                                width: 18px;
                                height: 18px;
                                margin-right: 12px;
                                cursor: pointer;
                            ">
                            <div style="flex: 1;">
                                <div style="font-weight: 500; margin-bottom: 4px;">
                                    Video ${idx + 1}
                                </div>
                                <div style="font-size: 12px; color: #666;">
                                    ${video.width}×${video.height} • ${formatDuration(video.duration)}
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
                    justify-content: flex-end;
                ">
                    <button id="flowscribe-cancel-btn" style="
                        padding: 10px 20px;
                        border: 2px solid #e0e0e0;
                        border-radius: 6px;
                        background: white;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 500;
                    ">
                        Cancel
                    </button>
                    <button id="flowscribe-add-btn" style="
                        padding: 10px 20px;
                        border: none;
                        border-radius: 6px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 500;
                    ">
                        Add Selected
                    </button>
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
            " id="flowscribe-dialog-backdrop"></div>
        `;

        document.body.appendChild(dialog);

        // Event listeners
        document.getElementById('flowscribe-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('flowscribe-dialog-backdrop').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('flowscribe-add-btn').addEventListener('click', () => {
            const checkboxes = dialog.querySelectorAll('input[type="checkbox"]:checked');
            const selectedIndices = Array.from(checkboxes).map(cb =>
                parseInt(cb.getAttribute('data-video-index'))
            );
            const selectedVideos = selectedIndices.map(idx => videos[idx]);
            dialog.remove();
            addVideosToQueue(selectedVideos);
        });
    }

    function formatDuration(seconds) {
        if (!seconds || seconds === 0) return 'Unknown';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // ============================================================================
    // Batch Add Videos
    // ============================================================================

    async function addVideosToQueue(videos) {
        const title = extractTitle();
        const urls = videos.map((video, idx) => ({
            url: video.src,
            title: videos.length > 1 ? `${title} - Part ${idx + 1}` : title,
        }));

        try {
            showNotification('Adding videos to queue...', 'info');

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
                `Added ${summary.queued} videos\n` +
                `Duplicates: ${summary.duplicates} | Errors: ${summary.errors}`,
                summary.errors > 0 ? 'warning' : 'success'
            );

            // Show queue status after adding
            setTimeout(() => showQueueStatus(), 1500);

        } catch (error) {
            handleError(error);
        }
    }

    // ============================================================================
    // Queue Status Display
    // ============================================================================

    async function showQueueStatus() {
        const status = await getQueueStatus();
        if (!status) {
            showNotification('Cannot connect to FlowScribe', 'error');
            return;
        }

        const queue = status.queue;
        const message = `
            <div style="text-align: left;">
                <div style="margin-bottom: 8px; font-weight: 600;">Queue Status</div>
                <div style="font-size: 13px; line-height: 1.6;">
                    Total: ${queue.total} | Pending: ${queue.pending}<br>
                    Running: ${queue.running} | Completed: ${queue.completed}
                </div>
            </div>
        `;

        showNotificationWithAction(message, 'info', 'Open FlowScribe', () => {
            // This would require a custom protocol handler
            showNotification('Please open FlowScribe GUI manually', 'info');
        });
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
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                max-width: 400px;
                animation: flowscribe-slide-in 0.3s ease-out;
            ">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="font-size: 24px; flex-shrink: 0;">
                        ${getIcon(type)}
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 4px;">
                            FlowScribe
                        </div>
                        <div style="opacity: 0.95;">
                            ${message}
                        </div>
                    </div>
                </div>
            </div>
        `;

        addStyles();
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.firstElementChild.style.animation = 'flowscribe-fade-out 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, CONFIG.notificationDuration);
    }

    function showNotificationWithAction(message, type, actionText, actionCallback) {
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
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                max-width: 400px;
                animation: flowscribe-slide-in 0.3s ease-out;
            ">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <div style="font-size: 24px; flex-shrink: 0;">
                        ${getIcon(type)}
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 4px;">
                            FlowScribe
                        </div>
                        <div style="opacity: 0.95;">
                            ${message}
                        </div>
                    </div>
                </div>
                <button id="flowscribe-action-btn" style="
                    width: 100%;
                    padding: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    border-radius: 4px;
                    background: rgba(255, 255, 255, 0.1);
                    color: white;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: 500;
                ">
                    ${actionText}
                </button>
            </div>
        `;

        addStyles();
        document.body.appendChild(notification);

        document.getElementById('flowscribe-action-btn').addEventListener('click', () => {
            notification.remove();
            actionCallback();
        });

        setTimeout(() => {
            notification.firstElementChild.style.animation = 'flowscribe-fade-out 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, CONFIG.notificationDuration + 2000);
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
        if (!document.getElementById('flowscribe-styles')) {
            const style = document.createElement('style');
            style.id = 'flowscribe-styles';
            style.textContent = `
                @keyframes flowscribe-slide-in {
                    from { transform: translateX(400px); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes flowscribe-fade-out {
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
                'Connection timeout (5s)\nIs FlowScribe server running?',
                'error'
            );
        } else if (error.message.includes('Failed to fetch')) {
            showNotification(
                'Cannot connect to FlowScribe\nPlease start the server first',
                'error'
            );
        } else {
            showNotification(`Unexpected error: ${error.message}`, 'error');
        }
    }

    // ============================================================================
    // Main Logic
    // ============================================================================

    async function addToFlowScribe() {
        if (isProcessing) return;
        isProcessing = true;

        try {
            // Detect videos on page
            const videos = detectVideos();

            if (videos.length > 1) {
                // Multiple videos: show selection dialog
                showVideoSelectionDialog(videos);
            } else if (videos.length === 1) {
                // Single video: add directly
                await addVideosToQueue(videos);
            } else {
                // No videos: add current page URL
                const url = extractUrl();
                const title = extractTitle();

                if (!url || !url.startsWith('http')) {
                    showNotification('Invalid URL format', 'error');
                    return;
                }

                showNotification('Adding to queue...', 'info');

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
                        `Added: ${title}\nQueue position: ${data.position}`,
                        'success'
                    );
                    setTimeout(() => showQueueStatus(), 1500);
                } else if (data.status === 'duplicate') {
                    showNotification(
                        `Already in queue: ${data.existing_status}\n${title}`,
                        'warning'
                    );
                } else {
                    showNotification(`Error: ${data.message}`, 'error');
                }
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

    function setupKeyboardShortcut() {
        document.addEventListener('keydown', (event) => {
            if (event.altKey && event.key.toLowerCase() === 'f') {
                event.preventDefault();
                addToFlowScribe();
            }
        });
    }

    // Initialize
    setupKeyboardShortcut();
    addToFlowScribe();

})();
