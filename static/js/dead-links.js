/**
 * Bookmark Studio - 失效书签审计、批量处置与人工安全核验模块
 */
const DeadLinksModule = {
  items: [],
  filter: 'all',
  manualVerified: false,
  modalCandidates: [],
  elements: null,
  showToast: null,

  init(el, showToastFn) {
    this.elements = el;
    this.showToast = showToastFn;
    this.bindEvents();
  },

  setItems(rawDeadList) {
    this.items = (rawDeadList || []).map((b, idx) => ({
      ...b,
      _idx: idx,
      _action: 'archive',
      _checked: false
    }));
    this.manualVerified = false;
    this.render();
  },

  getArchived() {
    return this.items.filter(b => b._action === 'archive');
  },

  getDeleted() {
    return this.items.filter(b => b._action === 'delete');
  },

  getKept() {
    return this.items.filter(b => b._action === 'keep');
  },

  isVerified() {
    return this.manualVerified;
  },

  getFilteredItems() {
    return this.items.filter(b => {
      const reason = (b._dead_reason || '').toLowerCase();
      if (this.filter === 'all') return true;
      if (this.filter === '404') return reason.includes('404') || reason.startsWith('4');
      if (this.filter === 'timeout') return reason.includes('超时') || reason.includes('timeout') || reason.includes('连接失败');
      if (this.filter === 'ssl') return reason.includes('ssl') || reason.includes('证书');
      if (this.filter === 'delete') return b._action === 'delete';
      return true;
    });
  },

  updateBadges() {
    const el = this.elements;
    const total = this.items.length;
    if (el.auditDeadCount) el.auditDeadCount.textContent = total;

    const cntArchived = this.getArchived().length;
    const cntDeleted = this.getDeleted().length;
    const cntKept = this.getKept().length;

    if (el.badgeArchivedCount) el.badgeArchivedCount.textContent = cntArchived;
    if (el.badgeDeletedCount) el.badgeDeletedCount.textContent = cntDeleted;
    if (el.badgeKeptCount) el.badgeKeptCount.textContent = cntKept;

    const cnt404 = this.items.filter(b => (b._dead_reason || '').includes('404') || (b._dead_reason || '').startsWith('4')).length;
    const cntTimeout = this.items.filter(b => (b._dead_reason || '').includes('超时') || (b._dead_reason || '').toLowerCase().includes('timeout') || (b._dead_reason || '').includes('连接失败')).length;
    const cntSsl = this.items.filter(b => (b._dead_reason || '').toLowerCase().includes('ssl') || (b._dead_reason || '').includes('证书')).length;

    if (el.filterCntAll) el.filterCntAll.textContent = total;
    if (el.filterCnt404) el.filterCnt404.textContent = cnt404;
    if (el.filterCntTimeout) el.filterCntTimeout.textContent = cntTimeout;
    if (el.filterCntSsl) el.filterCntSsl.textContent = cntSsl;
    if (el.filterCntDelete) el.filterCntDelete.textContent = cntDeleted;

    const visibleItems = this.getFilteredItems();
    const checkedCount = visibleItems.filter(b => b._checked).length;
    if (el.selectedDeadCount) el.selectedDeadCount.textContent = checkedCount;

    const allChecked = visibleItems.length > 0 && checkedCount === visibleItems.length;
    if (el.selectAllDead) el.selectAllDead.checked = allChecked;
    if (el.tableHeadCheckbox) el.tableHeadCheckbox.checked = allChecked;
  },

  render() {
    this.updateBadges();
    const el = this.elements;
    const visibleList = this.getFilteredItems();

    if (!this.items.length) {
      el.deadLinksBody.innerHTML = '<tr><td colspan="5" class="text-accent text-center">🎉 探活全部通过！未发现失效或死链书签。</td></tr>';
      return;
    }

    if (!visibleList.length) {
      el.deadLinksBody.innerHTML = '<tr><td colspan="5" class="text-muted text-center">当前筛选标签下无匹配书签</td></tr>';
      return;
    }

    el.deadLinksBody.innerHTML = visibleList.map(bm => {
      const isDel = bm._action === 'delete';
      const isArch = bm._action === 'archive';
      const badgeCls = isDel ? 'badge-danger' : (isArch ? 'badge-warning' : 'badge-accent');

      return `
        <tr data-idx="${bm._idx}">
          <td style="text-align: center;">
            <input type="checkbox" class="dead-row-cb" data-idx="${bm._idx}" ${bm._checked ? 'checked' : ''}>
          </td>
          <td>
            <span class="status-badge ${badgeCls}">${this.escapeHtml(bm._dead_reason || '异常')}</span>
          </td>
          <td><strong>${this.escapeHtml(bm.name || '(无标题)')}</strong></td>
          <td>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <code style="font-size:0.78rem; word-break: break-all;">${this.escapeHtml(bm.url || '')}</code>
              <a href="${this.escapeHtml(bm.url || '#')}" target="_blank" rel="noopener noreferrer" class="link-test-btn" title="在新标签页测试">
                测试 ↗
              </a>
            </div>
          </td>
          <td>
            <select class="action-select dead-action-select" data-idx="${bm._idx}">
              <option value="archive" ${bm._action === 'archive' ? 'selected' : ''}>📦 自动归档</option>
              <option value="delete" ${bm._action === 'delete' ? 'selected' : ''}>🗑️ 彻底删除 (需核验)</option>
              <option value="keep" ${bm._action === 'keep' ? 'selected' : ''}>保留并归类</option>
            </select>
          </td>
        </tr>
      `;
    }).join('');

    el.deadLinksBody.querySelectorAll('.dead-row-cb').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        const item = this.items.find(b => b._idx === idx);
        if (item) item._checked = e.target.checked;
        this.updateBadges();
      });
    });

    el.deadLinksBody.querySelectorAll('.dead-action-select').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        const item = this.items.find(b => b._idx === idx);
        if (!item) return;
        const val = e.target.value;
        if (val === 'delete') {
          this.openVerifyModal([item]);
        } else {
          item._action = val;
          this.render();
        }
      });
    });
  },

  openVerifyModal(candidates) {
    const el = this.elements;
    if (!candidates || !candidates.length) {
      if (this.showToast) this.showToast('未选择任何待删除书签', 'warning');
      return;
    }
    this.modalCandidates = candidates.map(item => ({ item, checked: true }));
    this.renderModalList();
    el.chkManualVerifiedConfirm.checked = false;
    el.btnModalConfirmDelete.disabled = true;
    el.batchDeleteModal.classList.remove('hidden');
  },

  renderModalList() {
    const el = this.elements;
    const list = this.modalCandidates;
    const selectedCount = list.filter(c => c.checked).length;
    el.modalDeleteCount.textContent = list.length;
    el.modalConfirmBtnCount.textContent = selectedCount;
    el.modalSelectAll.checked = selectedCount === list.length && list.length > 0;

    el.modalDeleteListBody.innerHTML = list.map((c, i) => `
      <tr>
        <td style="text-align: center;">
          <input type="checkbox" class="modal-item-cb" data-i="${i}" ${c.checked ? 'checked' : ''}>
        </td>
        <td><span class="status-badge badge-warning">${this.escapeHtml(c.item._dead_reason || '异常')}</span></td>
        <td><strong>${this.escapeHtml(c.item.name || '(无标题)')}</strong></td>
        <td>
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <code style="font-size:0.75rem; word-break:break-all;">${this.escapeHtml(c.item.url || '')}</code>
            <a href="${this.escapeHtml(c.item.url || '#')}" target="_blank" rel="noopener noreferrer" class="link-test-btn">测试 ↗</a>
          </div>
        </td>
      </tr>
    `).join('');

    el.modalDeleteListBody.querySelectorAll('.modal-item-cb').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const i = parseInt(e.target.dataset.i, 10);
        if (this.modalCandidates[i]) {
          this.modalCandidates[i].checked = e.target.checked;
          const selCount = this.modalCandidates.filter(x => x.checked).length;
          el.modalConfirmBtnCount.textContent = selCount;
          el.modalSelectAll.checked = selCount === this.modalCandidates.length;
          this.updateModalConfirmBtnState();
        }
      });
    });
  },

  updateModalConfirmBtnState() {
    const el = this.elements;
    const selCount = this.modalCandidates.filter(x => x.checked).length;
    el.btnModalConfirmDelete.disabled = !(el.chkManualVerifiedConfirm.checked && selCount > 0);
  },

  bindEvents() {
    const el = this.elements;

    el.modalSelectAll.addEventListener('change', (e) => {
      this.modalCandidates.forEach(c => c.checked = e.target.checked);
      this.renderModalList();
      this.updateModalConfirmBtnState();
    });

    el.chkManualVerifiedConfirm.addEventListener('change', () => {
      this.updateModalConfirmBtnState();
    });

    el.btnModalConfirmDelete.addEventListener('click', () => {
      const confirmed = this.modalCandidates.filter(c => c.checked).map(c => c.item);
      if (!confirmed.length) {
        if (this.showToast) this.showToast('请至少选择一项待物理删除的书签', 'warning');
        return;
      }
      confirmed.forEach(item => { item._action = 'delete'; item._checked = false; });
      this.modalCandidates.filter(c => !c.checked).forEach(c => {
        if (c.item._action === 'delete') c.item._action = 'archive';
      });

      this.manualVerified = true;
      el.batchDeleteModal.classList.add('hidden');
      this.render();
      if (this.showToast) this.showToast(`人工核验通过！已标记 ${confirmed.length} 项彻底物理删除`, 'danger');
    });

    el.btnModalDowngradeArchive.addEventListener('click', () => {
      this.modalCandidates.forEach(c => {
        c.item._action = 'archive';
        c.item._checked = false;
      });
      el.batchDeleteModal.classList.add('hidden');
      this.render();
      if (this.showToast) this.showToast('已安全降级为自动归档模式', 'success');
    });

    const closeModal = () => {
      el.batchDeleteModal.classList.add('hidden');
      this.render();
    };
    el.btnModalCancel.addEventListener('click', closeModal);
    el.btnCloseDeleteModal.addEventListener('click', closeModal);

    // 批量工具栏
    el.selectAllDead.addEventListener('change', (e) => {
      const visible = this.getFilteredItems();
      visible.forEach(b => b._checked = e.target.checked);
      if (el.tableHeadCheckbox) el.tableHeadCheckbox.checked = e.target.checked;
      this.render();
    });

    if (el.tableHeadCheckbox) {
      el.tableHeadCheckbox.addEventListener('change', (e) => {
        const visible = this.getFilteredItems();
        visible.forEach(b => b._checked = e.target.checked);
        el.selectAllDead.checked = e.target.checked;
        this.render();
      });
    }

    el.btnBatchDelete.addEventListener('click', () => {
      let targets = this.items.filter(b => b._checked);
      if (!targets.length) targets = this.getFilteredItems();
      if (!targets.length) {
        if (this.showToast) this.showToast('当前没有可操作的失效书签', 'warning');
        return;
      }
      this.openVerifyModal(targets);
    });

    el.btnBatchArchive.addEventListener('click', () => {
      let targets = this.items.filter(b => b._checked);
      if (!targets.length) targets = this.getFilteredItems();
      if (!targets.length) return;
      targets.forEach(b => { b._action = 'archive'; b._checked = false; });
      this.render();
      if (this.showToast) this.showToast(`已批量设为安全归档: ${targets.length} 项`, 'success');
    });

    el.btnBatchKeep.addEventListener('click', () => {
      let targets = this.items.filter(b => b._checked);
      if (!targets.length) targets = this.getFilteredItems();
      if (!targets.length) return;
      targets.forEach(b => { b._action = 'keep'; b._checked = false; });
      this.render();
      if (this.showToast) this.showToast(`已批量设为保留归类: ${targets.length} 项`, 'info');
    });

    el.deadFilterChips.querySelectorAll('.filter-chip').forEach(btn => {
      btn.addEventListener('click', (e) => {
        el.deadFilterChips.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.filter = e.currentTarget.dataset.filter;
        this.render();
      });
    });
  },

  escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
};
