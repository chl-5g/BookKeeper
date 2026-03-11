<template>
  <view class="page">
    <!-- 月份选择 -->
    <view class="month-row">
      <text class="arrow" @click="changeMonth(-1)">&lt;</text>
      <text class="month-text">{{ currentMonth }}</text>
      <text class="arrow" @click="changeMonth(1)">&gt;</text>
    </view>

    <!-- 支出分类饼图 -->
    <view class="chart-card">
      <text class="chart-title">支出分类</text>
      <view v-if="expenseCategories.length === 0" class="empty-tip">
        <text>本月暂无支出</text>
      </view>
      <view v-else>
        <canvas canvas-id="pieChart" id="pieChart" class="pie-canvas" @click="onPieTap"></canvas>
        <view class="legend">
          <view v-for="(item, i) in expenseCategories" :key="i" class="legend-item">
            <view class="legend-dot" :style="{ background: redShades[i % redShades.length] }"></view>
            <text class="legend-name">{{ item.category }}</text>
            <text class="legend-amount">{{ item.amount }}</text>
            <text class="legend-pct">{{ ((item.amount / expenseTotal) * 100).toFixed(1) }}%</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 收入分类 -->
    <view class="chart-card" v-if="incomeCategories.length > 0">
      <text class="chart-title">收入分类</text>
      <view class="legend">
        <view v-for="(item, i) in incomeCategories" :key="i" class="legend-item">
          <view class="legend-dot" :style="{ background: greenShades[i % greenShades.length] }"></view>
          <text class="legend-name">{{ item.category }}</text>
          <text class="legend-amount">+{{ item.amount }}</text>
        </view>
      </view>
    </view>

    <!-- 趋势图 -->
    <view class="chart-card">
      <text class="chart-title">收支趋势（近6个月）</text>
      <view v-if="trendData.length === 0" class="empty-tip">
        <text>暂无数据</text>
      </view>
      <canvas v-else canvas-id="trendChart" id="trendChart" class="trend-canvas"></canvas>
      <view v-if="trendData.length > 0" class="trend-legend">
        <view class="trend-legend-item">
          <view class="legend-dot" style="background: #4CAF50"></view>
          <text>收入</text>
        </view>
        <view class="trend-legend-item">
          <view class="legend-dot" style="background: #f44336"></view>
          <text>支出</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { get } from '../../utils/api.js'

const RED_SHADES = ['#f44336', '#e53935', '#d32f2f', '#c62828', '#b71c1c', '#ff5252', '#ff1744', '#ef5350', '#e57373', '#ef9a9a']
const GREEN_SHADES = ['#4CAF50', '#43A047', '#388E3C', '#2E7D32', '#1B5E20', '#66BB6A', '#81C784', '#A5D6A7', '#69F0AE', '#00E676']

export default {
  data() {
    const now = new Date()
    return {
      currentMonth: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      expenseCategories: [],
      incomeCategories: [],
      expenseTotal: 0,
      trendData: [],
      redShades: RED_SHADES,
      greenShades: GREEN_SHADES,
    }
  },
  onShow() {
    this.loadData()
  },
  methods: {
    async loadData() {
      try {
        const [stats, trend] = await Promise.all([
          get(`/api/stats/monthly?month=${this.currentMonth}`),
          get('/api/stats/trend?months=6'),
        ])
        this.expenseCategories = stats.expense_categories || []
        this.incomeCategories = stats.income_categories || []
        this.expenseTotal = stats.expense_total || 0
        this.trendData = trend || []

        this.$nextTick(() => {
          if (this.expenseCategories.length > 0) this.drawPie()
          if (this.trendData.length > 0) this.drawTrend()
        })
      } catch (e) {
        console.error(e)
      }
    },
    changeMonth(delta) {
      const [y, m] = this.currentMonth.split('-').map(Number)
      const d = new Date(y, m - 1 + delta, 1)
      this.currentMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      this.loadData()
    },
    drawPie() {
      const ctx = uni.createCanvasContext('pieChart', this)
      const cx = 150, cy = 110, r = 80
      let startAngle = -Math.PI / 2
      const total = this.expenseTotal

      this.expenseCategories.forEach((item, i) => {
        const sliceAngle = (item.amount / total) * Math.PI * 2
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.arc(cx, cy, r, startAngle, startAngle + sliceAngle)
        ctx.closePath()
        ctx.setFillStyle(RED_SHADES[i % RED_SHADES.length])
        ctx.fill()
        startAngle += sliceAngle
      })
      ctx.draw()
    },
    drawTrend() {
      const ctx = uni.createCanvasContext('trendChart', this)
      const data = this.trendData
      const W = 340, H = 180
      const padL = 50, padR = 20, padT = 20, padB = 40
      const chartW = W - padL - padR
      const chartH = H - padT - padB

      // Find max
      let maxVal = 0
      data.forEach(d => {
        if (d.income > maxVal) maxVal = d.income
        if (d.expense > maxVal) maxVal = d.expense
      })
      if (maxVal === 0) maxVal = 100

      // Grid lines
      ctx.setStrokeStyle('#eee')
      ctx.setLineWidth(1)
      for (let i = 0; i <= 4; i++) {
        const y = padT + chartH * (1 - i / 4)
        ctx.beginPath()
        ctx.moveTo(padL, y)
        ctx.lineTo(W - padR, y)
        ctx.stroke()
        // Y label
        ctx.setFillStyle('#999')
        ctx.setFontSize(10)
        ctx.setTextAlign('right')
        ctx.fillText(Math.round(maxVal * i / 4), padL - 6, y + 4)
      }

      // X labels
      ctx.setTextAlign('center')
      ctx.setFillStyle('#999')
      ctx.setFontSize(10)
      data.forEach((d, i) => {
        const x = padL + (i / Math.max(data.length - 1, 1)) * chartW
        ctx.fillText(d.month.slice(5), x, H - 8)
      })

      // Draw lines
      function drawLine(key, color) {
        ctx.beginPath()
        ctx.setStrokeStyle(color)
        ctx.setLineWidth(2)
        data.forEach((d, i) => {
          const x = padL + (i / Math.max(data.length - 1, 1)) * chartW
          const y = padT + chartH * (1 - d[key] / maxVal)
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        })
        ctx.stroke()
        // Dots
        data.forEach((d, i) => {
          const x = padL + (i / Math.max(data.length - 1, 1)) * chartW
          const y = padT + chartH * (1 - d[key] / maxVal)
          ctx.beginPath()
          ctx.arc(x, y, 3, 0, Math.PI * 2)
          ctx.setFillStyle(color)
          ctx.fill()
        })
      }

      drawLine('income', '#4CAF50')
      drawLine('expense', '#f44336')
      ctx.draw()
    },
    onPieTap() {
      // Could show detail popup, skip for now
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
  color: #667eea;
}
.month-text {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.chart-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.chart-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 16rpx;
}
.pie-canvas {
  width: 300px;
  height: 220px;
  margin: 0 auto;
}
.trend-canvas {
  width: 340px;
  height: 180px;
  margin: 0 auto;
}
.empty-tip {
  text-align: center;
  padding: 40rpx;
  color: #999;
  font-size: 28rpx;
}
/* Legend */
.legend {
  margin-top: 16rpx;
}
.legend-item {
  display: flex;
  align-items: center;
  padding: 8rpx 0;
  gap: 12rpx;
}
.legend-dot {
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-name {
  font-size: 26rpx;
  color: #333;
  flex: 1;
}
.legend-amount {
  font-size: 26rpx;
  color: #333;
  font-weight: 500;
}
.legend-pct {
  font-size: 24rpx;
  color: #999;
  width: 80rpx;
  text-align: right;
}
.trend-legend {
  display: flex;
  justify-content: center;
  gap: 40rpx;
  margin-top: 12rpx;
}
.trend-legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 24rpx;
  color: #666;
}
</style>
