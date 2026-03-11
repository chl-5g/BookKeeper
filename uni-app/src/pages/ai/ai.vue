<template>
  <view class="page">
    <!-- 功能切换 -->
    <view class="func-tabs">
      <text :class="['func-tab', activeFunc === 'report' && 'func-active']" @click="activeFunc = 'report'">报告</text>
      <text :class="['func-tab', activeFunc === 'profile' && 'func-active']" @click="activeFunc = 'profile'">画像</text>
      <text :class="['func-tab', activeFunc === 'chat' && 'func-active']" @click="activeFunc = 'chat'">问答</text>
      <text :class="['func-tab', activeFunc === 'budget' && 'func-active']" @click="activeFunc = 'budget'">预算</text>
    </view>

    <!-- AI 月度报告 -->
    <view v-if="activeFunc === 'report'" class="card">
      <text class="card-title">AI 月度报告</text>
      <text class="card-desc">{{ currentMonth }} 收支分析与理财建议</text>
      <button class="ai-btn" :disabled="reportLoading" @click="generateReport">
        {{ reportLoading ? '生成中...' : '生成报告' }}
      </button>
      <view v-if="reportText" class="answer-card">
        <text class="answer-text">{{ reportText }}</text>
      </view>
    </view>

    <!-- 消费画像 -->
    <view v-if="activeFunc === 'profile'" class="card">
      <text class="card-title">消费习惯画像</text>
      <text class="card-desc">AI 分析你的消费习惯，给出标签和建议</text>
      <button class="ai-btn" :disabled="profileLoading" @click="generateProfile">
        {{ profileLoading ? '分析中...' : '生成画像' }}
      </button>
      <view v-if="profileText" class="answer-card">
        <text class="answer-text">{{ profileText }}</text>
      </view>
    </view>

    <!-- 账单问答 -->
    <view v-if="activeFunc === 'chat'" class="card">
      <text class="card-title">账单问答</text>
      <text class="card-desc">基于你的收支数据，问任何问题</text>
      <input v-model="chatQuestion" placeholder="如：这个月花最多的是什么？" class="text-input" />
      <button class="ai-btn" :disabled="chatLoading || !chatQuestion.trim()" @click="askChat">
        {{ chatLoading ? '思考中...' : '提问' }}
      </button>
      <view v-if="chatAnswer" class="answer-card">
        <text class="answer-text">{{ chatAnswer }}</text>
      </view>
    </view>

    <!-- 预算助手 -->
    <view v-if="activeFunc === 'budget'" class="card">
      <text class="card-title">预算助手</text>
      <text class="card-desc">设定月度预算，AI 帮你控制开支</text>
      <view class="budget-row">
        <text class="budget-label">{{ currentMonth }} 预算</text>
        <view class="budget-input-wrap">
          <text class="currency">¥</text>
          <input v-model="budgetAmount" type="digit" placeholder="输入预算金额" class="budget-input" />
        </view>
        <button class="set-btn" @click="setBudget" :disabled="!budgetAmount || budgetAmount <= 0">设定</button>
      </view>
      <!-- 预算进度 -->
      <view v-if="budgetInfo.budget" class="budget-progress">
        <view class="progress-header">
          <text>已支出 ¥{{ budgetInfo.expense_total || 0 }}</text>
          <text>预算 ¥{{ budgetInfo.budget }}</text>
        </view>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: progressPct + '%', background: progressPct > 80 ? '#f44336' : '#667eea' }"></view>
        </view>
        <text class="progress-text">剩余 ¥{{ budgetInfo.remaining || 0 }}，已过 {{ budgetInfo.days_passed }}/{{ budgetInfo.days_total }} 天</text>
      </view>
      <button class="ai-btn" :disabled="budgetAdviceLoading || !budgetInfo.budget" @click="getBudgetAdvice">
        {{ budgetAdviceLoading ? '生成中...' : 'AI 预算建议' }}
      </button>
      <view v-if="budgetAdviceText" class="answer-card">
        <text class="answer-text">{{ budgetAdviceText }}</text>
      </view>
    </view>

    <!-- 消费画像 -->
    <view v-if="activeFunc === 'profile'" class="card">
      <text class="card-title">消费习惯画像</text>
      <text class="card-desc">AI 分析你的消费习惯，给出标签和建议</text>
      <button class="ai-btn" :disabled="profileLoading" @click="generateProfile">
        {{ profileLoading ? '分析中...' : '生成画像' }}
      </button>
      <view v-if="profileText" class="answer-card">
        <text class="answer-text">{{ profileText }}</text>
      </view>
    </view>

    <!-- AI 月度报告 -->
    <view class="card">
      <text class="card-title">AI 月度报告</text>
      <text class="card-desc">{{ currentMonth }} 收支分析与理财建议</text>
      <button class="ai-btn" :disabled="reportLoading" @click="generateReport">
        {{ reportLoading ? '生成中...' : '生成报告' }}
      </button>
      <view v-if="reportText" class="answer-card">
        <text class="answer-text">{{ reportText }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { get, post } from '../../utils/api.js'

export default {
  data() {
    const now = new Date()
    return {
      activeFunc: 'report',
      currentMonth: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      // 账单问答
      chatQuestion: '',
      chatAnswer: '',
      chatLoading: false,
      // 预算
      budgetAmount: '',
      budgetInfo: {},
      budgetAdviceText: '',
      budgetAdviceLoading: false,
      // 画像
      profileText: '',
      profileLoading: false,
      // 报告
      reportText: '',
      reportLoading: false,
    }
  },
  computed: {
    progressPct() {
      if (!this.budgetInfo.budget) return 0
      return Math.min(100, ((this.budgetInfo.expense_total || 0) / this.budgetInfo.budget * 100))
    }
  },
  onShow() {
    this.loadBudgetInfo()
  },
  methods: {
    async loadBudgetInfo() {
      try {
        this.budgetInfo = await get(`/api/ai/budget-advice?month=${this.currentMonth}`)
        if (this.budgetInfo.budget) {
          this.budgetAmount = this.budgetInfo.budget
        }
      } catch (e) { /* ignore */ }
    },
    // 账单问答
    async askChat() {
      const q = this.chatQuestion.trim()
      if (!q) return
      this.chatLoading = true
      this.chatAnswer = ''
      try {
        const res = await post('/api/ai/chat', { question: q })
        this.chatAnswer = res.answer || '无法回答'
      } catch (e) { this.chatAnswer = '网络错误' }
      finally { this.chatLoading = false }
    },
    // 预算
    async setBudget() {
      if (!this.budgetAmount || this.budgetAmount <= 0) return
      try {
        await post('/api/budget', { month: this.currentMonth, amount: parseFloat(this.budgetAmount) })
        uni.showToast({ title: '预算已设定', icon: 'success' })
        await this.loadBudgetInfo()
      } catch (e) {
        uni.showToast({ title: '设定失败', icon: 'none' })
      }
    },
    async getBudgetAdvice() {
      this.budgetAdviceLoading = true
      this.budgetAdviceText = ''
      try {
        const res = await get(`/api/ai/budget-advice?month=${this.currentMonth}`)
        this.budgetAdviceText = res.advice || ''
        this.budgetInfo = res
      } catch (e) { this.budgetAdviceText = '获取失败' }
      finally { this.budgetAdviceLoading = false }
    },
    // 画像
    async generateProfile() {
      this.profileLoading = true
      this.profileText = ''
      try {
        const res = await get('/api/ai/profile')
        this.profileText = res.profile || '画像生成失败'
      } catch (e) { this.profileText = '网络错误' }
      finally { this.profileLoading = false }
    },
    // 报告
    async generateReport() {
      this.reportLoading = true
      this.reportText = ''
      try {
        const res = await get(`/api/ai/report?month=${this.currentMonth}`)
        this.reportText = res.report || '报告生成失败'
      } catch (e) { this.reportText = '网络错误' }
      finally { this.reportLoading = false }
    },
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
.func-tabs {
  display: flex;
  background: #fff;
  border-radius: 16rpx;
  padding: 8rpx;
  margin-bottom: 24rpx;
}
.func-tab {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 26rpx;
  color: #666;
  border-radius: 12rpx;
}
.func-active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-weight: bold;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.card-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
  display: block;
}
.card-desc {
  font-size: 24rpx;
  color: #999;
  display: block;
  margin-top: 8rpx;
  margin-bottom: 20rpx;
}
.text-input {
  width: 100%;
  height: 80rpx;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
  margin-bottom: 16rpx;
}
.ai-btn {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 28rpx;
  border-radius: 12rpx;
  border: none;
  margin-top: 8rpx;
}
.ai-btn[disabled] {
  opacity: 0.5;
}
.error-text {
  color: #f44336;
  font-size: 24rpx;
  margin-top: 12rpx;
}
/* Smart add result */
.result-card {
  background: #f8f8ff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-top: 16rpx;
}
.result-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #667eea;
  display: block;
  margin-bottom: 12rpx;
}
.result-row {
  display: flex;
  justify-content: space-between;
  padding: 8rpx 0;
  border-bottom: 1rpx solid #eee;
}
.result-label {
  font-size: 26rpx;
  color: #999;
}
.result-value {
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
/* Answer card */
.answer-card {
  background: #f8f8ff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-top: 16rpx;
}
.answer-text {
  font-size: 26rpx;
  color: #333;
  line-height: 1.8;
}
/* Budget */
.budget-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.budget-label {
  font-size: 26rpx;
  color: #333;
  flex-shrink: 0;
}
.budget-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 16rpx;
  height: 72rpx;
}
.currency {
  font-size: 28rpx;
  color: #999;
  margin-right: 8rpx;
}
.budget-input {
  flex: 1;
  font-size: 28rpx;
}
.set-btn {
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 32rpx;
  background: #667eea;
  color: #fff;
  font-size: 26rpx;
  border-radius: 12rpx;
  border: none;
  flex-shrink: 0;
}
.set-btn[disabled] {
  opacity: 0.5;
}
.budget-progress {
  background: #f8f8ff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  font-size: 24rpx;
  color: #666;
  margin-bottom: 12rpx;
}
.progress-bar {
  height: 16rpx;
  background: #eee;
  border-radius: 8rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 8rpx;
  transition: width 0.3s;
}
.progress-text {
  font-size: 22rpx;
  color: #999;
  margin-top: 8rpx;
  display: block;
}
</style>
