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
        const reportText = ref('');
        const reportLoading = ref(false);
        const profileText = ref('');
        const profileLoading = ref(false);
        const alerts = ref([]);
        const budgetInfo = ref({});
        const budgetAmount = ref(null);
        const budgetAdviceText = ref('');
        const budgetAdviceLoading = ref(false);
        const smartText = ref('');
        const smartResult = ref(null);
        const smartError = ref('');
        const smartLoading = ref(false);
        const chatQuestion = ref('');
        const chatAnswer = ref('');
        const chatLoading = ref(false);
        const classifyText = ref('');
        const classifyResult = ref('');
        const classifyLoading = ref(false);

        // 分页
        const currentPage = ref(1);
        const pageSize = 10;

        const now = new Date();
        const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`);

        const form = ref({
            type: 'expense',
            amount: null,
            category: '',
            note: '',
            date: now.toISOString().slice(0, 10),
        });

        const pageTitle = computed(() => ({ home: '智小账', add: '记一笔', stats: '统计', ai: 'AI' }[tab.value]));

        const totalPages = computed(() => Math.max(1, Math.ceil(records.value.length / pageSize)));
        const pagedRecords = computed(() => {
            const start = (currentPage.value - 1) * pageSize;
            return records.value.slice(start, start + pageSize);
        });

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
            currentPage.value = 1;
        }

        async function loadStats() {
            stats.value = await api('GET', `/api/stats/monthly?month=${currentMonth.value}`);
        }

        async function loadTrend() {
            trendData.value = await api('GET', '/api/stats/trend?months=6');
        }

        async function loadAlerts() {
            try { alerts.value = (await api('GET', `/api/ai/alerts?month=${currentMonth.value}`)).alerts || []; } catch(e) { alerts.value = []; }
        }

        async function loadBudgetInfo() {
            try { budgetInfo.value = await api('GET', `/api/ai/budget-advice?month=${currentMonth.value}`); } catch(e) { budgetInfo.value = {}; }
        }

        async function loadAll() {
            await Promise.all([loadRecords(), loadStats(), loadTrend(), loadAlerts(), loadBudgetInfo()]);
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

        async function doClassify() {
            const text = classifyText.value.trim();
            if (!text) return;
            classifyLoading.value = true; classifyResult.value = '';
            try {
                const res = await api('POST', '/api/ai/classify', { note: text });
                classifyResult.value = res.category || '无法识别';
            } catch (e) { classifyResult.value = '识别失败'; }
            finally { classifyLoading.value = false; }
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

        // AI Report
        async function generateReport() {
            reportLoading.value = true;
            reportText.value = '';
            try {
                const res = await api('GET', `/api/ai/report?month=${currentMonth.value}`);
                reportText.value = res.report || '报告生成失败';
            } catch (e) {
                reportText.value = '网络错误，请稍后重试';
            } finally {
                reportLoading.value = false;
            }
        }

        function renderMarkdown(text) {
            return text
                .replace(/### (.+)/g, '<h4 style="color:#667eea;margin:12px 0 6px;">$1</h4>')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>');
        }

        // 消费画像
        async function generateProfile() {
            profileLoading.value = true;
            profileText.value = '';
            try {
                const res = await api('GET', '/api/ai/profile');
                profileText.value = res.profile || '画像生成失败';
            } catch (e) { profileText.value = '网络错误'; }
            finally { profileLoading.value = false; }
        }

        // 智能记账
        async function smartAdd() {
            const t = smartText.value.trim();
            if (!t) return;
            smartLoading.value = true; smartError.value = ''; smartResult.value = null;
            try {
                const res = await api('POST', '/api/ai/smart-add', { text: t });
                if (res.error) { smartError.value = res.error; }
                else if (res.parsed) { smartResult.value = res.parsed; }
            } catch (e) { smartError.value = '解析失败'; }
            finally { smartLoading.value = false; }
        }
        async function confirmSmartAdd() {
            if (!smartResult.value) return;
            await api('POST', '/api/ai/smart-add/confirm', smartResult.value);
            smartResult.value = null; smartText.value = '';
            await loadAll();
        }

        // 账单问答
        async function askChat() {
            const q = chatQuestion.value.trim();
            if (!q) return;
            chatLoading.value = true; chatAnswer.value = '';
            try {
                const res = await api('POST', '/api/ai/chat', { question: q });
                chatAnswer.value = res.answer || '无法回答';
            } catch (e) { chatAnswer.value = '网络错误'; }
            finally { chatLoading.value = false; }
        }

        // 预算
        async function setBudget() {
            if (!budgetAmount.value || budgetAmount.value <= 0) return;
            await api('POST', '/api/budget', { month: currentMonth.value, amount: budgetAmount.value });
            await loadBudgetInfo();
        }
        async function getBudgetAdvice() {
            budgetAdviceLoading.value = true; budgetAdviceText.value = '';
            try {
                const res = await api('GET', `/api/ai/budget-advice?month=${currentMonth.value}`);
                budgetAdviceText.value = res.advice || '';
                budgetInfo.value = res;
            } catch (e) { budgetAdviceText.value = '获取失败'; }
            finally { budgetAdviceLoading.value = false; }
        }

        // Clear all records
        async function clearAllRecords() {
            if (!confirm('确定要清空所有收支记录吗？此操作不可撤销！')) return;
            if (!confirm('再次确认：删除后无法恢复，确定清空？')) return;
            try {
                await api('DELETE', '/api/records/all');
                await loadAll();
            } catch (e) { /* ignore */ }
        }

        // Charts
        // 支出：深色调（暗红/酒红/深橙等）
        const EXPENSE_COLORS = ['#c62828', '#ad1457', '#6a1b9a', '#4527a0', '#283593', '#bf360c', '#e65100', '#d84315', '#8e2c1a', '#880e4f'];
        // 收入：浅色调（浅绿/浅蓝/浅紫等）
        const INCOME_COLORS = ['#81C784', '#80CBC4', '#80DEEA', '#90CAF9', '#CE93D8', '#A5D6A7', '#B2DFDB', '#B3E5FC', '#C5CAE9', '#F0F4C3'];
        let pieChart = null;
        let incomePieChart = null;
        let trendChart = null;

        function renderPieChart() {
            const el = document.getElementById('pie-chart');
            if (!el) return;
            if (!pieChart) pieChart = echarts.init(el);
            const data = stats.value.expense_categories.map((c, i) => ({
                name: c.category, value: c.amount,
                itemStyle: { color: EXPENSE_COLORS[i % EXPENSE_COLORS.length] }
            }));
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

        function renderIncomePieChart() {
            const el = document.getElementById('income-pie-chart');
            if (!el) return;
            if (!incomePieChart) incomePieChart = echarts.init(el);
            const data = stats.value.income_categories.map((c, i) => ({
                name: c.category, value: c.amount,
                itemStyle: { color: INCOME_COLORS[i % INCOME_COLORS.length] }
            }));
            incomePieChart.setOption({
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
                nextTick(() => { renderPieChart(); renderIncomePieChart(); renderTrendChart(); });
            }
        }

        // Watchers
        watch(currentMonth, () => { loadAll().then(() => { if (tab.value === 'stats') nextTick(() => { renderPieChart(); renderIncomePieChart(); renderTrendChart(); }); }); });
        watch(() => stats.value, () => { if (tab.value === 'stats') nextTick(() => { renderPieChart(); renderIncomePieChart(); }); }, { deep: true });
        watch(() => trendData.value, () => { if (tab.value === 'stats') nextTick(renderTrendChart); }, { deep: true });

        onMounted(() => { checkAuth(); });

        return {
            user, authMode, authForm, authError, submitAuth, doLogout,
            tab, records, categories, stats, trendData, form, aiHint, importResult,
            reportText, reportLoading, generateReport, renderMarkdown,
            profileText, profileLoading, generateProfile,
            alerts, budgetInfo, budgetAmount, budgetAdviceText, budgetAdviceLoading,
            setBudget, getBudgetAdvice,
            smartText, smartResult, smartError, smartLoading, smartAdd, confirmSmartAdd,
            chatQuestion, chatAnswer, chatLoading, askChat,
            classifyText, classifyResult, classifyLoading, doClassify,
            currentMonth, currentPage, totalPages, pagedRecords,
            pageTitle, filteredCategories, canSubmit,
            getCatIcon, submitRecord, deleteRecord, aiClassify, importCSV,
            changeMonth, switchTab, clearAllRecords,
        };
    }
}).mount('#app');
