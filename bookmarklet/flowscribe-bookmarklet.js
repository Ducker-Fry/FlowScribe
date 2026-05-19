/**
 * FlowScribe Bookmarklet - Enhanced Version
 *
 * Features:
 * - Smart URL extraction (YouTube, Bilibili, generic)
 * - Page metadata extraction (title)
 * - Custom notification UI with animations
 * - Comprehensive error handling
 * - Network timeout protection
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        serverUrl: 'http://127.0.0.1:8765',
        timeout: 5000, // 5 seconds
        notificationDuration: 3000, // 3 seconds
    };

    // ============================================================================
    // Smart URL Extraction
    // ============================================================================

    /**
     * Extract optimized URL based on platform detection
     */
    function extractUrl() {
        const url = window.location.href;
        const hostname = window.location.hostname;

        // YouTube detection
        if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) {
            return extractYouTubeUrl(url);
        }

        // Bilibili detection
        if (hostname.includes('bilibili.com')) {
            return extractBilibiliUrl(url);
        }

        // Generic URL
        return url;
    }

    /**
     * Extract standard YouTube URL format
     */
    function extractYouTubeUrl(url) {
        // Handle youtu.be short links
        if (url.includes('youtu.be/')) {
            const match = url.match(/youtu\.be\/([a-zA-Z0-9_-]+)/);
            if (match) {
                return `https://www.youtube.com/watch?v=${match[1]}`;
            }
        }

        // Handle youtube.com/watch?v=xxx
        if (url.includes('youtube.com/watch')) {
            const urlObj = new URL(url);
            const videoId = urlObj.searchParams.get('v');
            if (videoId) {
                return `https://www.youtube.com/watch?v=${videoId}`;
            }
        }

        // Handle youtube.com/embed/xxx
        if (url.includes('youtube.com/embed/')) {
            const match = url.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]+)/);
            if (match) {
                return `https://www.youtube.com/watch?v=${match[1]}`;
            }
        }

        return url;
    }

    /**
     * Extract Bilibili BV number format
     */
    function extractBilibiliUrl(url) {
        // Extract BV number from various Bilibili URL formats
        const bvMatch = url.match(/BV[a-zA-Z0-9]+/);
        if (bvMatch) {
            return `https://www.bilibili.com/video/${bvMatch[0]}`;
        }

        // Handle av number format
        const avMatch = url.match(/av(\d+)/);
        if (avMatch) {
            return `https://www.bilibili.com/video/av${avMatch[1]}`;
        }

        return url;
    }

    // ============================================================================
    // Metadata Extraction
    // ============================================================================

    /**
     * Extract page title with fallback
     */
    function extractTitle() {
        // Try document.title first
        let title = document.title.trim();

        // Fallback to og:title meta tag
        if (!title) {
            const ogTitle = document.querySelector('meta[property="og:title"]');
            if (ogTitle) {
                title = ogTitle.getAttribute('content') || '';
            }
        }

        // Fallback to first h1
        if (!title) {
            const h1 = document.querySelector('h1');
            if (h1) {
                title = h1.textContent.trim();
            }
        }

        // Clean up title (remove site suffix like " - YouTube")
        title = cleanTitle(title);

        return title || 'Untitled';
    }

    /**
     * Clean up page title by removing common suffixes
     */
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
    // Notification UI
    // ============================================================================

    /**
     * Show custom notification with animation
     */
    function showNotification(message, type = 'success') {
        // Remove existing notification if any
        const existing = document.getElementById('flowscribe-notification');
        if (existing) {
            existing.remove();
        }

        // Create notification element
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

        // Add animation styles
        if (!document.getElementById('flowscribe-styles')) {
            const style = document.createElement('style');
            style.id = 'flowscribe-styles';
            style.textContent = `
                @keyframes flowscribe-slide-in {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes flowscribe-fade-out {
                    from {
                        opacity: 1;
                    }
                    to {
                        opacity: 0;
                        transform: translateX(400px);
                    }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(notification);

        // Auto-remove after duration
        setTimeout(() => {
            notification.firstElementChild.style.animation = 'flowscribe-fade-out 0.3s ease-out';
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

    // ============================================================================
    // Network Request with Timeout
    // ============================================================================

    /**
     * Fetch with timeout support
     */
    function fetchWithTimeout(url, options, timeout) {
        return Promise.race([
            fetch(url, options),
            new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Request timeout')), timeout)
            )
        ]);
    }

    // ============================================================================
    // Main Logic
    // ============================================================================

    async function addToFlowScribe() {
        try {
            // Extract URL and metadata
            const url = extractUrl();
            const title = extractTitle();

            // Validate URL
            if (!url || !url.startsWith('http')) {
                showNotification('Invalid URL format', 'error');
                return;
            }

            // Show loading state
            showNotification('Adding to queue...', 'info');

            // Send request to FlowScribe server
            const response = await fetchWithTimeout(
                `${CONFIG.serverUrl}/add-url`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        title: title,
                        timestamp: new Date().toISOString(),
                    }),
                },
                CONFIG.timeout
            );

            const data = await response.json();

            // Handle response
            if (data.status === 'queued') {
                showNotification(
                    `Added: ${title}\nQueue position: ${data.position}`,
                    'success'
                );
            } else if (data.status === 'duplicate') {
                showNotification(
                    `Already in queue: ${data.existing_status}\n${title}`,
                    'warning'
                );
            } else {
                showNotification(
                    `Error: ${data.message}`,
                    'error'
                );
            }

        } catch (error) {
            // Handle specific errors
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
                showNotification(
                    `Unexpected error: ${error.message}`,
                    'error'
                );
            }
        }
    }

    // Execute
    addToFlowScribe();

})();
