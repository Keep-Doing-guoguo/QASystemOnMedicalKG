const state = {
  lastResponse: null,
  history: []
};

const $ = (id) => document.getElementById(id);

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('bad status');
    $('apiStatus').textContent = 'API 已连接';
    $('apiStatus').className = 'status-dot ok';
  } catch (error) {
    $('apiStatus').textContent = 'API 未连接';
    $('apiStatus').className = 'status-dot error';
  }
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

async function sendQuestion(question) {
  const mode = currentMode();
  const endpoint = mode === 'llm' ? '/api/llm/chat' : '/api/rule/chat';
  $('answerView').textContent = '查询中...';

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '请求失败');
    state.lastResponse = data;
    state.history.unshift({question, mode, data});
    state.history = state.history.slice(0, 8);
    renderResponse(data);
    renderHistory();
  } catch (error) {
    $('answerView').textContent = `请求失败：${error.message}`;
  }
}

function renderResponse(data) {
  $('answerView').textContent = data.answer || '当前知识图谱中没有查到相关信息。';
  renderDebug(data);
  renderGraph(data.graph || {nodes: [], edges: []});
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

function renderHistory() {
  const list = $('historyList');
  list.innerHTML = '';
  state.history.forEach((item, index) => {
    const btn = document.createElement('button');
    btn.className = 'history-item';
    btn.innerHTML = `<strong>${escapeHtml(item.question)}</strong><span>${item.mode === 'llm' ? 'LLM 通道' : '规则匹配'}</span>`;
    btn.addEventListener('click', () => {
      document.querySelector(`input[name="mode"][value="${item.mode}"]`).checked = true;
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
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#8da1b2"></path>
      </marker>
    </defs>
  `;

  if (!nodes.length) {
    const text = svgText(450, 280, '暂无可视化子图', 'node-label');
    text.setAttribute('text-anchor', 'middle');
    svg.appendChild(text);
    return;
  }

  const positions = layoutNodes(nodes);
  edges.forEach((edge) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return;
    svg.appendChild(svgLine(source.x, source.y, target.x, target.y, 'edge'));
    const label = svgText((source.x + target.x) / 2, (source.y + target.y) / 2 - 8, edge.label || edge.type || '关系', 'edge-label');
    label.setAttribute('text-anchor', 'middle');
    svg.appendChild(label);
  });

  nodes.forEach((node) => {
    const pos = positions[node.id];
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', pos.x);
    circle.setAttribute('cy', pos.y);
    circle.setAttribute('r', node.id === nodes[0].id ? 40 : 32);
    circle.setAttribute('fill', colorForType(node.type));
    circle.setAttribute('class', 'node');
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${node.label} (${node.type || 'Entity'})`;
    circle.appendChild(title);
    group.appendChild(circle);

    const label = svgText(pos.x, pos.y + 54, node.label, 'node-label');
    label.setAttribute('text-anchor', 'middle');
    group.appendChild(label);
    svg.appendChild(group);
  });
}

function layoutNodes(nodes) {
  const positions = {};
  const center = {x: 450, y: 280};
  positions[nodes[0].id] = center;
  const others = nodes.slice(1);
  const radius = Math.min(210, 90 + others.length * 10);
  others.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(others.length, 1) - Math.PI / 2;
    positions[node.id] = {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius
    };
  });
  return positions;
}

function colorForType(type = '') {
  const map = {
    Disease: '#d95f5f',
    Symptom: '#e89a3c',
    Drug: '#4f83cc',
    Food: '#5aa76c',
    Check: '#8c6ccf',
    Department: '#35a7a0',
    Producer: '#8c97a3',
    Entity: '#6d8fb3'
  };
  return map[type] || map.Entity;
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

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}

document.querySelectorAll('.tab').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((content) => content.classList.remove('active'));
    button.classList.add('active');
    $(`tab-${button.dataset.tab}`).classList.add('active');
  });
});

document.querySelectorAll('.examples button').forEach((button) => {
  button.addEventListener('click', () => {
    $('questionInput').value = button.dataset.question;
    sendQuestion(button.dataset.question);
  });
});

$('sendBtn').addEventListener('click', () => {
  const question = $('questionInput').value.trim();
  if (question) sendQuestion(question);
});

$('questionInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    const question = $('questionInput').value.trim();
    if (question) sendQuestion(question);
  }
});

$('clearBtn').addEventListener('click', () => {
  state.lastResponse = null;
  state.history = [];
  $('questionInput').value = '';
  $('answerView').textContent = '等待输入问题。';
  $('entitiesJson').textContent = '{}';
  $('planJson').textContent = '{}';
  $('cypherText').textContent = '';
  $('resultsJson').textContent = '[]';
  renderHistory();
  renderGraph({nodes: [], edges: []});
});

checkStatus();
renderGraph({nodes: [], edges: []});
