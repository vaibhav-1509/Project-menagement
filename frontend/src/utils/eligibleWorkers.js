// Shared by AssignModal and RejectModal - both need the exact same
// eligible-worker predicate, so it lives in one place instead of two
// copies that could quietly drift apart.
export function eligibleWorkers(users, processTypeId, { includeUnavailable = false } = {}) {
  return users.filter((u) => {
    if (!u.IsActive || !u.enabledProcessTypeIds.includes(processTypeId)) return false
    if (includeUnavailable) return true
    return u.isAvailable && !u.isOnLeaveToday
  })
}
