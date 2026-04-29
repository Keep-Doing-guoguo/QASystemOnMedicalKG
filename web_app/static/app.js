const state = {
  lastResponse: null,
  history: [],
  zoom: 1,
  activeView: 'graph',
  sessionId: localStorage.getItem('kgqa_session_id') || null
};

const $ = (id) => document.getElementById(id);

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const payload = await res.json();
    if (!res.ok) throw new Error('bad status');
    $('apiStatus').textContent = '在线';
    $('apiStatus').className = 'status-online';
  } catch (error) {
    $('apiStatus').textContent = '离线';
    $('apiStatus').className = 'status-offline';
  }
}

function ensureSessionId(sessionId) {
  if (!sessionId) return;
  state.sessionId = sessionId;
  localStorage.setItem('kgqa_session_id', sessionId);
}

function currentMode() {
  return $('modeSelect').value;
}

async function sendQuestion(question) {
  const mode = currentMode();
  const endpoint = mode === 'llm' ? '/api/llm/chat' : '/api/rule/chat';
  $('questionText').textContent = question;
  $('answerView').textContent = '查询中...';
  setEmptyState(false);

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question, session_id: state.sessionId || undefined})
    });
    const payload = await res.json();
    if (!res.ok || !payload.ok) throw new Error(payload.error?.message || '请求失败');
    const data = payload.data || {};
    ensureSessionId(data.session_id);
    state.lastResponse = data;
    state.history.unshift({question, mode, data, time: new Date()});
    state.history = state.history.slice(0, 10);
    renderResponse(data);
    renderHistory();
  } catch (error) {
    $('answerView').textContent = `请求失败：${error.message}`;
    renderEvidence([]);
    renderPaths([]);
    renderEntityTags([]);
    renderDebug({mode, debug: {}});
    renderGraph({nodes: [], edges: []});
    renderPathView([]);
    setEmptyState(true);
  }
}

function renderResponse(data) {
  $('questionText').textContent = data.question || '等待输入问题';
  $('answerView').textContent = data.answer || '当前知识图谱中没有查到相关信息。';
  renderDebug(data);
  renderEvidence(data);
  renderPaths(data);
  renderEntityTags(data);
  renderGraph(data.graph || {nodes: [], edges: []});
  renderPathView(buildPathItems(data));
  setEmptyState(!(data.graph && data.graph.nodes && data.graph.nodes.length));
}

function renderDebug(data) {
  const debug = data.debug || {};
  if (data.mode === 'rule_based') {
    $('entitiesJson').textContent = pretty({
      matched_entities: debug.matched_entities || {},
      entity_types: debug.entity_types || [],
      question_types: debug.question_types || []
    });
    $('planJson').textContent = pretty({
      mode: data.mode,
      question_types: debug.question_types || [],
      matched_entities: debug.matched_entities || {}
    });
    $('cypherText').textContent = (debug.cypher || []).join('\n\n');
  } else {
    $('entitiesJson').textContent = pretty({
      linked_entities: debug.linked_entities || []
    });
    $('planJson').textContent = pretty({
      mode: data.mode,
      query_plan: debug.query_plan || {}
    });
    $('cypherText').textContent = [
      debug.cypher || '',
      pretty(debug.parameters || {})
    ].filter(Boolean).join('\n\n参数：\n');
  }
  $('resultsJson').textContent = pretty(debug.graph_results || []);
}

function renderEvidence(data) {
  const debug = data.debug || {};
  const graphResults = debug.graph_results || [];
  const list = $('evidenceList');
  list.innerHTML = '';

  const lines = [];
  if (data.mode === 'llm_based') {
    const plan = debug.query_plan || {};
    const subject = plan.subject?.name;
    if (plan.action === 'query_property' && graphResults.length) {
      lines.push(`${subject} → ${plan.property} → ${stringifyValue(graphResults[0].value)}`);
    } else if (plan.action === 'query_relation') {
      graphResults.slice(0, 8).forEach((item) => {
        const relation = item.relation_name || item.relation || plan.relation || '关系';
        if (plan.direction === 'incoming') {
          lines.push(`${item.object} → ${relation} → ${subject}`);
        } else {
          lines.push(`${subject} → ${relation} → ${item.object}`);
        }
      });
    }
  } else {
    graphResults.slice(0, 8).forEach((item) => {
      const start = item['m.name'] || item.subject || item.object;
      const end = item['n.name'] || item.value;
      const relation = item['r.name'] || item.relation_name || item.relation || '关系';
      if (start && end) lines.push(`${start} → ${relation} → ${end}`);
    });
  }

  if (!lines.length) {
    list.innerHTML = '<li>暂无图谱证据</li>';
    return;
  }

  lines.forEach((line) => {
    const li = document.createElement('li');
    li.textContent = line;
    list.appendChild(li);
  });
}

function renderPaths(data) {
  const container = $('pathList');
  const items = buildPathItems(data);
  container.innerHTML = '';

  if (!items.length) {
    container.innerHTML = '<span class="path-empty">暂无路径</span>';
    return;
  }

  items.forEach((item) => {
    const div = document.createElement('div');
    div.className = 'path-item';
    div.textContent = item.text;
    div.style.color = item.color;
    container.appendChild(div);
  });
}

function renderPathView(items) {
  const container = $('pathView');
  container.innerHTML = '';

  if (!items.length) {
    container.innerHTML = '<div class="path-track"><div class="path-pill"><span class="path-empty">暂无路径</span></div></div>';
    return;
  }

  const track = document.createElement('div');
  track.className = 'path-track';
  items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'path-pill';
    row.innerHTML = `
      <span class="path-node" style="background:${item.color}">${escapeHtml(item.start)}</span>
      <span class="path-arrow">→ ${escapeHtml(item.relation)} →</span>
      <span class="path-node" style="background:${item.color}">${escapeHtml(item.end)}</span>
    `;
    track.appendChild(row);
  });
  container.appendChild(track);
}

function renderEntityTags(data) {
  const debug = data.debug || {};
  const tags = new Set();
  const container = $('entityTags');

  if (data.mode === 'llm_based') {
    (debug.linked_entities || []).forEach((item) => tags.add(item.name));
    const plan = debug.query_plan || {};
    if (plan.subject?.name) tags.add(plan.subject.name);
    (debug.graph_results || []).forEach((item) => {
      if (item.object) tags.add(item.object);
    });
  } else {
    Object.keys(debug.matched_entities || {}).forEach((name) => tags.add(name));
    (debug.graph_results || []).forEach((item) => {
      if (item['m.name']) tags.add(item['m.name']);
      if (item['n.name']) tags.add(item['n.name']);
    });
  }

  container.innerHTML = '';
  if (!tags.size) {
    container.innerHTML = '<span class="tag">暂无实体</span>';
    return;
  }

  [...tags].slice(0, 18).forEach((name) => {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = name;
    container.appendChild(tag);
  });
}

function renderHistory() {
  const list = $('historyList');
  list.innerHTML = '';

  if (!state.history.length) {
    list.innerHTML = '<span class="path-empty">暂无历史记录</span>';
    return;
  }

  state.history.forEach((item) => {
    const btn = document.createElement('button');
    btn.className = 'history-item';
    btn.innerHTML = `
      <strong>${escapeHtml(item.question)}</strong>
      <span>${item.mode === 'llm' ? '高级搜索' : '规则搜索'} · ${formatTime(item.time)}</span>
    `;
    btn.addEventListener('click', () => {
      $('modeSelect').value = item.mode;
      $('questionInput').value = item.question;
      state.lastResponse = item.data;
      renderResponse(item.data);
    });
    list.appendChild(btn);
  });
}

function renderGraph(graph) {
  const svg = $('graphSvg');
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  svg.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,8 L10,4 z" fill="#94a8c7"></path>
      </marker>
    </defs>
  `;

  if (!nodes.length) {
    return;
  }

  const positions = layoutNodes(nodes);
  edges.forEach((edge, index) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return;

    const color = edgeColor(index, edge.type || edge.label || '');
    const line = svgLine(source.x, source.y, target.x, target.y, 'edge');
    line.setAttribute('stroke', color);
    line.querySelector?.('title');
    svg.appendChild(line);

    const label = svgText(
      (source.x + target.x) / 2,
      (source.y + target.y) / 2 - 8,
      edge.label || edge.type || '关系',
      'edge-label'
    );
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', color);
    svg.appendChild(label);
  });

  nodes.forEach((node, index) => {
    const pos = positions[node.id];
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    const fill = colorForType(node.type, index === 0);
    const radius = index === 0 ? 36 : 28;
    circle.setAttribute('cx', pos.x);
    circle.setAttribute('cy', pos.y);
    circle.setAttribute('r', radius);
    circle.setAttribute('fill', fill);
    circle.setAttribute('class', 'node');
    group.appendChild(circle);

    const icon = svgText(pos.x, pos.y + 6, glyphForType(node.type, index === 0), 'node-label');
    icon.setAttribute('text-anchor', 'middle');
    icon.setAttribute('fill', '#ffffff');
    icon.setAttribute('font-size', index === 0 ? '28' : '22');
    group.appendChild(icon);

    const label = svgText(pos.x, pos.y + radius + 32, node.label, 'node-label');
    label.setAttribute('text-anchor', 'middle');
    group.appendChild(label);

    const subtype = svgText(pos.x, pos.y + radius + 52, node.type || 'Entity', 'node-subtype');
    subtype.setAttribute('text-anchor', 'middle');
    group.appendChild(subtype);
    svg.appendChild(group);
  });

  updateZoom();
}

function layoutNodes(nodes) {
  const positions = {};
  const center = {x: 450, y: 290};
  positions[nodes[0].id] = center;
  const others = nodes.slice(1);
  const radius = Math.min(220, 120 + others.length * 10);
  others.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(others.length, 1) - Math.PI / 2;
    positions[node.id] = {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius
    };
  });
  return positions;
}

function buildPathItems(data) {
  const debug = data.debug || {};
  const items = [];

  if (data.mode === 'llm_based') {
    const plan = debug.query_plan || {};
    const subject = plan.subject?.name;
    (debug.graph_results || []).forEach((item, index) => {
      const relation = item.relation_name || item.relation || plan.relation || '关系';
      const color = edgeColor(index, relation);
      if (plan.action === 'query_relation' && subject && item.object) {
        if (plan.direction === 'incoming') {
          items.push({start: item.object, relation, end: subject, color, text: `${item.object} → ${relation} → ${subject}`});
        } else {
          items.push({start: subject, relation, end: item.object, color, text: `${subject} → ${relation} → ${item.object}`});
        }
      } else if (plan.action === 'query_property' && subject) {
        items.push({start: subject, relation: plan.property || '属性', end: stringifyValue(item.value), color, text: `${subject} → ${plan.property || '属性'} → ${stringifyValue(item.value)}`});
      }
    });
  } else {
    (debug.graph_results || []).forEach((item, index) => {
      const start = item['m.name'] || item.subject;
      const relation = item['r.name'] || item.relation_name || item.relation || '关系';
      const end = item['n.name'] || item.value;
      if (!start || !end) return;
      items.push({start, relation, end, color: edgeColor(index, relation), text: `${start} → ${relation} → ${end}`});
    });
  }

  return items.slice(0, 8);
}

function setEmptyState(show) {
  $('graphEmpty').style.display = show ? 'grid' : 'none';
}

function currentView() {
  return state.activeView;
}

function applyView() {
  const graphOn = currentView() === 'graph';
  $('graphViewport').classList.toggle('hidden', !graphOn);
  $('pathView').classList.toggle('hidden', graphOn);
  document.querySelectorAll('.view-tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.view === state.activeView);
  });
}

function updateZoom() {
  $('graphSvg').style.transform = `scale(${state.zoom})`;
}

function zoomBy(delta) {
  state.zoom = Math.max(0.6, Math.min(1.8, +(state.zoom + delta).toFixed(2)));
  updateZoom();
}

function resetState() {
  state.lastResponse = null;
  state.history = [];
  state.zoom = 1;
  state.sessionId = null;
  localStorage.removeItem('kgqa_session_id');
  $('questionInput').value = '';
  $('questionText').textContent = '等待输入问题';
  $('answerView').textContent = '系统将结合当前知识图谱返回结果。';
  $('entitiesJson').textContent = '{}';
  $('planJson').textContent = '{}';
  $('cypherText').textContent = '';
  $('resultsJson').textContent = '[]';
  renderHistory();
  renderEvidence({debug: {graph_results: []}});
  renderPaths({debug: {graph_results: []}});
  renderEntityTags({debug: {}});
  renderGraph({nodes: [], edges: []});
  renderPathView([]);
  setEmptyState(true);
  updateZoom();
}

async function clearSessionAndReset() {
  const current = state.sessionId;
  if (current) {
    try {
      await fetch('/api/session/clear', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: current})
      });
    } catch (error) {
      console.warn('clear session failed', error);
    }
  }
  resetState();
}

function colorForType(type = '', isCenter = false) {
  const map = {
    Disease: '#2d7eff',
    Symptom: '#ff6d7e',
    Drug: '#6aa9ff',
    Food: '#28c2d0',
    Check: '#8f68ff',
    Department: '#38c876',
    Producer: '#ff9f2f',
    Entity: '#4f8bff'
  };
  if (isCenter) return '#2d7eff';
  return map[type] || map.Entity;
}

function glyphForType(type = '', isCenter = false) {
  if (isCenter) return '●';
  const map = {
    Disease: '◉',
    Symptom: '✦',
    Drug: '⚗',
    Food: '◌',
    Check: '▣',
    Department: '◍',
    Producer: '◈',
    Entity: '•'
  };
  return map[type] || map.Entity;
}

function edgeColor(index, seed) {
  const palette = ['#39c772', '#ff9830', '#ff6d7e', '#3b89ff', '#8f68ff', '#28c2d0'];
  let total = index;
  for (const char of String(seed)) total += char.charCodeAt(0);
  return palette[total % palette.length];
}

function svgLine(x1, y1, x2, y2, className) {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', x1);
  line.setAttribute('y1', y1);
  line.setAttribute('x2', x2);
  line.setAttribute('y2', y2);
  line.setAttribute('class', className);
  return line;
}

function svgText(x, y, content, className) {
  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('x', x);
  text.setAttribute('y', y);
  text.setAttribute('class', className);
  text.textContent = content;
  return text;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function stringifyValue(value) {
  if (Array.isArray(value)) return value.join('、');
  if (value === null || value === undefined || value === '') return '暂无';
  return String(value);
}

function formatTime(value) {
  const date = value instanceof Date ? value : new Date(value);
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}

document.querySelectorAll('.examples button').forEach((button) => {
  button.addEventListener('click', () => {
    $('questionInput').value = button.dataset.question;
    sendQuestion(button.dataset.question);
  });
});

document.querySelectorAll('.view-tab').forEach((button) => {
  button.addEventListener('click', () => {
    state.activeView = button.dataset.view;
    applyView();
  });
});

$('sendBtn').addEventListener('click', () => {
  const question = $('questionInput').value.trim();
  if (question) sendQuestion(question);
});

$('questionInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    const question = $('questionInput').value.trim();
    if (question) sendQuestion(question);
  }
});

$('clearBtn').addEventListener('click', clearSessionAndReset);
$('historyToggle').addEventListener('click', () => {
  $('historyPanel').classList.toggle('hidden');
});
$('zoomInBtn').addEventListener('click', () => zoomBy(0.1));
$('zoomOutBtn').addEventListener('click', () => zoomBy(-0.1));
$('resetZoomBtn').addEventListener('click', () => {
  state.zoom = 1;
  updateZoom();
});

$('copyAnswerBtn').addEventListener('click', async () => {
  const text = $('answerView').textContent.trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    $('copyAnswerBtn').textContent = '✓ 已复制';
    setTimeout(() => {
      $('copyAnswerBtn').textContent = '⎘ 复制答案';
    }, 1200);
  } catch (error) {
    $('copyAnswerBtn').textContent = '复制失败';
    setTimeout(() => {
      $('copyAnswerBtn').textContent = '⎘ 复制答案';
    }, 1200);
  }
});

$('favoriteBtn').addEventListener('click', () => {
  $('favoriteBtn').textContent = '★ 已收藏';
  setTimeout(() => {
    $('favoriteBtn').textContent = '☆ 收藏';
  }, 1200);
});

$('exportBtn').addEventListener('click', () => {
  const payload = state.lastResponse || {
    question: $('questionText').textContent,
    answer: $('answerView').textContent
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'kg-qa-result.json';
  link.click();
  URL.revokeObjectURL(url);
});

checkStatus();
applyView();
renderHistory();
renderPathView([]);
renderGraph({nodes: [], edges: []});
setEmptyState(true);
