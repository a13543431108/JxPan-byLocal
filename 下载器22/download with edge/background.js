// ========== 配置 ==========
const DEFAULT_SERVER = 'http://127.0.0.1:9876';
let targetServer = DEFAULT_SERVER;
let downloaderAvailable = false;
let downloaderPath = ''; // 下载器程序/EXE路径（自动记录）
let launchAttempts = 0;
const MAX_LAUNCH_ATTEMPTS = 3; // 最大自动启动尝试次数

// ========== 请求头缓存（用于接管敏感链接） ==========
const requestHeadersCache = new Map();
const CACHE_TTL = 600000; // 缓存 600 秒（10分钟），给方案C更多时间匹配

// ========== 加载用户自定义设置 ==========
chrome.storage.local.get(['server', 'downloaderPath'], (result) => {
  if (result.server) targetServer = result.server;
  if (result.downloaderPath) downloaderPath = result.downloaderPath;
  // 首次启动时先尝试获取下载器路径
  fetchDownloaderInfo();
  checkDownloaderStatus();
});

// ========== 获取下载器信息（自动记录路径） ==========
function fetchDownloaderInfo() {
  fetch(`${targetServer}/get_info`)
    .then(response => response.json())
    .then(data => {
      if (data && data.exe_path) {
        downloaderPath = data.exe_path;
        downloaderAvailable = true;
        launchAttempts = 0;
        // 自动保存路径到存储
        chrome.storage.local.set({ downloaderPath: data.exe_path });
        console.log('[SmartDownload] 已自动记录下载器路径:', data.exe_path);
      }
    })
    .catch(() => {
      // 下载器还未启动，正常
    });
}

// ========== 定期检测下载器状态 ==========
function checkDownloaderStatus() {
  fetch(`${targetServer}/status`)
    .then(response => {
      if (response.ok) {
        downloaderAvailable = true;
        launchAttempts = 0;
        // 在线时顺便获取路径（如果还没有记录）
        if (!downloaderPath) {
          fetchDownloaderInfo();
        }
      }
      console.log('[SmartDownload] 下载器状态:', downloaderAvailable ? '在线' : '离线');
    })
    .catch(() => {
      downloaderAvailable = false;
      console.log('[SmartDownload] 下载器离线');
      // 离线时尝试自动启动
      tryLaunchDownloader();
    });
}
setInterval(checkDownloaderStatus, 15000);

// ========== 自动启动下载器 ==========
function tryLaunchDownloader() {
  if (!downloaderPath) return; // 未获取到路径，不打扰用户
  if (launchAttempts >= MAX_LAUNCH_ATTEMPTS) return; // 已达最大重试次数

  launchAttempts++;
  console.log(`[SmartDownload] 尝试启动下载器 (${launchAttempts}/${MAX_LAUNCH_ATTEMPTS}):`, downloaderPath);

  // 使用 Native Messaging 启动下载器（类似 IDM 的做法）
  try {
    chrome.runtime.connectNative('com.smartdownloader');
    console.log('[SmartDownload] 已通过 Native Messaging 启动下载器');

    // 启动后等待上线
    waitForDownloaderOnline();
  } catch (e) {
    console.warn('[SmartDownload] Native Messaging 启动失败:', e.message);
    // 只在最后一次重试失败时通知用户
    if (launchAttempts >= MAX_LAUNCH_ATTEMPTS) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon.png',
        title: '下载器未运行',
        message: '请手动打开下载器程序'
      });
    }
  }
}

// 启动后持续等待下载器上线
function waitForDownloaderOnline() {
  let retries = 0;
  const maxRetries = 30; // 最多等待 30 秒
  const interval = setInterval(() => {
    retries++;
    fetch(`${targetServer}/status`)
      .then(response => {
        if (response.ok) {
          downloaderAvailable = true;
          launchAttempts = 0;
          console.log('[SmartDownload] 下载器已上线');
          // 获取路径
          fetchDownloaderInfo();
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icon.png',
            title: '下载器',
            message: '下载器已成功启动并连接！'
          });
          clearInterval(interval);
        }
      })
      .catch(() => {
        if (retries >= maxRetries) {
          clearInterval(interval);
          console.warn('[SmartDownload] 等待下载器上线超时');
        }
      });
  }, 1000);
}

// 标记是否已通知过用户手动启动
let notifiedManualLaunch = false;

// ========== 抓取请求头（Cookie、Authorization 等） ==========
chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    // 只缓存 GET 请求的敏感头
    if (details.method !== 'GET' || details.tabId === -1) return;

    const important = {};
    details.requestHeaders.forEach(header => {
      const name = header.name.toLowerCase();
      if (['cookie', 'authorization', 'x-csrf-token'].includes(name)) {
        important[name] = header.value;
      }
    });

    if (Object.keys(important).length > 0) {
      requestHeadersCache.set(details.url, {
        headers: important,
        timestamp: Date.now()
      });
    }
  },
  { urls: ['<all_urls>'] },
  ['requestHeaders']
);

// 定期清理过期缓存（每 30 秒）
setInterval(() => {
  const now = Date.now();
  for (const [url, entry] of requestHeadersCache) {
    if (now - entry.timestamp > CACHE_TTL) {
      requestHeadersCache.delete(url);
    }
  }
}, 30000);

// ========== 判断是否应由浏览器自己下载 ==========
function shouldKeepBrowserDownload(url) {
  // 浏览器内部协议（blob:, data:, filesystem: 等）
  return /^(blob|data|filesystem|javascript|about):/i.test(url);
}

// ========== 拦截浏览器下载 ==========
chrome.downloads.onCreated.addListener((downloadItem) => {
  const url = downloadItem.url;

  // 浏览器内部协议 → 放行
  if (shouldKeepBrowserDownload(url)) {
    console.log('[SmartDownload] 内部协议，保留浏览器下载:', url);
    return;
  }

  // 下载器未运行 → 放行
  if (!downloaderAvailable) {
    return;
  }

  // 尝试接管：取消浏览器下载并转发（带 Cookie 头）
  chrome.downloads.cancel(downloadItem.id, () => {
    if (chrome.runtime.lastError) {
      console.warn('[SmartDownload] 取消失败:', chrome.runtime.lastError.message);
    } else {
      sendToDownloader(downloadItem.url, downloadItem.filename, downloadItem.referrer, downloadItem.finalUrl);
    }
  });
});

// ========== 发送下载链接 + 认证头到本地下载器 ==========
function sendToDownloader(url, suggestedFilename, referrer, finalUrl) {
  // 尝试从缓存中获取请求头
  let headers = null;
  const cached = requestHeadersCache.get(url);
  if (cached) {
    headers = cached.headers;
    requestHeadersCache.delete(url);  // 使用后即删
  }

  const payload = {
    url: url,
    filename: suggestedFilename || '',
    referrer: referrer || '',
    final_url: finalUrl || url,
    headers: headers    // 可以是 null 或对象
  };

  fetch(`${targetServer}/add_task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (response.ok) console.log('[SmartDownload] 已发送（含认证信息）:', url);
  })
  .catch(err => {
    console.warn('[SmartDownload] 发送失败:', err.message);
    downloaderAvailable = false;   // 标记离线，下次点击恢复浏览器下载
  });
}

// ========== 方案C：定期检查暂停任务，推送新Cookie ==========
function renewCookiesForTask(url) {
  // 从缓存中获取该 URL 的最新请求头
  const cached = requestHeadersCache.get(url);
  if (!cached || !cached.headers) {
    console.log('[SmartDownload] 缓存中无可用请求头:', url);
    return;
  }

  fetch(`${targetServer}/renew_cookies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: url,
      headers: cached.headers
    })
  })
  .then(response => {
    if (response.ok) {
      console.log('[SmartDownload] 已推送新Cookie到下载器:', url);
      requestHeadersCache.delete(url);  // 使用后即删
    }
  })
  .catch(err => {
    console.warn('[SmartDownload] 推送Cookie失败:', err.message);
  });
}

// 定期从下载器获取暂停任务列表，尝试从缓存匹配 Cookie 并推送
setInterval(() => {
  if (!downloaderAvailable) return;

  fetch(`${targetServer}/status`)
    .then(response => response.json())
    .then(data => {
      if (data && data.tasks && data.tasks.pending_task_urls) {
        data.tasks.pending_task_urls.forEach(task => {
          // 先用原始URL匹配，再尝试用备用URL匹配
          if (requestHeadersCache.has(task.url)) {
            renewCookiesForTask(task.url);
          } else if (task.original_url && task.original_url !== task.url && requestHeadersCache.has(task.original_url)) {
            renewCookiesForTask(task.url);
          }
        });
      }
    })
    .catch(() => {});
}, 30000);

// ========== 监听来自 popup 的消息 ==========
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'launchDownloader') {
    if (message.path) {
      downloaderPath = message.path;
    }
    tryLaunchDownloader();
    waitForDownloaderOnline();
    sendResponse({ status: 'launching' });
  }
  return true; // 保持 sendResponse 通道打开
});