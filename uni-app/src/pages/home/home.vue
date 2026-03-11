<template>
  <view class="page">
    <!-- 月份选择 + 概览 -->
    <view class="header-card">
      <view class="month-row">
        <text class="arrow" @click="changeMonth(-1)">&lt;</text>
        <text class="month-text">{{ currentMonth }}</text>
        <text class="arrow" @click="changeMonth(1)">&gt;</text>
      </view>
      <view class="overview">
        <view class="ov-item">
          <text class="ov-label">收入</text>
          <text class="ov-amount income">+{{ stats.income_total || 0 }}</text>
        </view>
        <view class="ov-divider"></view>
        <view class="ov-item">
          <text class="ov-label">支出</text>
          <text class="ov-amount expense">-{{ stats.expense_total || 0 }}</text>
        </view>
        <view class="ov-divider"></view>
        <view class="ov-item">
          <text class="ov-label">结余</text>
          <text class="ov-amount">{{ ((stats.income_total || 0) - (stats.expense_total || 0)).toFixed(2) }}</text>
        </view>
      </view>
    </view>

    <!-- AI 功能说明 -->
    <view class="ai-banner" v-if="showAiBanner" @click="showAiBanner = false">
      <view class="ai-icon-wrap">
        <text class="ai-icon">AI</text>
      </view>
      <view class="ai-text-wrap">
        <text class="ai-title">AI 智能分类</text>
        <text class="ai-desc">记账时输入备注，AI 大模型（qwen3:14b）自动识别消费类型，如"星巴克拿铁"自动归类为"餐饮"，省去手动选择分类的麻烦。</text>
      </view>
      <text class="ai-close">x</text>
    </view>

    <!-- 记录列表 -->
    <view class="records-section">
      <text class="section-title">交易记录</text>
      <view v-if="records.length === 0" class="empty-tip">
        <text>本月暂无记录</text>
      </view>
      <view v-for="item in records" :key="item.id" class="record-item" @longpress="confirmDelete(item.id)">
        <view class="record-left">
          <text class="record-cat">{{ item.category }}</text>
          <text class="record-note">{{ item.note || '-' }}</text>
        </view>
        <view class="record-right">
          <text :class="['record-amount', item.type === 'income' ? 'income' : 'expense']">
            {{ item.type === 'income' ? '+' : '-' }}{{ item.amount }}
          </text>
          <text class="record-date">{{ item.date }}</text>
        </view>
      </view>
    </view>

    <!-- 用户信息 + 退出 -->
    <view class="user-bar">
      <text class="user-name">{{ username }}</text>
      <text class="logout-btn" @click="logout">退出登录</text>
    </view>
  </view>
</template>

<script>
import { get, post } from '../../utils/api.js'
import { getUser, clearAuth } from '../../utils/auth.js'

export default {
  data() {
    const now = new Date()
    return {
      currentMonth: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      records: [],
      stats: {},
      username: '',
      showAiBanner: true,
    }
  },
  onShow() {
    this.username = getUser()
    this.loadData()
  },
  methods: {
    async loadData() {
      try {
        const [records, stats] = await Promise.all([
          get(`/api/records?month=${this.currentMonth}`),
          get(`/api/stats/monthly?month=${this.currentMonth}`),
        ])
        this.records = records
        this.stats = stats
      } catch (e) {
        console.error('loadData', e)
      }
    },
    changeMonth(delta) {
      const [y, m] = this.currentMonth.split('-').map(Number)
      const d = new Date(y, m - 1 + delta, 1)
      this.currentMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      this.loadData()
    },
    confirmDelete(id) {
      uni.showModal({
        title: '确认删除',
        content: '确定要删除这条记录吗？',
        success: async (res) => {
          if (res.confirm) {
            const { del } = require('../../utils/api.js')
            await del(`/api/records/${id}`)
            this.loadData()
          }
        }
      })
    },
    logout() {
      uni.showModal({
        title: '退出登录',
        content: '确定要退出吗？',
        success: async (res) => {
          if (res.confirm) {
            await post('/api/logout')
            clearAuth()
            uni.reLaunch({ url: '/pages/login/login' })
          }
        }
      })
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}
.header-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 32rpx 32rpx 40rpx;
  color: #fff;
}
.month-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40rpx;
  margin-bottom: 24rpx;
}
.arrow {
  font-size: 36rpx;
  padding: 8rpx 16rpx;
}
.month-text {
  font-size: 32rpx;
  font-weight: bold;
}
.overview {
  display: flex;
  justify-content: space-around;
  align-items: center;
}
.ov-item {
  text-align: center;
}
.ov-label {
  font-size: 24rpx;
  opacity: 0.8;
  display: block;
}
.ov-amount {
  font-size: 36rpx;
  font-weight: bold;
  display: block;
  margin-top: 8rpx;
}
.ov-divider {
  width: 2rpx;
  height: 60rpx;
  background: rgba(255,255,255,0.3);
}
/* AI banner */
.ai-banner {
  margin: 20rpx 24rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.06);
  position: relative;
}
.ai-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ai-icon {
  color: #fff;
  font-size: 24rpx;
  font-weight: bold;
}
.ai-text-wrap {
  flex: 1;
}
.ai-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
}
.ai-desc {
  font-size: 24rpx;
  color: #666;
  line-height: 1.6;
  margin-top: 8rpx;
  display: block;
}
.ai-close {
  position: absolute;
  top: 16rpx;
  right: 20rpx;
  font-size: 28rpx;
  color: #ccc;
}
/* Records */
.records-section {
  padding: 24rpx;
}
.section-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 16rpx;
  display: block;
}
.empty-tip {
  text-align: center;
  padding: 80rpx 0;
  color: #999;
  font-size: 28rpx;
}
.record-item {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.record-left {
  flex: 1;
}
.record-cat {
  font-size: 28rpx;
  color: #333;
  font-weight: 500;
  display: block;
}
.record-note {
  font-size: 24rpx;
  color: #999;
  margin-top: 6rpx;
  display: block;
}
.record-right {
  text-align: right;
}
.record-amount {
  font-size: 32rpx;
  font-weight: bold;
  display: block;
}
.record-date {
  font-size: 22rpx;
  color: #bbb;
  margin-top: 6rpx;
  display: block;
}
.income { color: #4CAF50; }
.expense { color: #f44336; }
/* User bar */
.user-bar {
  margin: 40rpx 24rpx 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx;
  background: #fff;
  border-radius: 12rpx;
}
.user-name {
  font-size: 28rpx;
  color: #333;
}
.logout-btn {
  font-size: 26rpx;
  color: #f44336;
}
</style>
