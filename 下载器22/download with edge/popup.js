// ========== 加载保存的设置 ==========
chrome.storage.local.get(['server', 'downloaderPath'], (result) => {
  if (result.server) document.getElementById('server').value = result.server;
  if (result.downloaderPath) {
    document.getElementById('downloaderPath').value = result.downloaderPath;
  } else {
    // 如果没有路径，尝试从下载器获取
    fetchDownloaderPath();
  }
});

// ========== 从下载器获取路径（自动记录） ==========
function fetchDownloaderPath() {
  chrome.storage.local.get(['server'], (result) => {
    const server = result.server || 'http://127.0.0.1:9876';
    fetch(`${server}/get_info`, { signal: AbortSignal.timeout(2000) })
      .then(res => res.json())
      .then(data => {
        if (data && data.exe_path) {
          document.getElementById('downloaderPath').value = data.exe_path;
          chrome.storage.local.set({ downloaderPath: data.exe_path });
        }
      })
      .catch(() => {});
  });
}

// ========== 保存设置 ==========
document.getElementById('save').addEventListener('click', () => {
  const server = document.getElementById('server').value.trim();
  const downloaderPath = document.getElementById('downloaderPath').value.trim();
  chrome.storage.local.set({ server, downloaderPath }, () => {
    alert('设置已保存');
  });
});

// ========== 检测下载器状态 ==========
function updateStatus() {
  const statusEl = document.getElementById('statusText');
  chrome.storage.local.get(['server'], (result) => {
    const server = result.server || 'http://127.0.0.1:9876';
    fetch(`${server}/status`, { signal: AbortSignal.timeout(3000) })
      .then(res => {
        if (res.ok) {
          statusEl.textContent = '✓ 下载器在线';
          statusEl.className = 'status online';
          // 在线时自动获取路径（如果没有）
          chrome.storage.local.get(['downloaderPath'], (r) => {
            if (!r.downloaderPath) fetchDownloaderPath();
          });
        } else {
          statusEl.textContent = '✗ 下载器离线';
          statusEl.className = 'status offline';
        }
      })
      .catch(() => {
        statusEl.textContent = '✗ 下载器离线';
        statusEl.className = 'status offline';
      });
  });
}

// 每秒更新状态
updateStatus();
setInterval(updateStatus, 3000);

// ========== 启动下载器 ==========
document.getElementById('launchBtn').addEventListener('click', () => {
  const path = document.getElementById('downloaderPath').value.trim();
  if (!path) {
    alert('正在自动检测下载器路径，请稍后...');
    fetchDownloaderPath();
    return;
  }

  // 保存路径
  chrome.storage.local.set({ downloaderPath: path }, () => {
    // 通知 background.js 尝试启动
    chrome.runtime.sendMessage({ action: 'launchDownloader', path: path }, (response) => {
      if (chrome.runtime.lastError) {
        // background 可能还没准备好，忽略
      }
    });

    // 等待下载器上线
    const statusEl = document.getElementById('statusText');
    statusEl.textContent = '正在启动下载器...';
    statusEl.className = 'status';

    let retries = 0;
    const maxRetries = 30;
    const checkInterval = setInterval(() => {
      retries++;
      const server = document.getElementById('server').value.trim() || 'http://127.0.0.1:9876';
      fetch(`${server}/status`, { signal: AbortSignal.timeout(2000) })
        .then(res => {
          if (res.ok) {
            statusEl.textContent = '✓ 下载器在线';
            statusEl.className = 'status online';
            // 自动获取路径
            fetchDownloaderPath();
            clearInterval(checkInterval);
          }
        })
        .catch(() => {
          if (retries >= maxRetries) {
            statusEl.textContent = '✗ 启动超时，请手动打开下载器';
            statusEl.className = 'status offline';
            clearInterval(checkInterval);
          }
        });
    }, 1000);
  });
});

// ========== 浏览选择文件 ==========
document.getElementById('browseBtn').addEventListener('click', () => {
  // 创建文件选择器
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.exe,.py,.bat,.cmd';
  input.onchange = (e) => {
    if (e.target.files.length > 0) {
      document.getElementById('downloaderPath').value = e.target.files[0].path || e.target.files[0].name;
    }
  };
  input.click();
});

// ========== 监听来自 background 的状态更新 ==========
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'downloaderStatus') {
    const statusEl = document.getElementById('statusText');
    if (message.online) {
      statusEl.textContent = '✓ 下载器在线';
      statusEl.className = 'status online';
    } else {
      statusEl.textContent = '✗ 下载器离线';
      statusEl.className = 'status offline';
    }
  }
});