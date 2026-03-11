const TOKEN_KEY = 'bk_token'
const USER_KEY = 'bk_user'

export function getToken() {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function setToken(token) {
  uni.setStorageSync(TOKEN_KEY, token)
}

export function getUser() {
  return uni.getStorageSync(USER_KEY) || ''
}

export function setUser(username) {
  uni.setStorageSync(USER_KEY, username)
}

export function clearAuth() {
  uni.removeStorageSync(TOKEN_KEY)
  uni.removeStorageSync(USER_KEY)
}

export function isLoggedIn() {
  return !!getToken()
}
