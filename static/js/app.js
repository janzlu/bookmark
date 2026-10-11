/**
 * Bookmark Studio 前端主逻辑与控制器 (支持实时 SSE 流式日志与进度反馈)
 */
document.addEventListener('DOMContentLoaded', () => {
  const state = {
    currentStep: 1,
    status: null,
    summary: null,
    probeResults: { alive: [], dead: [] },
    classifiedPairs: [],
    deadAction: 'archive',
    isProbing: false,
    isClassifying: false
  };

  const elements = {
    chromeBadge: document.getElementById('chrome-status-badge'),
    chromeStatusText: document.getElementById('chrome-status-text'),
    modelBadgeText: document.getElementById('model-text'),
    statTotal: document.getElementById('stat-total'),
    statUnique: document.getElementById('stat-unique'),
    statDuplicate: document.getElementById('stat-duplicate'),
    statBackups: document.getElementById('stat-backups'),
    infoPath: document.getElementById('info-path'),
    infoSize: document.getElementById('info-size'),
    infoChrome: document.getElementById('info-chrome'),
    backupBody: document.getElementById('backup-table-body'),
    btnRunProbe: document.getElementById('btn-run-probe'),
    probeStatusText: document.getElementById('probe-status-text'),
    probeProgressBar: document.getElementById('probe-progress-bar'),
    probePercent: document.getElementById('probe-status-percent'),
    probeLog: document.getElementById('probe-log-box'),
    auditDeadCount: document.getElementById('audit-dead-count'),
    deadLinksBody: document.getElementById('dead-links-body'),
    selectBulkAction: document.getElementById('select-bulk-action'),
    btnRunClassify: document.getElementById('btn-run-classify'),
    classifyStatusText: document.getElementById('classify-status-text'),
    classifyProgressBar: document.getElementById('classify-progress-bar'),
    classifyPercent: document.getElementById('classify-status-percent'),
    classifyLog: document.getElementById('classify-log-box'),
    presetChips: document.getElementById('preset-chips'),
    treeContainer: document.getElementById('tree-preview-container'),
    chromeWarning: document.getElementById('chrome-running-warning'),
    settingsModal: document.getElementById('settings-modal'),
    toastContainer: document.getElementById('toast-container')
  };

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 250);
    }, 3500);
  }

  function setStep(stepNum) {
    state.currentStep = stepNum;
    document.querySelectorAll('.step-item').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.step, 10) === stepNum);
    });
    document.querySelectorAll('.step-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === `panel-step-${stepNum}`);
    });
  }

  function appendLog(box, text, colorClass = '') {
    const line = document.createElement('div');
    line.className = `log-line ${colorClass}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    box.appendChild(line);

    // 限制最大历史输出行数，避免大量节点拖慢页面渲染
    while (box.children.length > 120) {
      box.removeChild(box.firstChild);
    }
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // 1. 初始化系统状态
  async function loadSystemStatus() {
    try {
      const data = await API.getStatus();
      state.status = data;

      if (data.chrome_running) {
        elements.chromeBadge.className = 'status-badge badge-warning';
        elements.chromeStatusText.textContent = 'Chrome 正在运行';
        elements.infoChrome.innerHTML = '<span class="text-warning">⚠️ 运行中 (写入前需退出)</span>';
        elements.chromeWarning.classList.remove('hidden');
      } else {
        elements.chromeBadge.className = 'status-badge badge-success';
        elements.chromeStatusText.textContent = 'Chrome 已退出 (安全)';
        elements.infoChrome.innerHTML = '<span class="text-accent">✓ 已完全退出</span>';
        elements.chromeWarning.classList.add('hidden');
      }

      elements.modelBadgeText.textContent = data.config.model_name || '默认模型';
      elements.infoPath.textContent = data.bookmark_path;
      elements.infoSize.textContent = `${(data.file_size / 1024).toFixed(1)} KB`;
      elements.statBackups.textContent = data.backups.length;

      renderBackups(data.backups);
      renderPresetChips(data.config.preset_categories || []);
    } catch (e) {
      showToast(e.message, 'danger');
    }
  }

  function renderBackups(backups) {
    if (!backups.length) {
      elements.backupBody.innerHTML = '<tr><td colspan="3" class="text-muted">暂无历史备份快照</td></tr>';
      return;
    }
    elements.backupBody.innerHTML = backups.map(b => `
      <tr>
        <td><code>${b.filename}</code></td>
        <td>${b.modified_time}</td>
        <td>
          <button class="btn btn-icon btn-restore" data-file="${b.filename}" title="一秒恢复此备份">
            恢复
          </button>
        </td>
      </tr>
    `).join('');

    elements.backupBody.querySelectorAll('.btn-restore').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const file = e.currentTarget.dataset.file;
        if (!confirm(`确定要从快照 ${file} 恢复书签吗？当前数据将被覆盖。`)) return;
        try {
          await API.restoreBackup(file);
          showToast(`已成功从 ${file} 恢复书签！`, 'success');
          await loadSystemStatus();
          await loadSummary();
        } catch (err) {
          showToast(err.message, 'danger');
        }
      });
    });
  }

  function renderPresetChips(categories) {
    elements.presetChips.innerHTML = categories.map(c => `
      <span class="status-badge badge-info" style="font-size:0.75rem;">${c}</span>
    `).join(' ');
  }

  // 2. 加载书签数据概览
  async function loadSummary() {
    try {
      const sum = await API.getSummary();
      state.summary = sum;
      elements.statTotal.textContent = sum.total_count;
      elements.statUnique.textContent = sum.unique_count;
      elements.statDuplicate.textContent = sum.duplicate_count;
    } catch (e) {
      showToast(e.message, 'danger');
    }
  }

  // 3. 异步流式探活事件绑定
  elements.btnRunProbe.addEventListener('click', async () => {
    if (state.isProbing) return;
    state.isProbing = true;
    elements.btnRunProbe.disabled = true;
    elements.btnRunProbe.textContent = '探活进行中...';

    appendLog(elements.probeLog, '[探活启动] 调度高并发异步非阻塞 HTTP 探活，实时流式接收检测事件...');
    elements.probeProgressBar.style.width = '0%';
    elements.probePercent.textContent = '0%';

    try {
      await API.runProbeStream({}, (event) => {
        if (event.type === 'progress') {
          const percent = Math.round((event.current / event.total) * 100);
          elements.probeProgressBar.style.width = `${percent}%`;
          elements.probePercent.textContent = `${percent}%`;
          elements.probeStatusText.textContent = `正在检测: ${event.current} / ${event.total} (${percent}%)`;

          const colorClass = event.is_alive ? 'text-accent' : 'text-danger';
          const mark = event.is_alive ? '✓ 存活' : '✗ 异常';
          appendLog(elements.probeLog, `[${mark} ${event.reason}] ${event.name} (${event.url})`, colorClass);
        } else if (event.type === 'complete') {
          state.probeResults = { alive: event.alive, dead: event.dead };
          elements.probeProgressBar.style.width = '100%';
          elements.probePercent.textContent = '100%';
          elements.probeStatusText.textContent = `探活全部完成！存活: ${event.alive_count} | 失效: ${event.dead_count}`;
          appendLog(elements.probeLog, `[探活全部完成] 总计扫描: ${event.total_tested} | 存活: ${event.alive_count} | 失效: ${event.dead_count}`, 'text-info');

          renderDeadLinks(event.dead);
          setTimeout(() => setStep(3), 900);
        }
      });
    } catch (e) {
      appendLog(elements.probeLog, `[探活中断报错] ${e.message}`, 'text-danger');
      showToast(e.message, 'danger');
    } finally {
      state.isProbing = false;
      elements.btnRunProbe.disabled = false;
      elements.btnRunProbe.textContent = '重新执行探活';
    }
  });

  function renderDeadLinks(deadList) {
    elements.auditDeadCount.textContent = deadList.length;
    if (!deadList.length) {
      elements.deadLinksBody.innerHTML = '<tr><td colspan="3" class="text-accent">🎉 探活全部通过！未发现失效或死链书签。</td></tr>';
      return;
    }

    elements.deadLinksBody.innerHTML = deadList.map((bm, idx) => `
      <tr>
        <td><span class="status-badge badge-warning">${bm._dead_reason || '未知异常'}</span></td>
        <td><strong>${escapeHtml(bm.name || '(无标题)')}</strong></td>
        <td><code style="font-size:0.78rem;">${escapeHtml(bm.url || '')}</code></td>
      </tr>
    `).join('');
  }

  // 步骤 3 -> 步骤 4
  document.getElementById('btn-next-to-classify').addEventListener('click', () => {
    state.deadAction = elements.selectBulkAction.value;
    setStep(4);
  });

  // 4. 异步流式语义分类事件绑定
  elements.btnRunClassify.addEventListener('click', async () => {
    if (state.isClassifying) return;
    state.isClassifying = true;
    elements.btnRunClassify.disabled = true;
    elements.btnRunClassify.textContent = 'AI 语义分类中...';

    let targets = [...state.probeResults.alive];
    if (state.deadAction === 'keep') {
      targets.push(...state.probeResults.dead);
    }
    if (!targets.length && state.summary) {
      targets = state.summary.items;
    }

    appendLog(elements.classifyLog, `[分类启动] 开始对 ${targets.length} 条书签进行大模型语义聚类...`);
    elements.classifyProgressBar.style.width = '0%';
    elements.classifyPercent.textContent = '0%';

    try {
      await API.runClassifyStream({ bookmarks: targets }, (event) => {
        if (event.type === 'progress') {
          const percent = Math.round((event.current / event.total) * 100);
          elements.classifyProgressBar.style.width = `${percent}%`;
          elements.classifyPercent.textContent = `${percent}%`;
          elements.classifyStatusText.textContent = `正在分类: ${event.current} / ${event.total} (${percent}%)`;

          for (const item of event.batch_items) {
            appendLog(elements.classifyLog, `🤖 [分类规划] ${item.name} -> ${item.category}`, 'text-accent');
          }
        } else if (event.type === 'complete') {
          state.classifiedPairs = event.classified;
          elements.classifyProgressBar.style.width = '100%';
          elements.classifyPercent.textContent = '100%';
          elements.classifyStatusText.textContent = `分类完成！构建了 ${event.classified.length} 个分类映射。`;
          appendLog(elements.classifyLog, `[分类完成] 成功完成全量分类规划。`, 'text-info');

          renderTreePreview(event.classified, state.probeResults.dead, state.deadAction);
          setTimeout(() => setStep(5), 900);
        }
      });
    } catch (e) {
      appendLog(elements.classifyLog, `[分类异常报错] ${e.message}`, 'text-danger');
      showToast(e.message, 'danger');
    } finally {
      state.isClassifying = false;
      elements.btnRunClassify.disabled = false;
      elements.btnRunClassify.textContent = '重新执行语义分类';
    }
  });

  // 5. 目录树渲染
  function renderTreePreview(classified, deadList, deadAction) {
    const tree = {};

    classified.forEach(item => {
      const cat = item.category || '其他/待整理';
      if (!tree[cat]) tree[cat] = [];
      tree[cat].push(item.bookmark);
    });

    if (deadAction === 'archive' && deadList && deadList.length) {
      tree['⚠️ 失效书签归档'] = deadList;
    }

    elements.treeContainer.innerHTML = Object.keys(tree).map(catPath => {
      const items = tree[catPath];
      return `
        <div class="tree-folder">
          <div class="tree-folder-title">
            <span>📁</span>
            <span>${catPath}</span>
            <span class="stat-desc">(${items.length} 项)</span>
          </div>
          <div class="tree-children">
            ${items.slice(0, 8).map(bm => `
              <div class="tree-item">
                <span>🔗</span>
                <span>${escapeHtml(bm.name || '(无标题)')}</span>
              </div>
            `).join('')}
            ${items.length > 8 ? `<div class="tree-item text-muted">... 以及另外 ${items.length - 8} 项</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // 步骤 5 -> 步骤 6
  document.getElementById('btn-goto-save').addEventListener('click', () => {
    setStep(6);
  });

  // 6. 原子覆写提交
  document.getElementById('btn-commit-apply').addEventListener('click', async () => {
    if (state.status && state.status.chrome_running) {
      alert('检测到 Google Chrome 仍在运行！请彻底退出 Chrome（如 macOS 终端执行 killall "Google Chrome"）后再点击确认保存！');
      return;
    }

    try {
      const res = await API.applyReconstruction({
        classified: state.classifiedPairs,
        dead: state.probeResults.dead,
        dead_action: state.deadAction
      });

      showToast(`🎉 整理完成！已安全生成 ${res.folder_count} 个分类文件夹`, 'success');
      alert(`书签全流程整理完成并已安全原子写入！\n备份文件: ${res.backup_path}\n重新打开 Chrome 即可查验全新书签栏。`);
      await loadSystemStatus();
      setStep(1);
    } catch (e) {
      showToast(e.message, 'danger');
    }
  });

  // 导航绑定
  document.querySelectorAll('.step-item').forEach(btn => {
    btn.addEventListener('click', () => setStep(parseInt(btn.dataset.step, 10)));
  });
  document.getElementById('btn-start-probe-step').addEventListener('click', () => setStep(2));

  // 设置弹窗绑定
  document.getElementById('btn-open-settings').addEventListener('click', () => {
    if (state.status && state.status.config) {
      const cfg = state.status.config;
      document.getElementById('cfg-api-key').value = cfg.api_key || '';
      document.getElementById('cfg-base-url').value = cfg.base_url || '';
      document.getElementById('cfg-model-name').value = cfg.model_name || '';
      document.getElementById('cfg-concurrency').value = cfg.max_concurrency || 30;
      document.getElementById('cfg-timeout').value = cfg.timeout_seconds || 7;
    }
    elements.settingsModal.classList.remove('hidden');
  });

  document.getElementById('btn-close-settings').addEventListener('click', () => {
    elements.settingsModal.classList.add('hidden');
  });

  document.getElementById('btn-save-settings').addEventListener('click', async () => {
    const payload = {
      api_key: document.getElementById('cfg-api-key').value.trim(),
      base_url: document.getElementById('cfg-base-url').value.trim(),
      model_name: document.getElementById('cfg-model-name').value.trim(),
      max_concurrency: parseInt(document.getElementById('cfg-concurrency').value, 10),
      timeout_seconds: parseFloat(document.getElementById('cfg-timeout').value)
    };
    try {
      await API.updateConfig(payload);
      showToast('配置已保存！', 'success');
      elements.settingsModal.classList.add('hidden');
      await loadSystemStatus();
    } catch (e) {
      showToast(e.message, 'danger');
    }
  });

  // 初始化加载
  loadSystemStatus();
  loadSummary();
});
