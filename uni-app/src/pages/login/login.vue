<template>
  <view class="login-page">
    <view class="logo-area">
      <text class="app-name">记账本</text>
      <text class="app-desc">AI 智能分类 · 轻松管理收支</text>
    </view>

    <view class="form-card">
      <view class="tab-bar">
        <text :class="['tab-item', mode === 'login' && 'active']" @click="mode = 'login'">登录</text>
        <text :class="['tab-item', mode === 'register' && 'active']" @click="mode = 'register'">注册</text>
      </view>

      <view class="input-group">
        <input v-model="username" placeholder="用户名" class="input" />
      </view>
      <view class="input-group">
        <input v-model="password" placeholder="密码" type="password" class="input" />
      </view>

      <text v-if="error" class="error-text">{{ error }}</text>

      <button class="submit-btn" :loading="loading" @click="submit">
        {{ mode === 'login' ? '登录' : '注册' }}
      </button>
    </view>
  </view>
</template>

<script>
import { post } from '../../utils/api.js'
import { setToken, setUser } from '../../utils/auth.js'

export default {
  data() {
    return {
      mode: 'login',
      username: '',
      password: '',
      error: '',
      loading: false,
    }
  },
  methods: {
    async submit() {
      if (!this.username || !this.password) {
        this.error = '请填写用户名和密码'
        return
      }
      if (this.mode === 'register' && this.password.length < 4) {
        this.error = '密码至少4位'
        return
      }
      this.error = ''
      this.loading = true
      try {
        const url = this.mode === 'login' ? '/api/login' : '/api/register'
        const res = await post(url, {
          username: this.username,
          password: this.password,
        })
        if (res.error) {
          this.error = res.error
        } else {
          setToken(res.token)
          setUser(res.username)
          uni.switchTab({ url: '/pages/home/home' })
        }
      } catch (e) {
        this.error = '网络错误，请检查连接'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 180rpx;
}
.logo-area {
  text-align: center;
  margin-bottom: 80rpx;
}
.app-name {
  font-size: 56rpx;
  font-weight: bold;
  color: #fff;
  display: block;
}
.app-desc {
  font-size: 26rpx;
  color: rgba(255,255,255,0.8);
  margin-top: 16rpx;
  display: block;
}
.form-card {
  width: 620rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 48rpx 40rpx;
  box-shadow: 0 8rpx 40rpx rgba(0,0,0,0.15);
}
.tab-bar {
  display: flex;
  justify-content: center;
  margin-bottom: 40rpx;
  gap: 60rpx;
}
.tab-item {
  font-size: 32rpx;
  color: #999;
  padding-bottom: 12rpx;
}
.tab-item.active {
  color: #667eea;
  font-weight: bold;
  border-bottom: 4rpx solid #667eea;
}
.input-group {
  margin-bottom: 24rpx;
}
.input {
  height: 88rpx;
  border: 2rpx solid #e8e8e8;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
}
.error-text {
  color: #f44336;
  font-size: 24rpx;
  display: block;
  margin-bottom: 16rpx;
}
.submit-btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 32rpx;
  border-radius: 12rpx;
  border: none;
  margin-top: 16rpx;
}
</style>
