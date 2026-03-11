<template>
  <view class="page">
    <!-- 智能记账 -->
    <view class="section smart-section">
      <text class="section-title">智能记账</text>
      <text class="smart-desc">输入一句话，AI 自动解析金额、分类和日期</text>
      <view class="smart-row">
        <input v-model="smartText" placeholder="如：昨天打车花了30元" class="smart-input" />
        <button class="smart-btn" :disabled="smartLoading || !smartText.trim()" @click="smartAdd">
          {{ smartLoading ? '...' : '解析' }}
        </button>
      </view>
      <view v-if="smartError" class="smart-error">{{ smartError }}</view>
      <view v-if="smartResult" class="smart-result">
        <view class="result-row"><text class="rl">类型</text><text class="rv">{{ smartResult.type === 'income' ? '收入' : '支出' }}</text></view>
        <view class="result-row"><text class="rl">金额</text><text class="rv">¥{{ smartResult.amount }}</text></view>
        <view class="result-row"><text class="rl">分类</text><text class="rv">{{ smartResult.category }}</text></view>
        <view class="result-row"><text class="rl">备注</text><text class="rv">{{ smartResult.note }}</text></view>
        <view class="result-row"><text class="rl">日期</text><text class="rv">{{ smartResult.date }}</text></view>
        <button class="confirm-btn" @click="confirmSmartAdd">确认入账</button>
      </view>
    </view>

    <!-- 收入/支出切换 -->
    <view class="type-switch">
      <text :class="['type-btn', form.type === 'expense' && 'active-expense']" @click="form.type = 'expense'">支出</text>
      <text :class="['type-btn', form.type === 'income' && 'active-income']" @click="form.type = 'income'">收入</text>
    </view>

    <!-- 金额 -->
    <view class="amount-card">
      <text class="currency">&#xa5;</text>
      <input v-model="form.amount" type="digit" placeholder="0.00" class="amount-input" />
    </view>

    <!-- 分类选择 -->
    <view class="section">
      <text class="section-title">分类</text>
      <view class="cat-grid">
        <view
          v-for="cat in filteredCategories"
          :key="cat.id"
          :class="['cat-item', form.category === cat.name && 'cat-active']"
          @click="form.category = cat.name"
        >
          <text class="cat-icon">{{ cat.icon }}</text>
          <text class="cat-name">{{ cat.name }}</text>
        </view>
      </view>
    </view>

    <!-- 备注 + AI 分类 -->
    <view class="section">
      <text class="section-title">备注</text>
      <view class="note-row">
        <input v-model="form.note" placeholder="输入备注，AI 自动识别分类" class="note-input" @blur="aiClassify" />
      </view>
      <view v-if="aiHint" class="ai-hint">
        <text>AI 建议分类：</text>
        <text class="ai-hint-cat" @click="form.category = aiHint">{{ aiHint }}</text>
      </view>
    </view>

    <!-- 日期 -->
    <view class="section">
      <text class="section-title">日期</text>
      <picker mode="date" :value="form.date" @change="form.date = $event.detail.value">
        <view class="date-picker">{{ form.date }}</view>
      </picker>
    </view>

    <!-- 提交按钮 -->
    <button class="save-btn" :disabled="!canSubmit" @click="submitRecord">保存</button>

    <!-- 导入区域 -->
    <view class="import-section">
      <view class="import-header">
        <text class="section-title">导入账单</text>
        <text class="guide-link" @click="showGuide = !showGuide">{{ showGuide ? '收起' : '导入指南' }}</text>
      </view>

      <!-- 导入指南 -->
      <view v-if="showGuide" class="guide-card">
        <text class="guide-title">如何导入账单文件？</text>

        <text class="guide-subtitle">支付宝：</text>
        <text class="guide-step">1. 打开支付宝 → 我的 → 账单</text>
        <text class="guide-step">2. 点击右上角「...」→ 开具交易流水证明</text>
        <text class="guide-step">3. 选择时间范围 → 用于个人对账</text>
        <text class="guide-step">4. 申请后会发到邮箱，下载 CSV 文件</text>

        <text class="guide-subtitle">微信：</text>
        <text class="guide-step">1. 微信 → 我 → 服务 → 钱包</text>
        <text class="guide-step">2. 点击右上角「账单」→ 常见问题</text>
        <text class="guide-step">3. 选择「下载账单」→ 用于个人对账</text>
        <text class="guide-step">4. 选择时间范围，发送到邮箱后下载</text>

        <text class="guide-note">支持格式：CSV、Excel（xlsx/xls）</text>
      </view>

      <button class="import-btn" @click="chooseFile">选择账单文件</button>

      <view v-if="importResult" class="import-result">
        <text v-if="importResult.error" class="error-text">{{ importResult.error }}</text>
        <text v-else class="success-text">
          导入成功！来源：{{ importResult.source === 'alipay' ? '支付宝' : '微信' }}，
          导入 {{ importResult.imported }} 条，跳过 {{ importResult.skipped }} 条
        </text>
      </view>
    </view>
  </view>
</template>

<script>
import { get, post, uploadFile } from '../../utils/api.js'

export default {
  data() {
    const now = new Date()
    return {
      form: {
        type: 'expense',
        amount: '',
        category: '',
        note: '',
        date: now.toISOString().slice(0, 10),
      },
      categories: [],
      aiHint: '',
      showGuide: false,
      importResult: null,
      smartText: '',
      smartResult: null,
      smartError: '',
      smartLoading: false,
    }
  },
  computed: {
    filteredCategories() {
      return this.categories.filter(c => c.type === this.form.type)
    },
    canSubmit() {
      return this.form.amount > 0 && this.form.category && this.form.date
    }
  },
  onShow() {
    this.loadCategories()
  },
  methods: {
    async smartAdd() {
      const t = this.smartText.trim()
      if (!t) return
      this.smartLoading = true; this.smartError = ''; this.smartResult = null
      try {
        const res = await post('/api/ai/smart-add', { text: t })
        if (res.error) this.smartError = res.error
        else if (res.parsed) this.smartResult = res.parsed
      } catch (e) { this.smartError = '解析失败' }
      finally { this.smartLoading = false }
    },
    async confirmSmartAdd() {
      if (!this.smartResult) return
      try {
        await post('/api/ai/smart-add/confirm', this.smartResult)
        uni.showToast({ title: '入账成功', icon: 'success' })
        this.smartResult = null; this.smartText = ''
        uni.switchTab({ url: '/pages/home/home' })
      } catch (e) {
        uni.showToast({ title: '入账失败', icon: 'none' })
      }
    },
    async loadCategories() {
      try {
        this.categories = await get('/api/categories')
      } catch (e) {
        console.error(e)
      }
    },
    async aiClassify() {
      const note = (this.form.note || '').trim()
      if (!note) return
      try {
        const res = await post('/api/ai/classify', { note })
        if (res.category && res.category !== '其他') {
          this.aiHint = res.category
          if (!this.form.category) {
            this.form.category = res.category
          }
        }
      } catch (e) { /* ignore */ }
    },
    async submitRecord() {
      if (!this.canSubmit) return
      try {
        await post('/api/records', {
          ...this.form,
          amount: parseFloat(this.form.amount),
        })
        uni.showToast({ title: '保存成功', icon: 'success' })
        this.form.amount = ''
        this.form.note = ''
        this.form.category = ''
        this.aiHint = ''
        uni.switchTab({ url: '/pages/home/home' })
      } catch (e) {
        uni.showToast({ title: '保存失败', icon: 'none' })
      }
    },
    chooseFile() {
      // #ifdef MP-WEIXIN
      uni.chooseMessageFile({
        count: 1,
        type: 'file',
        extension: ['csv', 'xlsx', 'xls'],
        success: (res) => {
          this.doImport(res.tempFiles[0].path)
        }
      })
      // #endif
      // #ifdef H5
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.csv,.xlsx,.xls'
      input.onchange = (e) => {
        const file = e.target.files[0]
        if (file) this.doImportH5(file)
      }
      input.click()
      // #endif
      // #ifdef APP-PLUS
      uni.chooseFile({
        count: 1,
        extension: ['.csv', '.xlsx', '.xls'],
        success: (res) => {
          this.doImport(res.tempFilePaths[0])
        }
      })
      // #endif
    },
    async doImport(filePath) {
      this.importResult = null
      try {
        const res = await uploadFile('/api/import', filePath)
        this.importResult = res
      } catch (e) {
        this.importResult = { error: '导入失败：' + e.message }
      }
    },
    doImportH5(file) {
      // H5 使用 fetch 上传
      this.importResult = null
      const formData = new FormData()
      formData.append('file', file)
      const { getToken } = require('../../utils/auth.js')
      const { BASE_URL } = require('../../utils/config.js')
      const token = getToken()
      const headers = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      fetch(BASE_URL + '/api/import', {
        method: 'POST',
        body: formData,
        headers,
      })
        .then(r => r.json())
        .then(data => { this.importResult = data })
        .catch(e => { this.importResult = { error: '导入失败' } })
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
  padding-bottom: 140rpx;
}
.type-switch {
  display: flex;
  justify-content: center;
  gap: 32rpx;
  margin-bottom: 24rpx;
}
.type-btn {
  font-size: 30rpx;
  color: #999;
  padding: 12rpx 48rpx;
  border-radius: 40rpx;
  background: #fff;
}
.active-expense {
  background: #f44336;
  color: #fff;
}
.active-income {
  background: #4CAF50;
  color: #fff;
}
.amount-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}
.currency {
  font-size: 48rpx;
  color: #333;
  margin-right: 16rpx;
}
.amount-input {
  flex: 1;
  font-size: 56rpx;
  font-weight: bold;
  color: #333;
}
.section {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.section-title {
  font-size: 26rpx;
  color: #999;
  margin-bottom: 16rpx;
  display: block;
}
.cat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.cat-item {
  width: 140rpx;
  text-align: center;
  padding: 16rpx 0;
  border-radius: 12rpx;
  border: 2rpx solid #eee;
}
.cat-active {
  border-color: #667eea;
  background: rgba(102,126,234,0.08);
}
.cat-icon {
  font-size: 36rpx;
  display: block;
}
.cat-name {
  font-size: 22rpx;
  color: #666;
  display: block;
  margin-top: 4rpx;
}
.note-row {
  display: flex;
  align-items: center;
}
.note-input {
  flex: 1;
  height: 72rpx;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
}
.ai-hint {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #999;
}
.ai-hint-cat {
  color: #667eea;
  font-weight: bold;
  text-decoration: underline;
}
.date-picker {
  height: 72rpx;
  line-height: 72rpx;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  color: #333;
}
.save-btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 32rpx;
  border-radius: 12rpx;
  border: none;
  margin-bottom: 40rpx;
}
.save-btn[disabled] {
  opacity: 0.5;
}
/* Import section */
.import-section {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
}
.import-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.guide-link {
  font-size: 24rpx;
  color: #667eea;
}
.guide-card {
  background: #f8f8ff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.guide-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 16rpx;
}
.guide-subtitle {
  font-size: 26rpx;
  font-weight: bold;
  color: #667eea;
  display: block;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
}
.guide-step {
  font-size: 24rpx;
  color: #666;
  line-height: 1.8;
  display: block;
  padding-left: 16rpx;
}
.guide-note {
  font-size: 24rpx;
  color: #999;
  display: block;
  margin-top: 16rpx;
  font-style: italic;
}
.import-btn {
  height: 72rpx;
  line-height: 72rpx;
  background: #fff;
  color: #667eea;
  border: 2rpx solid #667eea;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.import-result {
  margin-top: 16rpx;
}
.error-text {
  color: #f44336;
  font-size: 24rpx;
}
.success-text {
  color: #4CAF50;
  font-size: 24rpx;
}
/* Smart add */
.smart-section {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.smart-desc {
  font-size: 24rpx;
  color: #888;
  display: block;
  margin-bottom: 16rpx;
}
.smart-row {
  display: flex;
  gap: 12rpx;
}
.smart-input {
  flex: 1;
  height: 72rpx;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
}
.smart-btn {
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 32rpx;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 26rpx;
  border-radius: 12rpx;
  border: none;
}
.smart-btn[disabled] {
  opacity: 0.5;
}
.smart-error {
  color: #f44336;
  font-size: 24rpx;
  margin-top: 12rpx;
}
.smart-result {
  background: #f8f8ff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-top: 16rpx;
}
.result-row {
  display: flex;
  justify-content: space-between;
  padding: 8rpx 0;
  border-bottom: 1rpx solid #eee;
}
.rl {
  font-size: 26rpx;
  color: #999;
}
.rv {
  font-size: 26rpx;
  color: #333;
  font-weight: 500;
}
.confirm-btn {
  width: 100%;
  height: 72rpx;
  line-height: 72rpx;
  background: #4CAF50;
  color: #fff;
  font-size: 28rpx;
  border-radius: 12rpx;
  border: none;
  margin-top: 16rpx;
}
</style>
