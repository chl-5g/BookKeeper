<script>
import { isLoggedIn } from './utils/auth.js'

export default {
  onLaunch() {
    // 检查登录状态，未登录跳转登录页
    if (!isLoggedIn()) {
      uni.reLaunch({ url: '/pages/login/login' })
    }
  },
}
</script>

<style>
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
