/**
 * Bookmark Studio 前端 API 交互客户端
 */
const API = {
  async getStatus() {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error(`获取状态失败: ${res.statusText}`);
    return await res.json();
  },

  async getSummary() {
    const res = await fetch('/api/bookmarks/summary');
    if (!res.ok) throw new Error(`获取书签概览失败: ${res.statusText}`);
    return await res.json();
  },

  async streamSSE(url, payload, onEvent) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || `请求失败: ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        const trimmed = block.trim();
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim();
          if (jsonStr) {
            try {
              const data = JSON.parse(jsonStr);
              onEvent(data);
            } catch (e) {
              console.warn('SSE parse error:', e);
            }
          }
        }
      }
    }
  },

  async runProbeStream(payload, onEvent) {
    return this.streamSSE('/api/prober/stream', payload, onEvent);
  },

  async runClassifyStream(payload, onEvent) {
    return this.streamSSE('/api/classifier/stream', payload, onEvent);
  },

  async applyReconstruction(payload) {
    const res = await fetch('/api/pipeline/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || '覆写持久化失败');
    }
    return await res.json();
  },

  async restoreBackup(filename) {
    const res = await fetch('/api/backups/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || '快照恢复失败');
    }
    return await res.json();
  },

  async updateConfig(config) {
    const res = await fetch('/api/config/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error('配置更新失败');
    return await res.json();
  }
};
