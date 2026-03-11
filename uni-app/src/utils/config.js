// API 基础地址 — 开发时指向工作站，生产环境需改为实际域名
// #ifdef H5
const BASE_URL = ''  // H5 同源，无需前缀
// #endif
// #ifndef H5
const BASE_URL = 'http://192.168.0.15:8080'  // 小程序/App 需完整地址
// #endif

export { BASE_URL }
