import { BASE_URL } from './config.js'
import { getToken, clearAuth } from './auth.js'

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const header = { 'Content-Type': 'application/json' }
    if (token) header['Authorization'] = `Bearer ${token}`

    uni.request({
      url: BASE_URL + path,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode === 401) {
          clearAuth()
          uni.reLaunch({ url: '/pages/login/login' })
          reject(new Error('未登录'))
          return
        }
        resolve(res.data)
      },
      fail(err) {
        reject(err)
      }
    })
  })
}

export function get(path) {
  return request('GET', path)
}

export function post(path, data) {
  return request('POST', path, data)
}

export function del(path) {
  return request('DELETE', path)
}

export function uploadFile(path, filePath) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const header = {}
    if (token) header['Authorization'] = `Bearer ${token}`

    uni.uploadFile({
      url: BASE_URL + path,
      filePath,
      name: 'file',
      header,
      success(res) {
        if (res.statusCode === 401) {
          clearAuth()
          uni.reLaunch({ url: '/pages/login/login' })
          reject(new Error('未登录'))
          return
        }
        resolve(JSON.parse(res.data))
      },
      fail(err) {
        reject(err)
      }
    })
  })
}
