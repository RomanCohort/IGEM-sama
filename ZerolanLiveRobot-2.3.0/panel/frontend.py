"""IGEM-sama Operator Control Panel - Frontend HTML."""

PANEL_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IGEM-sama 控制面板</title>
<style>
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3;
  --muted: #8b949e; --accent: #e94560; --accent2: #0f3460; --success: #3fb950; --warn: #d29922;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

/* Layout */
.header { background: var(--card); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 20px; color: var(--accent); }
.header .status { font-size: 13px; color: var(--muted); }
.main { display: grid; grid-template-columns: 280px 1fr 300px; gap: 0; height: calc(100vh - 52px); }

/* Sidebar */
.sidebar { background: var(--card); border-right: 1px solid var(--border); padding: 16px; overflow-y: auto; }
.sidebar h3 { font-size: 12px; text-transform: uppercase; color: var(--muted); margin: 16px 0 8px; letter-spacing: 1px; }
.sidebar h3:first-child { margin-top: 0; }
.nav-btn { display: block; width: 100%; text-align: left; background: none; border: none; color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 14px; margin-bottom: 2px; }
.nav-btn:hover { background: var(--accent2); }
.nav-btn.active { background: var(--accent); color: #fff; }

/* Center content */
.content { padding: 24px; overflow-y: auto; }
.panel { display: none; }
.panel.active { display: block; }
.panel h2 { font-size: 18px; margin-bottom: 16px; color: var(--accent); }

/* Right sidebar */
.rightbar { background: var(--card); border-left: 1px solid var(--border); padding: 16px; overflow-y: auto; }
.rightbar h3 { font-size: 12px; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }

/* Cards */
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.card h4 { font-size: 13px; color: var(--muted); margin-bottom: 8px; }

/* Form elements */
input, textarea, select { background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 6px; padding: 8px 12px; font-size: 14px; width: 100%; margin-bottom: 8px; font-family: inherit; }
textarea { resize: vertical; min-height: 60px; }
input:focus, textarea:focus { outline: none; border-color: var(--accent); }

/* Buttons */
.btn { background: var(--accent2); border: none; color: var(--text); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; margin-right: 6px; margin-bottom: 4px; }
.btn:hover { opacity: 0.9; }
.btn-accent { background: var(--accent); }
.btn-success { background: var(--success); color: #000; }
.btn-warn { background: var(--warn); color: #000; }
.btn-sm { padding: 4px 10px; font-size: 12px; }

/* Toggle switch */
.toggle-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); }
.toggle-row:last-child { border-bottom: none; }
.toggle-label { font-size: 14px; }
.switch { position: relative; width: 44px; height: 24px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; inset: 0; background: var(--border); border-radius: 24px; cursor: pointer; transition: 0.3s; }
.slider:before { content: ''; position: absolute; width: 18px; height: 18px; left: 3px; bottom: 3px; background: var(--text); border-radius: 50%; transition: 0.3s; }
input:checked + .slider { background: var(--success); }
input:checked + .slider:before { transform: translateX(20px); }

/* Stats grid */
.stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.stat-box { background: var(--bg); border-radius: 8px; padding: 12px; text-align: center; }
.stat-box .val { font-size: 24px; font-weight: bold; color: var(--accent); }
.stat-box .lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Emotion display */
.emotion-bar { display: flex; height: 28px; border-radius: 8px; overflow: hidden; margin: 8px 0; }
.emotion-seg { display: flex; align-items: center; justify-content: center; font-size: 10px; color: #fff; transition: width 0.5s; min-width: 0; }

/* Memory list */
.mem-item { background: var(--bg); border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
.mem-item .content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mem-item .meta { color: var(--muted); font-size: 11px; margin-left: 8px; flex-shrink: 0; }

/* Quick action grid */
.action-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.action-btn { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; cursor: pointer; text-align: center; transition: 0.2s; }
.action-btn:hover { border-color: var(--accent); background: var(--accent2); }
.action-btn .icon { font-size: 24px; }
.action-btn .label { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* Log */
#log { background: var(--bg); border-radius: 6px; padding: 8px; font-family: 'Consolas', monospace; font-size: 12px; max-height: 200px; overflow-y: auto; color: var(--muted); line-height: 1.6; }

/* Toast */
.toast { position: fixed; top: 16px; right: 16px; background: var(--success); color: #000; padding: 10px 20px; border-radius: 8px; font-size: 14px; z-index: 999; opacity: 0; transition: opacity 0.3s; }
.toast.show { opacity: 1; }
.toast.error { background: var(--accent); color: #fff; }
</style>
</head>
<body>
<div class="header">
  <h1>IGEM-sama 控制面板</h1>
  <div class="status" id="conn-status">连接中...</div>
</div>
<div class="main">
  <!-- Left Sidebar -->
  <div class="sidebar">
    <h3>导航</h3>
    <button class="nav-btn active" onclick="showPanel('dashboard')">仪表盘</button>
    <button class="nav-btn" onclick="showPanel('actions')">快捷操作</button>
    <button class="nav-btn" onclick="showPanel('knowledge')">知识库管理</button>
    <button class="nav-btn" onclick="showPanel('memory')">记忆管理</button>
    <button class="nav-btn" onclick="showPanel('viewers')">观众档案</button>
    <button class="nav-btn" onclick="showPanel('obs')">OBS控制</button>
    <button class="nav-btn" onclick="showPanel('chat')">手动发言</button>
    <h3>开关</h3>
    <div class="toggle-row">
      <span class="toggle-label">自主行为</span>
      <label class="switch"><input type="checkbox" id="tog-autonomous" checked onchange="toggleFeature('autonomous')"><span class="slider"></span></label>
    </div>
    <div class="toggle-row">
      <span class="toggle-label">情感分析</span>
      <label class="switch"><input type="checkbox" id="tog-sentiment" checked onchange="toggleFeature('sentiment')"><span class="slider"></span></label>
    </div>
  </div>

  <!-- Center Content -->
  <div class="content">
    <!-- Dashboard -->
    <div class="panel active" id="panel-dashboard">
      <h2>实时仪表盘</h2>
      <div class="stat-grid" id="stats">
        <div class="stat-box"><div class="val" id="s-danmaku">0</div><div class="lbl">弹幕总数</div></div>
        <div class="stat-box"><div class="val" id="s-dpm">0</div><div class="lbl">弹幕/分钟</div></div>
        <div class="stat-box"><div class="val" id="s-viewers">0</div><div class="lbl">独立观众</div></div>
        <div class="stat-box"><div class="val" id="s-interactions">0</div><div class="lbl">互动次数</div></div>
      </div>
      <div class="card">
        <h4>当前情绪</h4>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span id="e-label" style="font-size:28px;font-weight:bold;">neutral</span>
          <span id="e-intensity" style="color:var(--muted);">0.00</span>
        </div>
        <div class="emotion-bar" id="emotion-bar"></div>
      </div>
      <div class="card">
        <h4>服务状态</h4>
        <div id="services" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="panel" id="panel-actions">
      <h2>快捷操作</h2>
      <div class="action-grid">
        <div class="action-btn" onclick="quickAction('greet')"><div class="icon">&#x1F44B;</div><div class="label">打招呼</div></div>
        <div class="action-btn" onclick="quickAction('quiz')"><div class="icon">&#x2753;</div><div class="label">出题</div></div>
        <div class="action-btn" onclick="quickAction('fact')"><div class="icon">&#x1F52C;</div><div class="label">科普知识</div></div>
        <div class="action-btn" onclick="quickAction('project')"><div class="icon">&#x1F3AF;</div><div class="label">介绍项目</div></div>
        <div class="action-btn" onclick="quickAction('lottery')"><div class="icon">&#x1F381;</div><div class="label">抽奖</div></div>
        <div class="action-btn" onclick="quickAction('vote')"><div class="icon">&#x1F4CA;</div><div class="label">投票</div></div>
        <div class="action-btn" onclick="quickAction('countdown')"><div class="icon">&#x23F1;</div><div class="label">倒计时</div></div>
        <div class="action-btn" onclick="quickAction('idle')"><div class="icon">&#x1F60A;</div><div class="label">闲聊一下</div></div>
      </div>
      <div class="card" style="margin-top:16px;">
        <h4>手动设定情绪</h4>
        <div style="display:flex;flex-wrap:wrap;gap:6px;">
          <button class="btn btn-sm" onclick="setEmotion('happy')">开心</button>
          <button class="btn btn-sm" onclick="setEmotion('excited')">激动</button>
          <button class="btn btn-sm" onclick="setEmotion('curious')">好奇</button>
          <button class="btn btn-sm" onclick="setEmotion('proud')">自豪</button>
          <button class="btn btn-sm" onclick="setEmotion('shy')">害羞</button>
          <button class="btn btn-sm" onclick="setEmotion('sad')">难过</button>
          <button class="btn btn-sm" onclick="setEmotion('angry')">生气</button>
          <button class="btn btn-sm" onclick="setEmotion('neutral')">平静</button>
        </div>
      </div>
    </div>

    <!-- Knowledge Base -->
    <div class="panel" id="panel-knowledge">
      <h2>知识库管理</h2>
      <div class="card">
        <h4>搜索知识库</h4>
        <input id="kb-query" placeholder="输入搜索关键词...">
        <button class="btn btn-accent" onclick="kbSearch()">搜索</button>
        <div id="kb-results" style="margin-top:12px;"></div>
      </div>
      <div class="card">
        <h4>导入文档</h4>
        <input id="kb-path" placeholder="文件/目录路径 (如 knowledge_base/docs)" value="knowledge_base/docs">
        <input id="kb-category" placeholder="分类 (如 project, parts, safety)" value="general">
        <label style="font-size:13px;display:flex;align-items:center;gap:6px;margin-bottom:8px;">
          <input type="checkbox" id="kb-reset"> 重建（删除旧数据后重新导入）
        </label>
        <button class="btn btn-accent" onclick="kbIngest()">导入</button>
      </div>
    </div>

    <!-- Memory -->
    <div class="panel" id="panel-memory">
      <h2>记忆管理</h2>
      <div class="card">
        <h4>添加记忆</h4>
        <textarea id="mem-content" placeholder="输入要记住的内容..."></textarea>
        <input id="mem-category" placeholder="分类" value="fact">
        <button class="btn btn-accent" onclick="memAdd()">添加</button>
      </div>
      <div class="card">
        <h4>所有记忆 <span id="mem-count" style="color:var(--muted);"></span></h4>
        <div id="mem-list"></div>
      </div>
    </div>

    <!-- Viewers -->
    <div class="panel" id="panel-viewers">
      <h2>观众档案</h2>
      <div id="viewer-list"></div>
    </div>

    <!-- OBS -->
    <div class="panel" id="panel-obs">
      <h2>OBS 控制</h2>
      <div class="card">
        <h4>切换场景</h4>
        <div style="display:flex;flex-wrap:wrap;gap:6px;">
          <button class="btn btn-sm" onclick="obsScene('idle')">空闲</button>
          <button class="btn btn-sm" onclick="obsScene('talk')">聊天</button>
          <button class="btn btn-sm" onclick="obsScene('quiz')">问答</button>
          <button class="btn btn-sm" onclick="obsScene('game')">游戏</button>
        </div>
      </div>
      <div class="card">
        <h4>叠层文字</h4>
        <textarea id="obs-text" placeholder="输入要显示在画面上的文字..."></textarea>
        <input id="obs-source" placeholder="OBS文字源名称" value="OverlayText">
        <button class="btn btn-accent" onclick="obsOverlay('show')">显示</button>
        <button class="btn" onclick="obsOverlay('clear')">清除</button>
        <button class="btn btn-warn" onclick="obsOverlay('hide')">隐藏</button>
      </div>
    </div>

    <!-- Chat -->
    <div class="panel" id="panel-chat">
      <h2>手动发言</h2>
      <div class="card">
        <h4>通过LLM回复（AI生成）</h4>
        <textarea id="chat-llm" placeholder="输入提示词，IGEM-sama会根据提示词生成回复..."></textarea>
        <button class="btn btn-accent" onclick="chatLLM()">发送给AI</button>
      </div>
      <div class="card">
        <h4>直接发言（绕过LLM，直出TTS）</h4>
        <textarea id="chat-direct" placeholder="输入要IGEM-sama直接说的话..."></textarea>
        <button class="btn btn-success" onclick="chatDirect()">直接说出</button>
      </div>
    </div>
  </div>

  <!-- Right Sidebar -->
  <div class="rightbar">
    <h3>操作日志</h3>
    <div id="log"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let refreshTimer;

function log(msg, type='info') {
  const el = document.getElementById('log');
  const t = new Date().toLocaleTimeString();
  const color = type === 'error' ? 'var(--accent)' : type === 'success' ? 'var(--success)' : 'var(--muted)';
  el.innerHTML += `<div style="color:${color}">[${t}] ${msg}</div>`;
  el.scrollTop = el.scrollHeight;
}

function toast(msg, error=false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (error ? ' error' : '');
  setTimeout(() => el.className = 'toast', 2500);
}

async function api(path, method='GET', body=null) {
  try {
    const opts = { method, headers: {'Content-Type': 'application/json'} };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    return await res.json();
  } catch(e) {
    log('API错误: ' + e.message, 'error');
    return null;
  }
}

// Panel switching
function showPanel(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  event.target.classList.add('active');
  if (id === 'memory') memList();
  if (id === 'viewers') viewerList();
}

// Refresh dashboard
async function refresh() {
  const data = await api('/api/status');
  if (!data || !data.running) {
    document.getElementById('conn-status').textContent = '未连接';
    return;
  }
  document.getElementById('conn-status').textContent = '运行中 | ' + data.bot_name;
  document.getElementById('s-danmaku').textContent = data.analytics.danmaku_count;
  document.getElementById('s-dpm').textContent = data.analytics.danmaku_per_minute;
  document.getElementById('s-viewers').textContent = data.analytics.unique_viewers;
  document.getElementById('s-interactions').textContent = data.analytics.interaction_count;
  // Emotion
  document.getElementById('e-label').textContent = data.emotion.dominant;
  document.getElementById('e-intensity').textContent = data.emotion.intensity.toFixed(2);
  const bar = document.getElementById('emotion-bar');
  const colors = {happy:'#FFD700',excited:'#FF6347',calm:'#87CEEB',curious:'#9370DB',sad:'#4682B4',angry:'#DC143C',shy:'#FF69B4',proud:'#32CD32',neutral:'#808080'};
  bar.innerHTML = '';
  for (const [e, v] of Object.entries(data.emotion.all)) {
    if (v > 0.01) {
      const seg = document.createElement('div');
      seg.className = 'emotion-seg';
      seg.style.width = (v * 100) + '%';
      seg.style.background = colors[e] || '#808080';
      if (v > 0.15) seg.textContent = e;
      bar.appendChild(seg);
    }
  }
  // Services
  const svcs = document.getElementById('services');
  svcs.innerHTML = '';
  for (const [name, ok] of Object.entries(data.services)) {
    const badge = document.createElement('span');
    badge.style.cssText = `padding:4px 10px;border-radius:12px;font-size:12px;background:${ok?'var(--success)':'var(--border)'};color:${ok?'#000':'var(--muted)'}`;
    badge.textContent = name + (ok ? ' ON' : ' OFF');
    svcs.appendChild(badge);
  }
}

// Toggles
async function toggleFeature(feature) {
  const el = document.getElementById('tog-' + feature);
  await api('/api/toggle/' + feature, 'POST', {enabled: el.checked});
  log(feature + ' -> ' + el.checked, 'success');
}

// Quick actions
async function quickAction(action) {
  const prompts = {
    greet: '跟观众打个招呼吧！',
    quiz: '你想和观众玩一个iGEM知识问答游戏。',
    fact: '给观众分享一个合成生物学的有趣知识。',
    project: '介绍一下IGEM-FBH团队的项目亮点。',
    lottery: '启动一个抽奖活动！让观众发弹幕参与。',
    vote: '发起一个投票，问问观众最感兴趣的话题。',
    countdown: '开始一个30秒倒计时，准备下一个环节！',
    idle: '随便聊点什么轻松的话题吧。',
  };
  const r = await api('/api/action/trigger_autonomous', 'POST', {prompt: prompts[action]});
  if (r && r.ok) toast('已触发: ' + action);
  log('快捷操作: ' + action);
}

// Set emotion
async function setEmotion(e) {
  await api('/api/action/emotion', 'POST', {emotion: e, intensity: 0.8});
  toast('情绪 -> ' + e);
  log('手动设定情绪: ' + e);
}

// Knowledge base
async function kbSearch() {
  const q = document.getElementById('kb-query').value;
  if (!q) return;
  const r = await api('/api/kb/search', 'POST', {query: q, top_k: 5});
  const div = document.getElementById('kb-results');
  if (!r || !r.items || r.items.length === 0) { div.innerHTML = '<p style="color:var(--muted)">未找到相关内容</p>'; return; }
  div.innerHTML = r.items.map((item, i) => `<div class="mem-item"><span class="content">${item.text}</span><span class="meta">[${item.category}] ${item.distance}</span></div>`).join('');
}

async function kbIngest() {
  const path = document.getElementById('kb-path').value;
  const cat = document.getElementById('kb-category').value;
  const reset = document.getElementById('kb-reset').checked;
  const r = await api('/api/kb/ingest', 'POST', {path, category: cat, reset});
  if (r && r.ingested !== undefined) toast('导入完成: ' + r.ingested + ' 条');
  log('知识库导入: ' + path);
}

// Memory
async function memList() {
  const r = await api('/api/memory/list');
  if (!r) return;
  document.getElementById('mem-count').textContent = '(' + r.total + ')';
  document.getElementById('mem-list').innerHTML = r.memories.map(m =>
    `<div class="mem-item"><span class="content" title="${m.content}">${m.content}</span><span class="meta">[${m.category}] ${m.age_hours}h <button class="btn btn-sm btn-warn" onclick="memDel('${m.id}')">X</button></span></div>`
  ).join('');
}

async function memAdd() {
  const content = document.getElementById('mem-content').value;
  const cat = document.getElementById('mem-category').value;
  if (!content) return;
  await api('/api/memory/add', 'POST', {content, category: cat});
  toast('记忆已添加');
  log('添加记忆: ' + content.substring(0, 30));
  document.getElementById('mem-content').value = '';
  memList();
}

async function memDel(id) {
  await api('/api/memory/delete/' + id, 'DELETE');
  toast('记忆已删除');
  memList();
}

// Viewers
async function viewerList() {
  const r = await api('/api/viewers');
  if (!r) return;
  document.getElementById('viewer-list').innerHTML = r.viewers.length === 0
    ? '<p style="color:var(--muted)">暂无观众数据</p>'
    : r.viewers.map(v => `<div class="mem-item"><span class="content">${v.username || v.uid} (${v.platform}) - ${v.visits}次</span><span class="meta">${v.notes.join(', ')}</span></div>`).join('');
}

// OBS
async function obsScene(scene) {
  await api('/api/obs/scene', 'POST', {scene});
  toast('场景 -> ' + scene);
  log('OBS场景: ' + scene);
}

async function obsOverlay(action) {
  const text = document.getElementById('obs-text').value;
  const source = document.getElementById('obs-source').value;
  await api('/api/obs/overlay', 'POST', {text, source, action});
  toast('叠层: ' + action);
  log('OBS叠层: ' + action);
}

// Chat
async function chatLLM() {
  const text = document.getElementById('chat-llm').value;
  if (!text) return;
  await api('/api/action/speak', 'POST', {text});
  toast('已发送给AI');
  log('LLM发言: ' + text.substring(0, 30));
  document.getElementById('chat-llm').value = '';
}

async function chatDirect() {
  const text = document.getElementById('chat-direct').value;
  if (!text) return;
  await api('/api/chat/send', 'POST', {text});
  toast('直接发言: ' + text.substring(0, 20));
  log('直接发言: ' + text);
  document.getElementById('chat-direct').value = '';
}

// Init
refresh();
refreshTimer = setInterval(refresh, 3000);
log('控制面板已启动');
</script>
</body>
</html>"""
