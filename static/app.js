const { createApp, ref, computed, watch, onMounted, nextTick } = Vue;

createApp({
    setup() {
        // Auth state
        const user = ref(null);
        const authMode = ref('login');
        const authForm = ref({ username: '', password: '' });
        const authError = ref('');

        // App state
        const tab = ref('home');
        const records = ref([]);
        const categories = ref([]);
        const stats = ref({ income_total: 0, expense_total: 0, income_categories: [], expense_categories: [] });
        const trendData = ref([]);
        const aiHint = ref('');
        const importResult = ref(null);

        const now = new Date();
        const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`);

        const form = ref({
            type: 'expense',
            amount: null,
            category: '',
            note: '',
            date: now.toISOString().slice(0, 10),
        });

        const pageTitle = computed(() => ({ home: '智小账', add: '记一笔', stats: '统计' }[tab.value]));

        const filteredCategories = computed(() =>
            categories.value.filter(c => c.type === form.value.type)
        );

        const canSubmit = computed(() =>
            form.value.amount > 0 && form.value.category && form.value.date
        );

        const catIconMap = {};
        function getCatIcon(name) {
            return catIconMap[name] || '📦';
        }

        // API helpers
        async function api(method, path, body) {
            const opts = { method, headers: { 'Content-Type': 'application/json' } };
            if (body) opts.body = JSON.stringify(body);
            const res = await fetch(path, opts);
            return res.json();
        }

        // Auth
        async function checkAuth() {
            try {
                const res = await fetch('/api/user');
                if (res.ok) {
                    const data = await res.json();
                    user.value = data.username;
                    await loadCategories();
                    await loadAll();
                }
            } catch (e) { /* not logged in */ }
        }

        async function submitAuth() {
            authError.value = '';
            const url = authMode.value === 'login' ? '/api/login' : '/api/register';
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(authForm.value),
                });
                const data = await res.json();
                if (data.error) {
                    authError.value = data.error;
                } else {
                    user.value = data.username;
                    authForm.value = { username: '', password: '' };
                    await loadCategories();
                    await loadAll();
                }
            } catch (e) {
                authError.value = '网络错误';
            }
        }

        async function doLogout() {
            await api('POST', '/api/logout');
            user.value = null;
            records.value = [];
            stats.value = { income_total: 0, expense_total: 0, income_categories: [], expense_categories: [] };
            trendData.value = [];
            tab.value = 'home';
        }

        // Data loading
        async function loadCategories() {
            categories.value = await api('GET', '/api/categories');
            categories.value.forEach(c => { catIconMap[c.name] = c.icon; });
        }

        async function loadRecords() {
            records.value = await api('GET', `/api/records?month=${currentMonth.value}`);
        }

        async function loadStats() {
            stats.value = await api('GET', `/api/stats/monthly?month=${currentMonth.value}`);
        }

        async function loadTrend() {
            trendData.value = await api('GET', '/api/stats/trend?months=6');
        }

        async function loadAll() {
            await Promise.all([loadRecords(), loadStats(), loadTrend()]);
        }

        // Actions
        async function submitRecord() {
            if (!canSubmit.value) return;
            await api('POST', '/api/records', form.value);
            form.value.amount = null;
            form.value.note = '';
            form.value.category = '';
            aiHint.value = '';
            await loadAll();
            tab.value = 'home';
        }

        async function deleteRecord(id) {
            if (!confirm('确定删除？')) return;
            await api('DELETE', `/api/records/${id}`);
            await loadAll();
        }

        async function aiClassify() {
            const note = form.value.note.trim();
            if (!note) return;
            aiHint.value = '';
            try {
                const res = await api('POST', '/api/ai/classify', { note });
                if (res.category && res.category !== '其他') {
                    aiHint.value = res.category;
                    if (!form.value.category) {
                        form.value.category = res.category;
                    }
                }
            } catch (e) { /* ignore */ }
        }

        async function importCSV(event) {
            const file = event.target.files[0];
            if (!file) return;
            importResult.value = null;
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch('/api/import', { method: 'POST', body: formData });
                importResult.value = await res.json();
                if (!importResult.value.error) {
                    await loadAll();
                }
            } catch (e) {
                importResult.value = { error: '导入失败：' + e.message };
            }
            event.target.value = '';
        }

        function changeMonth(delta) {
            const [y, m] = currentMonth.value.split('-').map(Number);
            const d = new Date(y, m - 1 + delta, 1);
            currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
        }

        // Charts
        let pieChart = null;
        let trendChart = null;

        function renderPieChart() {
            const el = document.getElementById('pie-chart');
            if (!el) return;
            if (!pieChart) pieChart = echarts.init(el);
            const data = stats.value.expense_categories.map(c => ({ name: c.category, value: c.amount }));
            pieChart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
                series: [{
                    type: 'pie',
                    radius: ['35%', '65%'],
                    label: { formatter: '{b}\n¥{c}', fontSize: 11 },
                    data: data.length ? data : [{ name: '暂无数据', value: 0 }],
                }],
            });
        }

        function renderTrendChart() {
            const el = document.getElementById('trend-chart');
            if (!el) return;
            if (!trendChart) trendChart = echarts.init(el);
            const months = trendData.value.map(d => d.month);
            trendChart.setOption({
                tooltip: { trigger: 'axis' },
                legend: { data: ['收入', '支出'], bottom: 0 },
                grid: { top: 10, right: 16, bottom: 36, left: 50 },
                xAxis: { type: 'category', data: months },
                yAxis: { type: 'value' },
                series: [
                    { name: '收入', type: 'line', data: trendData.value.map(d => d.income), smooth: true, itemStyle: { color: '#4CAF50' } },
                    { name: '支出', type: 'line', data: trendData.value.map(d => d.expense), smooth: true, itemStyle: { color: '#f44336' } },
                ],
            });
        }

        function switchTab(t) {
            tab.value = t;
            if (t === 'stats') {
                nextTick(() => { renderPieChart(); renderTrendChart(); });
            }
        }

        // Watchers
        watch(currentMonth, () => { loadAll().then(() => { if (tab.value === 'stats') nextTick(() => { renderPieChart(); renderTrendChart(); }); }); });
        watch(() => stats.value, () => { if (tab.value === 'stats') nextTick(renderPieChart); }, { deep: true });
        watch(() => trendData.value, () => { if (tab.value === 'stats') nextTick(renderTrendChart); }, { deep: true });

        onMounted(() => { checkAuth(); });

        return {
            user, authMode, authForm, authError, submitAuth, doLogout,
            tab, records, categories, stats, trendData, form, aiHint, importResult,
            currentMonth, pageTitle, filteredCategories, canSubmit,
            getCatIcon, submitRecord, deleteRecord, aiClassify, importCSV,
            changeMonth, switchTab,
        };
    }
}).mount('#app');
