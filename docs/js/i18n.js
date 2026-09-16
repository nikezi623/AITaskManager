/**
 * Translations.
 *
 * Ported from the desktop app's TS table (app.py). The desktop version left a
 * number of user-facing strings hardcoded outside that table -- and showed
 * Chinese units ("天连续") even in English mode. Those live here now, so the
 * two languages are actually complete.
 */

export const STRINGS = {
  zh: {
    title: 'ATM · 习惯打卡',
    lang: 'EN',
    add_habit: '新增习惯',
    add_group: '新增分组',
    edit_habit: '编辑习惯',
    delete_habit: '删除习惯',
    edit_group: '编辑分组',
    delete_group: '删除分组',
    habit_name: '习惯名称',
    group_name: '分组名称',
    group_name_zh: '分组名称 (中文)',
    group_name_en: '分组名称 (English)',
    group_color: '分组颜色',
    select_group: '选择分组',
    cancel: '取消',
    save: '保存',
    delete: '删除',
    total_days: '累计',
    streak_days: '连续',
    week_completion: '本周完成率',
    all_done: '全部完成 🎉',
    confirm_delete_habit: '确定要删除习惯「{name}」吗？',
    confirm_delete_group: '确定要删除分组「{name}」及其所有习惯吗？',
    group_has_habits: '该分组下有 {n} 个习惯，将被一并删除！',
    stats_title: '打卡统计',
    today: '今天',
    move_to: '移动到',
    move_up: '上移',
    move_down: '下移',
    ungrouped: '未分组',
    day_unit: '天',
    streak_unit: '天连续',
    no_habits: '还没有习惯，长按空白处或点 + 新增',
    // sync
    sync_now: '立即同步',
    syncing: '同步中…',
    synced_at: '已同步 {time}',
    sync_failed: '同步失败',
    sync_pending: '待同步',
    offline: '离线',
    never_synced: '未连接',
    tap_to_sync: '点此同步',
    diagnostics: '诊断信息',
    diag_token: 'Token',
    diag_habits: '本机习惯数',
    diag_last_sync: '上次同步',
    diag_dirty: '有未推送改动',
    diag_error: '上次错误',
    diag_state_size: '本机数据大小',
    yes: '是',
    no: '否',
    never: '从未',
    // settings
    settings: '设置',
    token: 'GitHub 令牌',
    token_help: '需要 fine-grained token，仅勾选 ATM-data 仓库的 Contents 读写权限。',
    token_saved: '令牌已保存',
    test_connection: '测试连接',
    testing: '测试中…',
    connection_ok: '连接正常',
    force_update: '强制更新',
    version: '版本',
    undo: '撤销',
    deleted_habit: '已删除「{name}」',
    deleted_group: '已删除分组「{name}」',
    // errors
    err_token_invalid: 'GitHub 令牌已失效，请到设置里重新输入',
    err_token_scope: '令牌权限不足：需要 ATM-data 仓库的 Contents 读写权限',
    err_rate_limited: '触发 GitHub 频率限制，稍后自动重试',
    err_network: '网络不可用，数据已存在本机',
    err_conflict_retry: '同步冲突，正在重试…',
    err_unknown: '出错：{msg}',
  },
  en: {
    title: 'ATM · Habit Tracker',
    lang: '中文',
    add_habit: 'Add Habit',
    add_group: 'Add Group',
    edit_habit: 'Edit Habit',
    delete_habit: 'Delete Habit',
    edit_group: 'Edit Group',
    delete_group: 'Delete Group',
    habit_name: 'Habit Name',
    group_name: 'Group Name',
    group_name_zh: 'Group Name (中文)',
    group_name_en: 'Group Name (English)',
    group_color: 'Group Color',
    select_group: 'Select Group',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    total_days: 'Total',
    streak_days: 'Streak',
    week_completion: 'Weekly Completion',
    all_done: 'All Done 🎉',
    confirm_delete_habit: "Delete habit '{name}'?",
    confirm_delete_group: "Delete group '{name}' and all its habits?",
    group_has_habits: 'This group has {n} habit(s) which will also be deleted!',
    stats_title: 'Statistics',
    today: 'Today',
    move_to: 'Move to',
    move_up: 'Move Up',
    move_down: 'Move Down',
    ungrouped: 'Ungrouped',
    day_unit: 'd',
    streak_unit: 'd streak',
    no_habits: 'No habits yet. Long-press the background or tap +',
    // sync
    sync_now: 'Sync now',
    syncing: 'Syncing…',
    synced_at: 'Synced {time}',
    sync_failed: 'Sync failed',
    sync_pending: 'Pending',
    offline: 'Offline',
    never_synced: 'Not connected',
    tap_to_sync: 'Tap to sync',
    diagnostics: 'Diagnostics',
    diag_token: 'Token',
    diag_habits: 'Habits on this device',
    diag_last_sync: 'Last sync',
    diag_dirty: 'Unpushed changes',
    diag_error: 'Last error',
    diag_state_size: 'Local data size',
    yes: 'yes',
    no: 'no',
    never: 'never',
    // settings
    settings: 'Settings',
    token: 'GitHub token',
    token_help: 'Needs a fine-grained token with Contents read/write on the ATM-data repo only.',
    token_saved: 'Token saved',
    test_connection: 'Test connection',
    testing: 'Testing…',
    connection_ok: 'Connection OK',
    force_update: 'Force update',
    version: 'Version',
    undo: 'Undo',
    deleted_habit: "Deleted '{name}'",
    deleted_group: "Deleted group '{name}'",
    // errors
    err_token_invalid: 'GitHub token expired or revoked. Re-enter it in Settings.',
    err_token_scope: 'Token lacks permission: needs Contents read/write on ATM-data',
    err_rate_limited: 'GitHub rate limit hit, retrying shortly',
    err_network: 'Network unavailable — data is safe on this device',
    err_conflict_retry: 'Sync conflict, retrying…',
    err_unknown: 'Error: {msg}',
  },
};

export const WEEKDAYS = {
  zh: ['一', '二', '三', '四', '五', '六', '日'],
  en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
};

/** Translate `key` for `lang`, falling back to Chinese then to the key. */
export function makeT(lang) {
  const table = STRINGS[lang] || STRINGS.zh;
  return function t(key, params) {
    let value = table[key] ?? STRINGS.zh[key] ?? key;
    if (params) {
      for (const [name, replacement] of Object.entries(params)) {
        value = value.replaceAll(`{${name}}`, replacement);
      }
    }
    return value;
  };
}

/** "2026年09月" / "September 2026" */
export function formatMonth(year, monthIndex, lang) {
  const month = monthIndex + 1;
  if (lang === 'zh') return `${year}年${String(month).padStart(2, '0')}月`;
  const names = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  return `${names[monthIndex]} ${year}`;
}

export function weekdayLabels(lang) {
  return WEEKDAYS[lang] || WEEKDAYS.zh;
}
