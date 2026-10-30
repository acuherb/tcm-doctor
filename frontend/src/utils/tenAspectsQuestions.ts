// 倪海厦经方家问诊十问（题干 + 选项），供 TenAspectsPanel 与问诊十问详情展示共用
export interface TenAspectOption {
  key: string
  label: string
}
export interface TenAspectQuestion {
  key: string
  title: string
  topic: string
  options: TenAspectOption[]
}

export const TEN_QUESTIONS: TenAspectQuestion[] = [
  {
    key: 'sleep', title: '1. 问睡眠',
    topic: '睡眠如何？是否一觉到天亮？是否每天定时醒？如果会醒是几点？是否多梦？',
    options: [
      { key: 'normal', label: '一觉到天亮，睡眠安稳' },
      { key: 'wake_incomplete', label: '断续睡眠、睡不安稳' },
      { key: 'wake_1_3', label: '持续在1-3点醒来' },
      { key: 'wake_3_5', label: '持续在3-5点醒来' },
      { key: 'dreamy', label: '多梦纷纭' },
    ],
  },
  {
    key: 'appetite', title: '2. 问胃口',
    topic: '感觉饿吗？有欲望想吃什么特别的食物或味道吗？还是不饿、完全没胃口？',
    options: [
      { key: 'normal', label: '有食欲，食之有味' },
      { key: 'huge', label: '胃口过大、食不知饱' },
      { key: 'no', label: '没胃口、完全不饿' },
      { key: 'tasteless', label: '食之无味' },
    ],
  },
  {
    key: 'stool', title: '3. 问大便',
    topic: '便秘吗？每天有大便吗？大便颜色？是下利吗？很臭还是无味？',
    options: [
      { key: 'normal', label: '每日一次，成形，软硬适中' },
      { key: 'loose', label: '大便稀溏' },
      { key: 'hard', label: '大便干硬、便秘' },
      { key: 'undigested', label: '下利清谷(有未消化食物)' },
    ],
  },
  {
    key: 'urine', title: '4. 问小便',
    topic: '小便什么颜色？频尿吗？还是尿不出来？没有尿意？平均一天几次？',
    options: [
      { key: 'normal', label: '小便淡黄，通畅' },
      { key: 'yellow', label: '小便黄或深黄' },
      { key: 'clear', label: '小便清白、量多' },
    ],
  },
  {
    key: 'thirst', title: '5. 问口渴',
    topic: '很渴吗？渴想喝什么温度的水？不渴会忘记喝水？再怎么喝也不能止渴？',
    options: [
      { key: 'normal', label: '时而有口渴，正常饮水' },
      { key: 'no_thirst', label: '不渴，经常忘记喝水' },
      { key: 'unquenchable', label: '口渴，怎么喝都不解渴' },
      { key: 'cold_water', label: '口渴，想喝冰水' },
      { key: 'warm_water', label: '口渴，想喝温水' },
    ],
  },
  {
    key: 'hot_cold', title: '6. 问寒热',
    topic: '平时觉得身体很热还是很冷？手脚冰冷？睡时身体寒热如何？',
    options: [
      { key: 'normal', label: '脚温，睡时无特别感觉' },
      { key: 'cold_feet', label: '手脚冰冷' },
      { key: 'cold_all', label: '睡时全身冰冷' },
      { key: 'hot_upper_cold_lower', label: '上热下寒' },
      { key: 'mingled', label: '寒热并结' },
      { key: 'hot_all', label: '全身燥热(长期低烧)' },
    ],
  },
  {
    key: 'sweat', title: '7. 问汗',
    topic: '容易出汗吗？会半夜盗汗？会时常流汗不止？还是不出汗的身体？',
    options: [
      { key: 'normal', label: '天热或运动易出汗' },
      { key: 'constant', label: '汗流不止、动不动就出汗' },
      { key: 'night', label: '半夜盗汗' },
      { key: 'none', label: '不怎么出汗、无汗' },
    ],
  },
  {
    key: 'energy', title: '8. 问体力精神',
    topic: '精神好吗？还是一直疲惫？早上起床精神奕奕还是无法起床？精神能集中吗？',
    options: [
      { key: 'normal', label: '精神好，精力充沛' },
      { key: 'tired', label: '精力不足、容易疲惫' },
      { key: 'aortic_listless', label: '全身疲乏、难以起床' },
    ],
  },
  {
    key: 'sexual', title: '9. 问性功能',
    topic: '性功能好吗？男性晨起是否有阳反应？女性乳房是否敏感？',
    options: [
      { key: 'normal', label: '晨起有阳反应，性功能正常' },
      { key: 'low', label: '性功能减退、晨起无阳反应' },
    ],
  },
  {
    key: 'menses', title: '10. 问女子月经',
    topic: '无论有无月经，详细说明月经情形：延后还是提前？痛不痛？生过小孩吗？',
    options: [
      { key: 'na', label: '不适用 / 无月经(男性或已绝经)' },
      { key: 'regular', label: '月经规律，无不适' },
      { key: 'early', label: '月经提前' },
      { key: 'late', label: '月经延后' },
      { key: 'pain', label: '痛经或有瘀血块' },
    ],
  },
]

// 由问诊答案(选项key)反查选项文案；custom 表示自填，返回 null 交由 note 展示
export function optionLabelOf(qKey: string, optKey: string | undefined): string | null {
  if (!optKey || optKey === 'custom') return null
  const q = TEN_QUESTIONS.find(x => x.key === qKey)
  const o = q?.options.find(o => o.key === optKey)
  return o ? o.label : null
}
