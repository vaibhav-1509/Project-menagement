const TOKEN_KEY = 'pmt_token'
const USERNAME_KEY = 'pmt_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY)
}

function setUsername(name) {
  if (name) localStorage.setItem(USERNAME_KEY, name)
  else localStorage.removeItem(USERNAME_KEY)
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const token = getToken()
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })

  if (res.status === 401) {
    // The token is invalid - expired, rotated by a password change/reset
    // elsewhere, or (after a full data wipe) simply doesn't match any
    // account anymore. Clear it and tell AuthContext so every protected
    // route redirects to /login from wherever the user currently is,
    // instead of leaving them stuck on a page where every action silently
    // 401s forever.
    setToken(null)
    setUsername(null)
    window.dispatchEvent(new Event('pmt:unauthorized'))
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      // response wasn't JSON - keep the status text
    }
    throw new Error(detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export async function login(username, password) {
  const form = new URLSearchParams()
  form.set('username', username)
  form.set('password', password)

  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  if (!res.ok) {
    // Surface the backend's actual message (wrong credentials vs. account
    // locked are meaningfully different) instead of a single hardcoded string.
    let detail = 'Incorrect username or password'
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      // response wasn't JSON - keep the default message
    }
    throw new Error(detail)
  }
  const data = await res.json()
  setToken(data.access_token)
  setUsername(username)
  return data
}

export function getMe() {
  return request('/auth/me')
}

export function logout() {
  setToken(null)
  setUsername(null)
}

export function decodeJwt(token) {
  try {
    const payload = token.split('.')[1]
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch {
    return null
  }
}

export function getLookups() {
  return request('/lookups')
}

export function getUsers() {
  return request('/admin/users')
}

export function createUser(payload) {
  return request('/admin/users', { method: 'POST', body: payload })
}

export function updateUser(userId, payload) {
  return request(`/admin/users/${userId}`, { method: 'PUT', body: payload })
}

export function adminResetPassword(userId, newPassword) {
  return request(`/admin/users/${userId}/reset-password`, { method: 'POST', body: { new_password: newPassword } })
}

export function deleteUser(userId) {
  return request(`/admin/users/${userId}`, { method: 'DELETE' })
}

export function setUserActive(userId, isActive) {
  return request(`/admin/users/${userId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export async function changePassword(currentPassword, newPassword) {
  const data = await request('/auth/change-password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
  // The backend rotates this account's session-invalidation stamp as part of
  // changing the password (so any OTHER device's old token stops working),
  // which would otherwise log this browser out too - it hands back a fresh
  // token for the current session, so apply it to stay logged in.
  if (data.access_token) setToken(data.access_token)
  return data
}

export function getFiles(filters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') params.set(key, value)
  })
  const qs = params.toString()
  return request(`/dashboard/files${qs ? `?${qs}` : ''}`)
}

export function assignFile(fileId, userId, processTypeId) {
  return request(`/admin/files/${fileId}/assign`, {
    method: 'POST',
    body: { user_id: userId, process_type_id: processTypeId },
  })
}

export function assignBulk(fileIds, userId, processTypeId) {
  return request(`/admin/files/bulk-assign`, {
    method: 'POST',
    body: { file_ids: fileIds, user_id: userId, process_type_id: processTypeId },
  })
}

export function resetFile(fileId, processTypeId) {
  return request(`/admin/files/${fileId}/reset?process_type_id=${processTypeId}`, { method: 'POST' })
}

export function revokeFile(fileId, processTypeId) {
  return request(`/admin/files/${fileId}/revoke?process_type_id=${processTypeId}`, { method: 'POST' })
}

export function reopenFile(fileId, processTypeId) {
  return request(`/files/${fileId}/reopen?process_type_id=${processTypeId}`, { method: 'POST' })
}

export function approveFile(fileId, processTypeId) {
  return request(`/admin/files/${fileId}/approve?process_type_id=${processTypeId}`, { method: 'POST' })
}

export function rejectFile(fileId, processTypeId, reason, reassignToUserId) {
  return request(`/admin/files/${fileId}/reject?process_type_id=${processTypeId}`, {
    method: 'POST',
    body: { reason, reassign_to_user_id: reassignToUserId },
  })
}

export function setFileActive(fileId, isActive) {
  return request(`/admin/files/${fileId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export function deleteFile(fileId) {
  return request(`/admin/files/${fileId}`, { method: 'DELETE' })
}

export function completeAssignment(assignmentId) {
  return request(`/assignments/${assignmentId}/complete`, { method: 'POST' })
}

export function failAssignment(assignmentId, reason) {
  return request(`/assignments/${assignmentId}/fail`, { method: 'POST', body: { reason } })
}

export function getProcessHistory(fileId) {
  return request(`/files/${fileId}/process-history`)
}

export function previewImport(file, manualContext = null) {
  const form = new FormData()
  if (file) form.append('file', file)
  if (manualContext) {
    form.append('phase_name', manualContext.phaseName)
    if (manualContext.categoryName) form.append('category_name', manualContext.categoryName)
    if (manualContext.subCategoryName) form.append('sub_category_name', manualContext.subCategoryName)
    if (manualContext.fileNamesText) form.append('file_names_text', manualContext.fileNamesText)
  }
  return request('/admin/imports/preview', { method: 'POST', body: form, isForm: true })
}

export function commitImport(payload, csvFilename) {
  const qs = csvFilename ? `?csv_filename=${encodeURIComponent(csvFilename)}` : ''
  return request(`/admin/imports/commit${qs}`, { method: 'POST', body: payload })
}

export function moveCategory(fileIds, categoryId, subCategoryId) {
  return request('/admin/files/move-category', {
    method: 'POST',
    body: { file_ids: fileIds, category_id: categoryId, sub_category_id: subCategoryId },
  })
}

export function movePhase(fileIds, phaseId) {
  return request('/admin/files/move-phase', {
    method: 'POST',
    body: { file_ids: fileIds, phase_id: phaseId },
  })
}

export function createPhase(name) {
  return request('/admin/phases', { method: 'POST', body: { name } })
}

export function createCategory(phaseId, name) {
  return request('/admin/categories', { method: 'POST', body: { phase_id: phaseId, name } })
}

export function deleteCategory(categoryId) {
  return request(`/admin/categories/${categoryId}`, { method: 'DELETE' })
}

export function createSubCategory(categoryId, name) {
  return request('/admin/subcategories', { method: 'POST', body: { category_id: categoryId, name } })
}

export function deleteSubCategory(subCategoryId) {
  return request(`/admin/subcategories/${subCategoryId}`, { method: 'DELETE' })
}

export function getTaxonomyAdmin() {
  return request('/admin/taxonomy')
}

export function browseFolders(path) {
  const qs = path ? `?path=${encodeURIComponent(path)}` : ''
  return request(`/admin/filesystem/browse${qs}`)
}

export function setPhaseActive(phaseId, isActive) {
  return request(`/admin/phases/${phaseId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export function renamePhase(phaseId, name) {
  return request(`/admin/phases/${phaseId}`, { method: 'PATCH', body: { name } })
}

export function deletePhase(phaseId) {
  return request(`/admin/phases/${phaseId}`, { method: 'DELETE' })
}

export function setCategoryActive(categoryId, isActive) {
  return request(`/admin/categories/${categoryId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export function renameCategory(categoryId, name) {
  return request(`/admin/categories/${categoryId}`, { method: 'PATCH', body: { name } })
}

export function setSubCategoryActive(subCategoryId, isActive) {
  return request(`/admin/subcategories/${subCategoryId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export function renameSubCategory(subCategoryId, name) {
  return request(`/admin/subcategories/${subCategoryId}`, { method: 'PATCH', body: { name } })
}

export function getProcessTypes() {
  return request('/admin/process-types')
}

export function createProcessType(name) {
  return request('/admin/process-types', { method: 'POST', body: { name } })
}

export function setProcessTypeActive(processTypeId, isActive) {
  return request(`/admin/process-types/${processTypeId}`, { method: 'PATCH', body: { is_active: isActive } })
}

export function renameProcessType(processTypeId, name) {
  return request(`/admin/process-types/${processTypeId}`, { method: 'PATCH', body: { name } })
}

export function reorderProcessTypes(orderedIds) {
  return request('/admin/process-types/reorder', { method: 'POST', body: { ordered_ids: orderedIds } })
}

export function deleteProcessType(processTypeId) {
  return request(`/admin/process-types/${processTypeId}`, { method: 'DELETE' })
}

export function getAuditTrail(filters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') params.set(key, value)
  })
  const qs = params.toString()
  return request(`/admin/audit-trail${qs ? `?${qs}` : ''}`)
}

export function getCalendarMonth(year, month) {
  return request(`/calendar/activity?year=${year}&month=${month}`)
}

export function getCalendarDay(dateIso) {
  return request(`/calendar/day?date=${dateIso}`)
}

export function getCompletionsReport(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  ).toString()
  return request(`/reports/completions${qs ? `?${qs}` : ''}`)
}

export function getTaxonomyProgressReport() {
  return request('/reports/taxonomy-progress')
}

export function getRepairsReport(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  ).toString()
  return request(`/reports/repairs${qs ? `?${qs}` : ''}`)
}

export function getReportsDetail(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  ).toString()
  return request(`/reports/detail${qs ? `?${qs}` : ''}`)
}

export function getNotifications(limit = 30) {
  return request(`/notifications?limit=${limit}`)
}

export function markNotificationRead(id) {
  return request(`/notifications/${id}/read`, { method: 'POST' })
}

export function markAllNotificationsRead() {
  return request('/notifications/mark-all-read', { method: 'POST' })
}

export function getAdminWorkboard() {
  return request('/admin/workboard')
}

async function downloadFile(path, filenameFallback) {
  // Binary response (xlsx/pdf) - can't use a plain <a href> because the
  // endpoint needs the Bearer token, so fetch it manually and hand the
  // browser a blob: URL to actually save it.
  const token = getToken()
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api${path}`, { headers })

  if (res.status === 401) {
    setToken(null)
    setUsername(null)
    window.dispatchEvent(new Event('pmt:unauthorized'))
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      // response wasn't JSON - keep the status text
    }
    throw new Error(detail)
  }

  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : filenameFallback

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function _exportQueryString(params) {
  return new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  ).toString()
}

export function exportReportExcel(params = {}) {
  const qs = _exportQueryString(params)
  return downloadFile(`/reports/export/excel${qs ? `?${qs}` : ''}`, 'completions_report.xlsx')
}

export function exportReportPdf(params = {}) {
  const qs = _exportQueryString(params)
  return downloadFile(`/reports/export/pdf${qs ? `?${qs}` : ''}`, 'completions_report.pdf')
}

export function getWorkerProcessPaths(userId) {
  return request(`/admin/users/${userId}/process-paths`)
}

export function setWorkerProcessPaths(userId, entries) {
  return request(`/admin/users/${userId}/process-paths`, { method: 'PUT', body: entries })
}

export function updatePriority(fileId, priority) {
  return request(`/admin/files/${fileId}/priority`, { method: 'PATCH', body: { priority } })
}

export function getSettings() {
  return request('/admin/settings')
}

export function updateSettings(lowWorkloadThreshold, staleAssignmentDays, adminFolders = {}) {
  return request('/admin/settings', {
    method: 'PUT',
    body: {
      low_workload_threshold: lowWorkloadThreshold,
      stale_assignment_days: staleAssignmentDays,
      all_pending_path: adminFolders.allPendingPath ?? null,
      admin_pending_path: adminFolders.adminPendingPath ?? null,
      admin_complete_path: adminFolders.adminCompletePath ?? null,
    },
  })
}

export function getProfile() {
  return request('/profile/me')
}

export function updateAvailability(isAvailable) {
  return request('/profile/availability', { method: 'PATCH', body: { is_available: isAvailable } })
}

export function getMyLeave() {
  return request('/profile/leave')
}

export function addMyLeave(startDate, endDate) {
  return request('/profile/leave', { method: 'POST', body: { start_date: startDate, end_date: endDate } })
}

export function cancelMyLeave(leaveId) {
  return request(`/profile/leave/${leaveId}`, { method: 'DELETE' })
}

export function getUserLeave(userId) {
  return request(`/admin/users/${userId}/leave`)
}

export function addUserLeave(userId, startDate, endDate) {
  return request(`/admin/users/${userId}/leave`, {
    method: 'POST',
    body: { start_date: startDate, end_date: endDate },
  })
}

export function deleteUserLeave(userId, leaveId) {
  return request(`/admin/users/${userId}/leave/${leaveId}`, { method: 'DELETE' })
}
