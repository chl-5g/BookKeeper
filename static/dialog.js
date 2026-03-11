/**
 * 智小账 - 通用对话框控件
 * 直接操作 DOM，不受 Vue 容器 max-width 限制
 *
 * 用法：
 *   const { dialog, showConfirm, showAlert } = useDialog();
 *   await showConfirm({ title: '删除', message: '确定？', type: 'danger' });
 *   await showAlert({ title: '提示', message: '操作成功' });
 */

// 空 Vue 组件（仅占位，实际渲染由 useDialog 的原生 DOM 完成）
const DialogComponent = {
    name: 'AppDialog',
    props: { modelValue: Object },
    template: '<!-- dialog rendered natively -->',
};

function useDialog() {
    let overlayEl = null;

    let _escHandler = null;

    function _createOverlay({ title, message, type, confirmText, alertOnly, onConfirm, onCancel }) {
        _removeOverlay();

        const icon = type === 'danger' ? '⚠️' : type === 'success' ? '✅' : '❓';
        const iconClass = type;
        const btnClass = 'btn-' + type;

        overlayEl = document.createElement('div');
        overlayEl.className = 'dialog-overlay';
        overlayEl.innerHTML = `
            <div class="dialog-box">
                <div class="dialog-body">
                    <div class="dialog-icon ${iconClass}">${icon}</div>
                    <div class="dialog-title">${_esc(title)}</div>
                    <div class="dialog-msg">${_esc(message)}</div>
                </div>
                <div class="dialog-actions">
                    ${alertOnly ? '' : '<button class="dialog-cancel-btn">取消</button>'}
                    <button class="dialog-confirm-btn ${btnClass}">${_esc(confirmText)}</button>
                </div>
            </div>
        `;

        // 点击遮罩取消
        overlayEl.addEventListener('click', e => { if (e.target === overlayEl) onCancel(); });
        // 取消按钮
        const cancelBtn = overlayEl.querySelector('.dialog-cancel-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', onCancel);
        // 确认按钮
        overlayEl.querySelector('.dialog-confirm-btn').addEventListener('click', onConfirm);

        // ESC 键关闭
        _escHandler = e => { if (e.key === 'Escape') onCancel(); };
        document.addEventListener('keydown', _escHandler);

        // 锁定背景滚动
        document.body.style.overflow = 'hidden';

        document.documentElement.appendChild(overlayEl);
    }

    function _removeOverlay() {
        if (_escHandler) {
            document.removeEventListener('keydown', _escHandler);
            _escHandler = null;
        }
        document.body.style.overflow = '';
        if (overlayEl && overlayEl.parentNode) {
            overlayEl.parentNode.removeChild(overlayEl);
            overlayEl = null;
        }
    }

    function _esc(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    // Vue reactive state (for <app-dialog> component compatibility, though unused)
    const dialog = Vue.reactive({ show: false });

    function showConfirm({ title, message, type = 'primary', confirmText = '确定' }) {
        return new Promise(resolve => {
            _createOverlay({
                title, message, type, confirmText, alertOnly: false,
                onConfirm: () => { _removeOverlay(); resolve(true); },
                onCancel: () => { _removeOverlay(); resolve(false); },
            });
        });
    }

    function showAlert({ title, message, type = 'primary', confirmText = '知道了' }) {
        return new Promise(resolve => {
            _createOverlay({
                title, message, type, confirmText, alertOnly: true,
                onConfirm: () => { _removeOverlay(); resolve(); },
                onCancel: () => { _removeOverlay(); resolve(); },
            });
        });
    }

    return { dialog, showConfirm, showAlert };
}
