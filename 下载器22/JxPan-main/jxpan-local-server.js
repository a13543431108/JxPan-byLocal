/**
 * JxPan 本地解析服务
 * 将 JxPan (Cloudflare Workers) 的网盘解析能力封装为本地 HTTP 服务
 * 供下载器.py 调用
 * 
 * 使用方式: node jxpan-local-server.js [端口号]
 * 默认端口: 18765
 */

const http = require('http');
const url = require('url');

// ===================== 配置 =====================
const DEFAULT_PORT = 18765;
const PORT = parseInt(process.argv[2]) || DEFAULT_PORT;

// 模拟 Cloudflare Workers 的 env 对象
const env = {
    // 环境变量 - 可从外部配置或通过 API 设置
    ALIYUN_AUTHORIZATION: process.env.ALIYUN_AUTHORIZATION || '',
    QK_COOKIE: process.env.QK_COOKIE || '',
    UC_COOKIE: process.env.UC_COOKIE || '',
    MCLOUD_AUTHORIZATION: process.env.MCLOUD_AUTHORIZATION || '',
    CLOUD189_TOKEN: process.env.CLOUD189_TOKEN || '',
    PAN123_TOKEN: process.env.PAN123_TOKEN || '',
    GY_Login: process.env.GY_Login || '',
    admin: process.env.ADMIN || 'admin',
    pass: process.env.PASS || 'admin',
};

// ===================== 加载 JxPan 核心代码 =====================
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const jxpanPath = path.join(__dirname, '未加密源码.js');
if (!fs.existsSync(jxpanPath)) {
    console.error('[JxPan本地服务] 错误: 未找到 未加密源码.js');
    console.error('[JxPan本地服务] 请确保该文件与 jxpan-local-server.js 在同一目录');
    process.exit(1);
}

let jxpanCode = fs.readFileSync(jxpanPath, 'utf-8');

// JxPan 使用 ES Module 的 export default 语法
// 需要将其转换为在沙箱中可用的形式
// 替换 export default { ... } 为将对象赋值给全局变量
// 使用正则匹配最后的 export default 块
jxpanCode = jxpanCode.replace(
    /export\s+default\s*\{/,
    'var __jxpan_export = {'
);

// 同时删除文件末尾可能多余的 export default 相关代码
// 确保最后没有未闭合的 export 语句
// 创建一个沙箱上下文
const sandbox = {
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    setInterval: setInterval,
    clearInterval: clearInterval,
    Buffer: Buffer,
    process: process,
    // Cloudflare Workers 兼容的全局对象
    fetch: globalThis.fetch,
    Request: globalThis.Request,
    Response: globalThis.Response,
    Headers: globalThis.Headers,
    URL: globalThis.URL,
    URLSearchParams: globalThis.URLSearchParams,
    TextEncoder: globalThis.TextEncoder,
    TextDecoder: globalThis.TextDecoder,
    crypto: globalThis.crypto,
    // 模拟 Cloudflare Workers 的 caches
    caches: {
        default: {
            match: async () => null,
            put: async () => {},
            delete: async () => true,
        },
        open: async () => ({
            match: async () => null,
            put: async () => {},
            delete: async () => true,
        })
    },
    // 导出变量
    handleMainRequest: null,
    d1Init: null,
    __jxpan_export: null,
};

const context = vm.createContext(sandbox);

// 在沙箱外部保留 handleMainRequest 引用
let handleMainRequest;
let d1Init;

try {
    vm.runInContext(jxpanCode, context, { 
        filename: '未加密源码.js',
        timeout: 30000 
    });
    
    // 从沙箱中获取导出的函数
    handleMainRequest = context.handleMainRequest;
    d1Init = context.d1Init;
    
    if (typeof handleMainRequest !== 'function') {
        // 尝试查找其他可能的导出函数名
        const funcNames = Object.keys(context).filter(k => typeof context[k] === 'function');
        console.error('[JxPan本地服务] handleMainRequest 未定义');
        console.error('[JxPan本地服务] 沙箱中可用的函数:', funcNames.join(', '));
        throw new Error('handleMainRequest 未定义');
    }
    
    console.log('[JxPan本地服务] JxPan 核心代码已加载 (' + (jxpanCode.length / 1024).toFixed(0) + 'KB)');
    console.log('[JxPan本地服务] handleMainRequest: ' + (typeof handleMainRequest));
} catch (err) {
    console.error('[JxPan本地服务] JxPan 代码加载失败:', err.message);
    console.error('[JxPan本地服务] 请确保 未加密源码.js 是完整且未损坏的');
    process.exit(1);
}

// ===================== 存储配置 =====================
// 存储用户通过 API 设置的环境变量（临时）
const runtimeConfig = {};

// ===================== HTTP 服务器 =====================
const server = http.createServer(async (req, res) => {
    // CORS 头
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
    }

    const parsedUrl = new URL(req.url, `http://127.0.0.1:${PORT}`);
    const pathname = parsedUrl.pathname;

    try {
        if (pathname === '/api/parse' || pathname === '/') {
            // ===== 解析网盘分享链接 =====
            // 参数: ?url=分享链接[&pwd=密码][&id=文件ID]
            let params = Object.fromEntries(parsedUrl.searchParams);
            
            // 如果是 POST 请求，读取 body
            if (req.method === 'POST') {
                const body = await getRequestBody(req);
                try {
                    const json = JSON.parse(body);
                    params = { ...params, ...json };
                } catch (e) {
                    // 尝试表单格式
                    const formParams = new URLSearchParams(body);
                    for (const [k, v] of formParams) {
                        params[k] = v;
                    }
                }
            }

            const targetUrl = params.url || '';
            const pwd = params.pwd || '';
            const fileId = params.id || '';

            if (!targetUrl) {
                sendJson(res, 400, { code: 400, success: false, msg: '缺少 url 参数' });
                return;
            }

            console.log('[JxPan本地服务] 解析请求: url=' + targetUrl.substring(0, 80) + '...');

            // 构建模拟的 Request 对象
            const mockRequestUrl = new URL('http://localhost/?url=' + encodeURIComponent(targetUrl) + 
                (pwd ? '&pwd=' + encodeURIComponent(pwd) : '') +
                (fileId ? '&id=' + encodeURIComponent(fileId) : ''));
            
            const mockRequest = new Request(mockRequestUrl.toString(), {
                method: 'GET',
                headers: { 'User-Agent': 'JxPan-Local/1.0' }
            });

            // 合并运行时配置到 env
            const mergedEnv = { ...env, ...runtimeConfig };

            // 调用 JxPan 的主处理函数
            const response = await handleMainRequest(mockRequest, mergedEnv, null);
            const responseText = await response.text();
            
            let result;
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                result = { code: response.status, success: false, msg: responseText };
            }

            console.log('[JxPan本地服务] 解析结果: code=' + (result.code || result.status) + 
                ', success=' + result.success + 
                ', 文件名=' + (result.data?.file_name || result.data?.name || 'N/A'));

            sendJson(res, response.status, result);

        } else if (pathname === '/api/action' || pathname === '/api/proxy') {
            // ===== 通用 Action 路由 —— 透传所有 JxPan action 请求 =====
            // 用法: ?action=quark_qrcode 或 ?action=aliyun_qr_poll&token=xxx
            // 支持: 扫码登录 (quark/aliyun/cloud189/uc/guangya), 统计数据, 记录查询等
            let params = Object.fromEntries(parsedUrl.searchParams);

            // 如果是 POST 请求,读取 body
            if (req.method === 'POST') {
                const body = await getRequestBody(req);
                try {
                    const json = JSON.parse(body);
                    params = { ...params, ...json };
                } catch (e) {
                    const formParams = new URLSearchParams(body);
                    for (const [k, v] of formParams) {
                        params[k] = v;
                    }
                }
            }

            const action = params.action || '';
            if (!action) {
                sendJson(res, 400, { code: 400, success: false, msg: '缺少 action 参数' });
                return;
            }

            console.log('[JxPan本地服务] Action 请求: action=' + action);

            // 构建完整的查询字符串
            let queryString = 'action=' + encodeURIComponent(action);
            for (const [key, value] of Object.entries(params)) {
                if (key !== 'action' && value) {
                    queryString += '&' + encodeURIComponent(key) + '=' + encodeURIComponent(value);
                }
            }

            const mockRequestUrl = new URL('http://localhost/?' + queryString);
            const mockRequest = new Request(mockRequestUrl.toString(), {
                method: 'GET',
                headers: { 'User-Agent': 'JxPan-Local/1.0' }
            });

            const mergedEnv = { ...env, ...runtimeConfig };
            const response = await handleMainRequest(mockRequest, mergedEnv, null);
            const responseText = await response.text();

            let result;
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                result = { code: response.status, success: false, msg: responseText };
            }

            sendJson(res, response.status, result);

        } else if (pathname === '/api/status') {
            // ===== 服务状态 =====
            sendJson(res, 200, {
                code: 200,
                success: true,
                msg: 'JxPan 本地解析服务运行中',
                data: {
                    version: '1.0.0',
                    jxpan_version: '2026.08.27',
                    uptime: process.uptime(),
                    config: {
                        has_aliyun: !!env.ALIYUN_AUTHORIZATION || !!runtimeConfig.ALIYUN_AUTHORIZATION,
                        has_quark: !!env.QK_COOKIE || !!runtimeConfig.QK_COOKIE,
                        has_uc: !!env.UC_COOKIE || !!runtimeConfig.UC_COOKIE,
                        has_mcloud: !!env.MCLOUD_AUTHORIZATION || !!runtimeConfig.MCLOUD_AUTHORIZATION,
                        has_cloud189: !!env.CLOUD189_TOKEN || !!runtimeConfig.CLOUD189_TOKEN,
                        has_pan123: !!env.PAN123_TOKEN || !!runtimeConfig.PAN123_TOKEN,
                        has_guangya: !!env.GY_Login || !!runtimeConfig.GY_Login,
                    }
                }
            });

        } else if (pathname === '/api/config') {
            // ===== 设置环境变量（运行时临时） =====
            if (req.method === 'POST') {
                const body = await getRequestBody(req);
                try {
                    const config = JSON.parse(body);
                    Object.assign(runtimeConfig, config);
                    console.log('[JxPan本地服务] 配置已更新:', Object.keys(config));
                    sendJson(res, 200, { code: 200, success: true, msg: '配置已更新' });
                } catch (e) {
                    sendJson(res, 400, { code: 400, success: false, msg: 'JSON 解析失败: ' + e.message });
                }
            } else {
                sendJson(res, 200, {
                    code: 200,
                    success: true,
                    data: { env: { ...env }, runtime: runtimeConfig }
                });
            }

        } else if (pathname === '/api/test') {
            // ===== 测试 Node.js 环境是否正常 =====
            sendJson(res, 200, {
                code: 200,
                success: true,
                msg: '服务正常',
                data: {
                    node_version: process.version,
                    platform: process.platform,
                    jxpan_functions: typeof handleMainRequest !== 'undefined' ? '可用' : '不可用'
                }
            });

        } else {
            sendJson(res, 404, { code: 404, success: false, msg: '未知路径: ' + pathname });
        }
    } catch (err) {
        console.error('[JxPan本地服务] 错误:', err.message, err.stack);
        sendJson(res, 500, { code: 500, success: false, msg: '服务器内部错误: ' + err.message });
    }
});

function getRequestBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => resolve(body));
        req.on('error', reject);
    });
}

function sendJson(res, statusCode, data) {
    res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(data));
}

// ===================== 启动服务 =====================
server.listen(PORT, '127.0.0.1', () => {
    console.log('');
    console.log('========================================');
    console.log('  JxPan 本地解析服务');
    console.log('  版本: 1.0.0 (JxPan 2026.08.27)');
    console.log('  Node.js: ' + process.version);
    console.log('========================================');
    console.log('');
    console.log('  服务地址: http://127.0.0.1:' + PORT);
    console.log('');
    console.log('  接口列表:');
    console.log('  GET  /api/test        - 测试服务');
    console.log('  GET  /api/status      - 服务状态');
    console.log('  GET  /api/parse?url=  - 解析网盘分享链接');
    console.log('  POST /api/parse       - 解析网盘分享链接 (JSON body)');
    console.log('  GET/POST /api/action  - JxPan Action 代理 (扫码/统计等)');
    console.log('  POST /api/config      - 设置临时环境变量');
    console.log('  GET  /api/action      - 通用 Action 路由 (扫码登录等)');
    console.log('  GET  /api/proxy       - 通用 Action 路由 (同/action)');
    console.log('');
    console.log('  使用示例:');
    console.log('  http://127.0.0.1:' + PORT + '/api/parse?url=https://www.123pan.cn/s/XXXX');
    console.log('  http://127.0.0.1:' + PORT + '/api/action?action=quark_qrcode');
    console.log('  http://127.0.0.1:' + PORT + '/api/action?action=aliyun_qrcode');
    console.log('');
    console.log('  按 Ctrl+C 停止服务');
    console.log('========================================');
});

// 优雅退出
process.on('SIGINT', () => {
    console.log('\n[JxPan本地服务] 正在停止...');
    server.close(() => {
        console.log('[JxPan本地服务] 已停止');
        process.exit(0);
    });
});

process.on('SIGTERM', () => {
    server.close(() => process.exit(0));
});