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

  async runProbe(payload = {}) {
    const res = await fetch('/api/prober/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || '探活执行失败');
    }
    return await res.json();
  },

  async runClassify(payload = {}) {
    const res = await fetch('/api/classifier/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || '分类执行失败');
    }
    return await res.json();
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
