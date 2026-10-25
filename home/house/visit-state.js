// Viewing history is independent of resource-cache completeness.
export function createVisitState(build, path, stores) {
  const key = 'polebug-house-completed:' + path;
  const version = String(build || 'unversioned');
  return {
    hasCompleted() {
      return stores.some(getStore => {
        try { return getStore().getItem(key) === version; } catch { return false; }
      });
    },
    markCompleted() {
      for (const getStore of stores) {
        try { getStore().setItem(key, version); } catch { /* Private mode or quota. */ }
      }
    }
  };
}
