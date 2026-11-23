/* Chinese interface (简体中文), switchable; English stays the default and the source of truth.

   How it works: the page is written in English. In Chinese mode a text node, placeholder, title or aria-label whose
   whole text is a key of I18N_ZH is shown in Chinese; a MutationObserver does the same for text the app writes later.
   The English original is kept on the node, so switching back restores it exactly. No app code is changed and nothing
   is translated by a machine at run time: every Chinese string below was written by hand.

   What is NOT translated, on purpose:
   - Technical details (route edges, the route check, score formulas, indicator definitions). Walk names, walk
     descriptions, "Why this route?", City Walk stops and the page's own chat messages are written in Chinese where
     they are composed (route-story.js, journey-ui.js, journey.js, app.js); short labels with a number in them
     ("13 min", "Museum +1") are matched by I18N_ZH_PATTERNS below. A sentence no rule matches stays in English, whole.
   - Input values. The sentence the priority pills write into the request box stays English because the planner reads
     it. Visitors can type their own request in Chinese: on 2026-11-15 the live interpreter turned
     "我想要一条更绿、更安静、建筑有看头的路线" into Nature, Quiet & Relax and Architecture at 90. A start and destination
     written in a Chinese sentence are not filled into From / To (that step reads English), which the hint says.
   - The 12 dimension names are not renamed: Chinese mode shows a Chinese gloss followed by the unchanged English
     name ("自然 Nature"), so the name on screen always matches the data, the docs and the methodology.
   - Data-source names, and place names Wikidata has no Chinese label for. A place that has one (616 of them, in
     data/places/names-zh.json) is shown with it in front of the English name, "熨斗大厦 Flatiron Building", when a
     text is exactly that name; a place name inside a sentence stays as it is.

   The choice is remembered in this browser only (localStorage), never sent anywhere. */
const I18N_DIMENSIONS_ZH = {
 'Architecture': '建筑', 'Nature': '自然', 'Culture': '文化', 'Quiet & Relax': '安静放松', 'Spatial Comfort': '空间舒适',
 'Urban Vibrancy': '城市活力', 'Food & Retail': '餐饮零售', 'Scenic & Visual': '景观视野', 'Walkability': '步行便利',
 'Access & Safety': '通行与安全', 'Environment': '环境', 'Transit Connectivity': '公交接驳',
};
const I18N_ZH = {
 // navigation and menus
 'Plan walk': '规划步行', 'Start & destination': '起点与终点', 'Customize walk': '自定义步行', 'Time & 12 dimensions': '时间与 12 个维度',
 'Explore urban data': '浏览城市数据', 'Explore Urban Data': '浏览城市数据', 'NYC GIS layers': '纽约 GIS 图层', 'Map layers': '地图图层', 'Weather & legend': '天气与图例',
 'Map': '地图', 'Dark': '深色', 'Light': '浅色', 'Reset map view': '重置地图视图', 'Back to Manhattan, Brooklyn & Queens': '回到曼哈顿、布鲁克林和皇后区', 'Manhattan, Brooklyn & Queens': '曼哈顿、布鲁克林和皇后区', 'Downtown & Midtown Manhattan': '曼哈顿下城和中城', 'Walker ratings': '步行者评分', 'How walkers rated their walks': '步行者怎么评价他们走过的路线', 'Data legend': '数据图例',
 'Show or hide': '显示或隐藏', 'Data sources': '数据来源', 'Status & coverage': '状态与覆盖范围', 'About': '关于', 'This prototype': '本原型',
 'Export to Kepler': '导出到 Kepler', 'GIS data': 'GIS 数据', 'Kepler studio': 'Kepler 工作台', 'Menu': '菜单', 'Back': '返回', '← Map': '← 地图',
 'Weather loading…': '天气加载中…', 'Weather…': '天气…', 'Find routes →': '查找路线 →', '⚙ Prefs': '⚙ 偏好', 'Navigate': '导航', 'Edit': '编辑', 'New': '新建',
 '☷ Plan': '☷ 规划', '◈ Results': '◈ 结果', 'Your walk': '你的步行', 'Interface language': '界面语言',
 // route result labels (the sentences and numbers beside them are built from data and stay in English)
 'Personalized score': '个性化得分', 'Overall score': '综合得分', 'Data coverage': '数据覆盖', 'Detour': '绕行', 'Shortest distance': '最短距离', 'Engine route': '引擎路线',
 'Describe your ideal walk...': '描述你理想的步行…（中文也可以）', 'choose destination': '选择终点',
 // planning
 '01 / HOW DO YOU WANT TO WALK?': '01 / 你想怎么走？', 'Find your': '找到属于你的', 'kind': '那种', 'of walk.': '步行。',
 'Not just the shortest way. Your way through the city.': '不只是最短的路，而是你穿过城市的方式。',
 'Made for people new to New York: get to know a neighbourhood in Manhattan, Brooklyn or Queens on a walk of 20 minutes or more.': '为刚到纽约的人而做：用一段 20 分钟以上的步行，认识曼哈顿、布鲁克林或皇后区的一个街区。',
 'WHAT MATTERS ON THIS WALK': '这次步行你在意什么',
 'Or describe the walk in your own words. From and To fill in from your sentence.': '也可以用自己的话描述这次步行，中文也可以。用中文描述时，起点和终点请在下方选择。',
 'Voice or text — you can edit the transcript.': '语音或文字均可，识别结果可以修改。',
 'I\u2019d like a greener, quieter walk with interesting architecture.': '我想要一条更绿、更安静、建筑有看头的路线。',
 'Make it quieter, even if it takes five more minutes…': '再安静一点，多走五分钟也可以…', 'Search address or landmark': '搜索地址或地标', 'Search dimensions…': '搜索维度…',
 'Search urban datasets…': '搜索城市数据集…', 'Add a stop: any NYC place': '添加途经点：纽约任意地点', 'Search any NYC address, place or business': '搜索纽约的地址、地点或商家',
 'Search your hotel (name or brand)': '搜索你的酒店（名称或品牌）',
 'Plan My Walk': '规划我的步行', 'Create My Walk': '生成我的步行', 'How would you like to explore New York?': '你想怎样探索纽约？', 'Made for people new to New York, on walks of 20 minutes or more.': '为刚到纽约的人而做，适合 20 分钟以上的步行。',
 'Checking AI interpretation service…': '正在检查 AI 理解服务…',
 'After your walk: rate it (optional)': '走完之后：给这段路打分（可选）', 'Overall, how satisfied are you with this walk?': '总体来说，你对这段步行有多满意？',
 'How well did it match what you asked for?': '和你想要的有多一致？', 'How quiet did it feel?': '感觉有多安静？', 'How green did it feel?': '感觉有多绿？',
 '1 not at all · 5 very. Only the first is required.': '1 完全不 · 5 非常。只有第一题必答。', 'The other dimensions you asked for:': '你选的其他维度：',
 'Send': '发送', 'This one': '这一条', 'The other one': '另一条', 'No difference': '没有差别', 'Yes': '是', 'No': '否',
 'You have arrived. How was the walk? Rate it under “Why this route”.': '你已到达。这段路走得怎么样？请在"为什么是这条路线"里打分。',
 'What walkers said': '其他步行者怎么说', 'All results': '全部结果', 'I walked this – rate it now': '我走完了，马上评价', 'How was your walk?': '这段路走得怎么样？',
 'Rate this walk (optional)': '给这段路打分（可选）', 'Choose a route first.': '请先选择一条路线。', 'No walker has rated a walk yet.': '还没有步行者评价过。',
 'Streets on this route walkers reported:': '这条路线上被步行者反馈过的街道：',
 'WALKER FEEDBACK': '步行者反馈', 'All results ↗': '全部结果 ↗', 'Create a walk to see what walkers said about it. After you walk it, rate it here.': '生成一条路线，就能看到其他步行者的评价；走完后在这里打分。',
 'Evaluation': '效果评估', 'No evaluation data yet': '暂无评估数据',
 'Tourist': '游客', 'Curious Local': '好奇的本地人', 'Leisure Walker': '休闲散步者',
 'Architecture & landmarks': '建筑与地标', 'A new neighbourhood': '一个没去过的街区', 'Quiet & green': '安静、有绿意',
 'Historic architecture and cultural landmarks': '历史建筑与文化地标', 'Through a neighbourhood I have not explored': '走进一个我没去过的街区', 'A quiet, green walk': '一段安静、有绿意的步行',
 'Set From to a neighbourhood you have not walked yet. Otherwise the loop starts where you are.': '把起点设在一个你还没走过的街区；不设的话，环线从你所在的位置出发。',
 'For tourists, curious locals and leisure walkers: walks of 20 minutes or more in Manhattan, Brooklyn or Queens.': '为游客、好奇的本地人和休闲散步者而做：在曼哈顿、布鲁克林或皇后区走 20 分钟以上。',
 'For tourists, curious locals and leisure walkers, on walks of 20 minutes or more.': '为游客、好奇的本地人和休闲散步者而做，适合 20 分钟以上的步行。',
 '02 / FROM & TO': '02 / 起点与终点', 'FROM': '起点', 'TO': '终点', 'From': '起点', 'To': '终点', '◎ Use GPS': '◎ 使用定位',
 'Quick-pick a start (default: my location)': '快速选择起点（默认：我的位置）', 'Quick-pick a destination (optional)': '快速选择终点（可选）',
 'Custom map / address point': '自选地图点或地址', 'My current location': '我的当前位置', 'Swap': '交换', 'STOPS': '途经点', 'optional · in order': '可选 · 按顺序',
 '⌖ PICK ON MAP': '⌖ 在地图上选点', 'Destination': '指定终点', 'Discover for me': '为我推荐', 'Back to start': '回到起点', 'Back to hotel': '回到酒店',
 'My hotel ·': '我的酒店 ·', 'not set': '未设置', 'Start here': '从这里出发', 'Return here': '回到这里', 'Explore nearby': '探索周边',
 'Remember on this device': '在本设备上记住', 'stored only in this browser': '仅保存在本浏览器',
 'Hotel search shows real places from map data. No live room availability, prices or booking.': '酒店搜索显示的是地图数据中的真实地点，不提供实时房态、价格或预订。',
 'DISCOVERY': '探索', 'Clear journey': '清空行程', 'QUICK PREFERENCES': '快捷偏好',
 'Each chip sets an existing experience dimension (or adds a café stop through the journey planner). Nothing is claimed until routes are computed.': '每个按钮对应一个已有的体验维度（或通过行程规划加一个咖啡停留点）。路线算出来之前，不会声称任何效果。',
 'Click anywhere on the map to set a point.': '点击地图任意位置来设定一个点。', 'CANCEL': '取消',
 // preferences
 '03 / YOUR WALKING PREFERENCES': '03 / 你的步行偏好', 'NOT INTERPRETED': '尚未解析',
 'Strollane turns your words into priorities; unmentioned dimensions stay neutral.': 'Strollane 把你的话转成偏好；没提到的维度保持中性。',
 '✧ Your interpreted priorities appear here after planning.': '✧ 规划后，这里会显示解析出的偏好。',
 'Fine-tune (12 dimensions)': '微调（12 个维度）', 'EXPERIENCE DIMENSION': '体验维度', 'PREFERENCE': '偏好', '✎ Adjust preferences': '✎ 调整偏好',
 'Weights indicate user preference (0–100), not objective city quality. Default 50 = not expressed. Route scores are relative ranks across Manhattan, Brooklyn and Queens together, computed from public NYC and OpenStreetMap records: proxies, not validated measures of how a street feels.': '权重表示你的偏好（0–100），不是城市的客观质量。默认 50 表示未表达偏好。路线分数是曼哈顿、布鲁克林和皇后区放在一起的相对排名，由纽约公开数据和 OpenStreetMap 记录算出：它们是替代指标，并非经过验证的街道感受度量。',
 // constraints
 '04 / WALK OPTIONS': '04 / 步行选项', '04 / WALKING CONSTRAINTS': '04 / 步行限制', 'MAX WALKING TIME · A HARD LIMIT': '最长步行时间 · 硬性上限', 'Custom': '自定义',
 'Custom maximum (minutes)': '自定义上限（分钟）', 'Default 100 min. Type any whole number of minutes (10 or more); the slider extends to match.': '默认 100 分钟。可输入任意整数分钟（不少于 10），滑杆会随之延长。',
 'MAX WALKING DISTANCE · HARD LIMIT': '最长步行距离 · 硬性上限', 'NOT SET': '未设置', 'Not set': '未设置', 'Custom distance': '自定义距离',
 'Total outing (walking + visits, optional, minutes)': '总外出时间（步行 + 停留，可选，分钟）', 'Maximum detour over shortest candidate (%)': '相对最短路线的最大绕行（%）',
 'Avoid excessive detours': '避免过多绕行', '≤ 25% longer than baseline': '比基准路线最多长 25%', 'Step-free access': '无台阶通行', 'verified pedestrian-access data required': '需要经过核实的无障碍数据',
 'Avoid stairs': '避开楼梯', 'excludes OpenStreetMap steps from routing': '规划时排除 OpenStreetMap 中的台阶',
 '⚠ Step-free access needs verified curb-ramp and elevator data, which is not connected. Recommendations are blocked while this constraint is on.': '⚠ 无台阶通行需要经过核实的路缘坡道和电梯数据，目前尚未接入。开启此限制时不会给出推荐。',
 // conversation
 '05 / REFINE YOUR WALK': '05 / 调整你的步行', 'CONVERSATION': '对话', 'Ask for changes. New route results and the map are recomputed when possible.': '可以提出修改。条件允许时会重新计算路线和地图。',
 'Enter to send · Shift + Enter for a new line': '回车发送 · Shift + 回车换行', 'CONVERSATION LOG (FULL)': '完整对话记录',
 // results
 'YOUR WALK': '你的步行', 'Choose how it': '选择它带给你的', 'feels.': '感受。', 'YOUR WALK OPTIONS': '可选路线', 'No walks yet': '还没有路线',
 'Describe how you want to walk, or tap a few chips.': '描述你想怎么走，或者点几个按钮。', 'More routes': '更多路线', '➤ Start Navigation': '➤ 开始导航', '➤ Start': '➤ 开始',
 '3D map preview': '3D 地图预览', '3D preview': '3D 预览', 'Share': '分享', 'Rate walk': '评价路线', 'Photos of places along the walk': '沿途地点照片', 'Show all places': '显示全部地点', 'After your walk: rate how it felt': '走完后：评价这次步行的感受', 'Share this walk': '分享这条路线', 'ALONG THIS WALK': '沿途', 'On the street': '街景',
 'Choose a walk to see the places along it.': '选一条路线，查看沿途地点。', 'REFINE YOUR WALK': '调整你的步行',
 'More Nature': '更多自然', 'Quieter Streets': '更安静的街道', 'More Architecture': '更多建筑', 'Shorter Walk': '更短的路线',
 'Each action updates state and requests fresh pedestrian candidate routes. A preference without evidence will not be claimed as achieved.': '每次操作都会更新状态并重新请求候选步行路线。没有数据支持的偏好，不会被声称已实现。',
 'Technical details': '技术细节', 'Scores, ranking, data and edges': '分数、排名、数据与路段', 'LIVE WEATHER': '实时天气', 'Awaiting forecast': '等待天气预报',
 'GPS STATUS': '定位状态', 'OFF': '关闭', 'Location unavailable': '无法获取位置', 'RANKING': '排名', 'No route data yet.': '还没有路线数据。',
 'WHY THIS ROUTE?': '为什么是这条路线？', 'Generate routes to see evidence-grounded reasons.': '生成路线后，可查看有数据依据的理由。',
 'WEATHER & YOUR WALK': '天气与你的步行', 'Loading the forecast…': '正在加载天气预报…', 'ROUTE URBAN DATA': '路线周边城市数据',
 'Select a route to see the real city data around it.': '选一条路线，查看周边的真实城市数据。', 'ROUTE EDGES': '路线路段', 'Ordered OSM pedestrian edges': '按顺序排列的 OSM 步行路段',
 'Select a route to list the OSM pedestrian edges it uses, in order.': '选一条路线，按顺序列出它经过的 OSM 步行路段。',
 'EXPERIENCE PROFILE': '体验概况', 'NOT AVAILABLE': '暂无', 'Selected route': '所选路线', 'Compare routes': '比较路线',
 'Dimension Score ≠ Preference Weight. Missing is not zero.': '维度分数 ≠ 偏好权重。缺失不等于零。',
 'RESEARCH / RAW STREET EVIDENCE': '研究 / 街道原始数据', 'Click a street segment to inspect its recorded attributes.': '点击一段街道，查看它的记录属性。',
 'Clear selected street': '取消选中的街道', 'DATA & METHODOLOGY ↗': '数据与方法 ↗', 'Export GIS data for Kepler.gl': '导出 GIS 数据到 Kepler.gl',
 'PROJECT NOTES / TRANSPARENCY': '项目说明 / 透明度', "What is real, and what's next.": '哪些是真实的，接下来做什么。',
 // map and explore
 'Connecting to the city': '正在连接城市数据', 'Loading the basemap and official NYC street data.': '正在加载底图和纽约官方街道数据。',
 'CONNECTING TO NYC DATA…': '正在连接纽约数据…', 'Street evidence ▾': '街道数据 ▾', 'Dimension': '维度', 'Display': '显示', 'Experience': '体验', 'Coverage': '覆盖率',
 'Analyze current view': '分析当前视图', 'Scores require calibration. Unknown ≠ zero.': '分数需要校准。未知 ≠ 零。', 'Reset view': '重置视图', 'Line opacity': '线条不透明度',
 'Loading computed 12-dimension street data…': '正在加载已计算的 12 维度街道数据…', 'Choose a journey to compare real walking routes.': '选择一段行程，比较真实的步行路线。',
 'Urban Data Layers': '城市数据图层', 'Explore real NYC data along your route': '浏览路线沿途的真实纽约数据', 'ACTIVE DATASETS': '已启用的数据集', 'All on': '全部开启', 'All off': '全部关闭',
 'Opacity': '不透明度', 'Along selected route': '沿所选路线', 'Current map view': '当前地图视图', 'Route corridor': '路线走廊', 'display only — never changes scores': '仅用于显示，不影响分数',
 'NAVIGATION OVERLAYS': '导航叠加层', 'Alternative routes': '备选路线', 'Route POIs': '路线地点', 'Legend': '图例', 'Lower': '较低', 'Mid': '中等', 'Higher': '较高',
 'The selected route and start / destination always stay on top. Your location appears only after you allow GPS.': '所选路线和起终点始终显示在最上层。只有在你允许定位后，才会显示你的位置。',
 'Summary': '概要', 'Indicators': '指标', 'Methodology': '方法',
 // navigation mode
 'Starting…': '正在开始…', 'Retry': '重试', 'Continue to next stop': '前往下一站', 'Skip optional stop': '跳过可选停留点', 'You have arrived': '你已到达', 'Walk complete.': '步行结束。',
 'End navigation': '结束导航', '◎ Recenter': '◎ 回到当前位置', 'Voice on': '语音开启', 'Pause': '暂停', 'More': '更多', 'Repeat': '重复', 'North up': '正北朝上', 'Exit': '退出',
 '➤ Start Navigation': '➤ 开始导航', 'Resume': '继续', 'Voice off': '语音关闭', 'Heading up': '前进方向朝上', 'Route up': '路线方向朝上', 'AR · compass': 'AR · 指南针', 'AR view': 'AR 视图',
 'Raise to view: on': '抬起手机即显示：开', 'Raise to view: off': '抬起手机即显示：关', 'Raise: on': '抬起：开', 'Send rating': '提交评分', 'Did it match what you asked for?': '和你的要求相符吗？', 'Not really': '不太相符', 'Partly': '部分相符', 'More detail (optional)': '更多细节（可选）', 'Add a comment (optional, public)': '写条评论（可选，公开）', 'No location or name is sent.': '不会发送位置或姓名。', 'No comments yet.': '还没有评论。', 'How quiet did it feel?': '感觉安静吗？', 'How green did it feel?': '感觉绿意多吗？', 'Thanks, saved.': '谢谢，已保存。', 'Raise: off': '抬起：关', 'Raise the phone to open the camera view': '抬起手机即打开相机视图', 'To the start of your walk': '前往路线起点',
 'Weak GPS signal — position approximate': 'GPS 信号弱，位置只是大致位置', 'Checking whether you left the route…': '正在确认你是否偏离了路线…', 'Off route': '已偏离路线',
 'Off route — recalculating on the walking network…': '已偏离路线，正在步行路网上重新规划…', 'Paused': '已暂停', 'Arrived at stop': '已到达途经点', 'Navigation problem': '导航出现问题',
 'Waiting for GPS…': '正在等待 GPS…', 'Getting your location…': '正在获取你的位置…', 'Could not recalculate — your last route is still shown. Tap Retry.': '无法重新规划，仍显示原来的路线。请点“重试”。',
 'Location permission was turned off. Navigation stopped updating.': '定位权限已关闭，导航已停止更新。',
 'No device direction — map follows the route instead; arrow hidden': '没有手机朝向数据：地图改为跟随路线方向，不显示朝向箭头',
 'No direction data — heading arrow hidden': '没有方向数据，不显示朝向箭头', 'Low-confidence instruction — check the map': '这条指引不太确定，请看地图',
 'Next:': '下一个：', 'Keep this screen on while you walk: iPhone pauses navigation when the screen locks or you switch apps.': '走路时请保持屏幕亮着：iPhone 锁屏或切到别的 App 时，导航会暂停。', 'Navigate to start': '导航到起点', 'Replan from my location': '从我的位置重新规划', 'Resume navigation?': '继续上次的导航？', 'Pick up where you stopped.': '从上次停下的地方继续。', 'The route server is still waking up; re-routing waits until it answers.': '路线服务器还在启动，重新规划要等它响应。', 'Discard': '放弃',
 'Choose how to begin. STROLLANE will not pretend you are at the start.': '请选择怎么开始。STROLLANE 不会假装你已经在起点。',
 'At the start — now following your planned walk.': '已到起点，现在开始按计划路线走。', 'Location is not available in this browser.': '这个浏览器无法使用定位。',
 'Re-planned from your location. Tap Start Navigation.': '已从你的位置重新规划。请点“开始导航”。',
 'The walking network was updated since your navigation started — please plan the walk again.': '导航开始后步行路网已更新，请重新规划路线。',
 'This route failed its route check and cannot be navigated.': '这条路线没有通过路线检查，无法导航。',
 'This walk is over your limits. Pick another walk or change your time.': '这条路线超出了你设定的限制。请换一条路线或调整时间。',
 'Location permission was denied. Allow location for this site to navigate.': '定位权限被拒绝。请允许本网站使用定位后再导航。',
 'Your position is unavailable (GPS off?).': '无法获取你的位置（GPS 是否关闭了？）。', 'Locating timed out. Try again outdoors.': '定位超时，请到室外再试。',
 // short pill labels (walk-presets.js): a gloss in front of the same short English label
 'Quiet': '安静 Quiet', 'Comfort': '舒适 Comfort', 'Vibrancy': '活力 Vibrancy', 'Scenic': '景观 Scenic', 'Safety': '安全 Safety', 'Transit': '公交 Transit', 'Food': '餐饮 Food',
 // journey and results labels
 "I'd like a greener, quieter walk with interesting architecture.": '我想要一条更绿、更安静、建筑有看头的路线。',
 'Plan your walk': '规划你的步行', 'Your routes': '你的路线', 'Coffee stop': '咖啡停留', 'YOUR CITY WALK': '你的城市漫步', 'WITHIN LIMITS': '在限制范围内', 'Walking': '步行', 'Stops': '停留点',
 'Total outing': '总外出时间', 'Replace': '更换', 'Remove': '移除', 'More museums': '更多博物馆', 'More historic': '更多历史建筑', 'Add coffee': '加一杯咖啡', 'Add restaurant': '加一家餐厅',
 'Return to hotel': '回酒店', 'Less walking': '少走一点', 'Extend time': '延长时间', 'Hours not listed': '未列出营业时间', 'NYC designated landmark': '纽约市指定地标',
 'Park': '公园', 'Historic building': '历史建筑', 'Museum': '博物馆', 'Landmark buildings': '地标建筑', 'Cultural venues': '文化场所', 'route match': '路线匹配',
 'Loading the map…': '地图加载中…', 'The street map is taking longer than usual on this connection. Everything else already works.': '当前网络下街道地图加载较慢，其他功能已可正常使用。',
 'Weather unavailable': '天气不可用', 'Weather n/a': '天气不可用', 'Weather-aware routing': '考虑天气的路线规划', 'Refresh': '刷新', 'Export sections to Kepler.gl': '导出分区到 Kepler.gl',
 'Building theme': '建筑主题', 'Environment theme': '环境主题', 'Open to load the dataset catalog.': '展开以加载数据集目录。', 'Street base (LION)': '街道底图（LION）', '↻ Streets': '↻ 街道',
 'Parks & gardens': '公园与花园', 'Street trees': '行道树', 'Historic districts': '历史街区', 'Landmark lots': '地标地块', 'Streets': '街道', 'Buildings': '建筑', 'Historic': '历史', 'Traffic': '交通', 'Public Services': '公共服务',
 'Street, path & transport lines': '街道、步道与交通线路', 'roof height': '屋顶高度', 'year built': '建成年代', '311 noise complaint density': '311 噪音投诉密度', 'No environmental surface': '不叠加环境图层',
 'Places & facilities': '地点与设施', 'YOU': '你', 'You': '你', 'Best match': '最佳匹配', 'best match': '最佳匹配', 'Shortest': '最短', 'Fastest': '最快',
 'Looking for street photos…': '正在查找街景照片…', 'Street evidence · raw units': '街道数据 · 原始单位', 'Original points / polygons': '原始点 / 面', 'Validated score · 0–100': '已验证分数 · 0–100',
 'Custom maximum (minutes)': '自定义上限（分钟）', 'Places near this walk have not been looked up yet.': '还没有查找这条路线附近的地点。', 'Generate or select a route to discover POIs.': '生成或选择一条路线以查看沿途地点。',
 // common dynamic labels
 'Planning your walk…': '正在规划你的步行…', 'Waking the route server…': '正在唤醒路线服务器…', 'Finding places & routing…': '正在查找地点并规划…', 'Details': '详情',
 'Locate me': '定位我', 'About the prototype': '关于本原型', 'Dismiss': '关闭', 'Clear': '清除', 'Describe your walk': '描述你的步行', 'Back to map': '回到地图', 'Quick preferences': '快捷偏好',
};
// What a walker sees after planning (City Walk, the left panel, weather, the data along the route). Added 2026-11-20
// after a live check in Chinese mode; technical details (route edges, route check, score formulas, indicator
// definitions) stay in English on purpose.
Object.assign(I18N_ZH, {
 // City Walk card
 'NOT FEASIBLE': '无法满足', 'no limit set': '未设上限', 'walking limit only': '只限制步行时间', 'How this plan was made': '这份行程是怎么排出来的', 'Find cappuccino': '找卡布奇诺',
 'Describe what you want to see, eat or do — or add stops — then Plan My Walk.': '描述你想看、想吃或想做的事，或者添加途经点，然后点"规划我的步行"。',
 'Hours listed but not machine-readable': '列有营业时间，但格式无法自动识别', 'Open at arrival per OSM hours': '按 OSM 营业时间，到达时在营业',
 'Opening hours (OSM) say closed at arrival time': '按 OSM 营业时间，到达时已关门', 'Closes during the planned visit (OSM hours)': '按 OSM 营业时间，停留期间会关门',
 'Verified facts': '已核实的事实', 'Derived metrics': '推算出的数据', 'Interpretation': '解读', 'Unknown': '未知',
 'Recommended: the requested item is confirmed and the detour is short.': '推荐：你要的东西已确认有，而且绕路很短。',
 'Possible match: please review the menu evidence.': '可能符合：请核对菜单依据。', 'Listed for reference only: it does not meet the request on current evidence.': '仅供参考：按现有依据不符合你的要求。',
 'Matches the requested kind of place.': '符合你要的地点类型。', 'rule-based (no language model)': '按规则判断（未用语言模型）',
 'Ratings and review counts: no rating provider is configured.': '评分和评论数：没有接入评分来源。', 'Ratings: not available.': '评分：暂无。',
 'Opening hours at arrival: not mapped or not machine-readable.': '到达时是否营业：没有记录，或格式无法识别。', 'Today’s stock and prices: a menu listing does not confirm them.': '今天有没有货、价格多少：菜单上列着并不代表确定。',
 'Confirmed menu match': '菜单上已确认有', 'Coffee shop': '咖啡店', 'A coffee shop by its OpenStreetMap listing; the menu was not read.': '地图资料标注为咖啡店，未读取菜单。', 'Probable match — review needed': '可能有，需要核对', 'Unverified': '未核实', 'Not found in checked sources': '查过的来源里没有',
 'Checking official menu…': '正在查官方菜单…', 'not checked': '未查', 'source': '来源', 'optional': '可选',
 'Wikidata-listed': 'Wikidata 收录', 'hours listed': '列有营业时间', 'OSM tag: serves espresso': 'OSM 标注：供应意式浓缩', 'OSM tag: serves coffee': 'OSM 标注：供应咖啡',
 // kinds of stops (journey.js labels and place categories)
 'Famous sight': '著名景点', 'Famous sights': '著名景点', 'Museums': '博物馆', 'Historic buildings': '历史建筑', 'Parks': '公园', 'Shopping': '购物',
 'Culture venue': '文化场所', 'Culture venues': '文化场所', 'Pharmacy': '药店', 'Grocery / supermarket': '杂货店 / 超市', 'Hospital / clinic': '医院 / 诊所',
 'ATM / bank': 'ATM / 银行', 'Public restroom': '公共厕所', 'Luggage storage': '行李寄存', 'Café': '咖啡馆', 'Restaurant': '餐厅', 'Bakery / dessert': '面包 / 甜点', 'Bar': '酒吧',
 'Coffee': '咖啡', 'Cappuccino': '卡布奇诺', 'Espresso': '意式浓缩', 'Latte': '拿铁', 'Tea': '茶', 'Matcha': '抹茶', 'Pizza': '披萨', 'Bagel': '贝果', 'Croissant': '可颂',
 'cafes': '咖啡馆', 'restaurants': '餐厅', 'bakeries': '面包甜点店', 'bars': '酒吧', 'museums': '博物馆', 'parks': '公园', 'historic': '历史建筑', 'famous': '著名景点',
 'culture': '文化场所', 'shopping': '购物', 'hotels': '酒店', 'Hotel': '酒店', 'Attraction': '景点', 'Gallery': '美术馆', 'Library': '图书馆', 'Monument': '纪念碑', 'Memorial': '纪念地',
 'Place of worship': '宗教场所', 'Theatre': '剧院', 'Viewpoint': '观景点', 'Garden': '花园', 'Bakery': '面包店', 'Fast food': '快餐',
 // left panel
 '✦ AI on · understood your last request': '✦ AI 已开启 · 已理解你上一个请求', '✦ AI on · describe your walk in your own words': '✦ AI 已开启 · 用你自己的话描述这次步行',
 '◇ AI off · your request is read with simple rules': '◇ AI 未开启 · 用简单规则理解你的请求', '◇ AI not reachable yet · it will try again when you plan': '◇ 暂时连不上 AI · 规划时会再试',
 'Planned stops are listed under “Your city walk” on the right.': '规划好的停留点列在右侧"你的城市漫步"里。',
 'READ BY AI': '由 AI 理解', 'READ WITH SIMPLE RULES': '用简单规则理解', 'NOT READ YET': '尚未理解', '✦ UNDERSTOOD YOUR PREFERENCES': '✦ 理解出的偏好',
 '✧ No preferences interpreted yet. Unmentioned dimensions = neutral 50.': '✧ 还没有理解出偏好。没提到的维度 = 中性 50。',
 'High': '高', 'Moderate': '中等', 'Low': '低', 'less': '更少', 'prefer less': '偏好更少', 'stairs allowed': '可以走楼梯', 'avoiding stairs': '避开楼梯', 'step-free': '无台阶',
 // results, map and status lines
 'Each button plans the walk again with that change. We only say it improved when the data shows it.': '每个按钮都会按这个改动重新规划。只有数据显示确实变好了，我们才会这么说。',
 'DATA ↗': '数据 ↗', '● Walking routes: Manhattan · Brooklyn · Queens': '● 步行路线：曼哈顿 · 布鲁克林 · 皇后区',
 'STREETS LOADED · MANHATTAN · BROOKLYN · QUEENS': '街道已加载 · 曼哈顿 · 布鲁克林 · 皇后区', 'How walkers rated their walks': '步行者给路线的评分', 'Install': '安装',
 'Selected': '已选', 'Did a street feel different from its score?': '有哪条街感觉和它的分数不一样吗？', 'Street': '街道', 'Worse than rated': '比分数差',
 'Better than rated': '比分数好', 'What these scores measure': '这些分数衡量什么', 'Explore on map ↗': '在地图上查看 ↗',
 'Trees': '行道树', 'Historic landmarks': '历史地标', 'Restaurants & cafés': '餐厅与咖啡馆', 'Transit stops': '公交站点', 'subway entrances + bus stops': '地铁入口 + 公交站',
 'Pedestrian crashes': '行人交通事故', 'Plan a route to see the city data around it.': '规划路线后，可以看到周边的城市数据。',
 // weather
 'Now': '现在', 'Humidity': '湿度', 'Wind': '风', 'Clear': '晴', 'Cloudy': '多云', 'Fog': '雾', 'Rain': '雨', 'Snow': '雪', 'Showers': '阵雨', 'Storm': '雷暴', 'Variable': '多变',
 'after dark': '天黑后', 'rain': '雨', 'wind': '风', 'alert': '警报', 'Forecast window unavailable': '暂无这段时间的预报',
 'No active NWS alerts for this point': '此处没有生效的天气警报（NWS）', 'NWS alerts unavailable': '暂时无法获取天气警报（NWS）',
 'These routes were computed without weather data.': '这些路线在规划时没有用到天气数据。', 'These routes were computed without usable weather data.': '这些路线在规划时没有可用的天气数据。',
 'Weather-aware routing is off.': '考虑天气的路线规划已关闭。', 'Weather will be checked when you plan a route.': '规划路线时会查看天气。',
 'Open-Meteo forecast (grid model, one value for the whole walk) · NWS alerts. Never a street-level measurement.': 'Open-Meteo 天气预报（网格模型，整段步行用同一个值）· NWS 天气警报。不是街道级的测量。',
 'Open-Meteo model (not a station observation)': 'Open-Meteo 模型（不是气象站实测）', 'INFO ONLY': '仅供参考', 'ROUTING ACTIVE': '已用于规划', 'UNAVAILABLE': '不可用',
 'Weather conditions': '天气状况', 'Rain chance · wind': '降雨概率 · 风', 'Weather impact on your walk': '天气对步行的影响',
 'No weather condition expected to affect walking comfort.': '预计没有会影响步行舒适度的天气。', 'Unknown — no forecast.': '未知：没有预报。',
 'Weather-aware route explanation': '天气与路线', 'Plan a route to see whether weather changed it.': '规划路线后，可以看到天气有没有改变它。',
 'Weather information is available, but weather-based route optimization is not active for this route.': '有天气信息，但这条路线没有按天气优化。',
 'Recalculate': '重新计算', 'Weather has not loaded.': '天气还没有加载。', 'Routes use the static experience scores.': '路线使用固定的体验分数。',
 // status lines
 'Clarification needed. The displayed previous route has not been recalculated.': '需要你补充一点信息。当前显示的路线没有重新计算。',
 'Journey changed. Plan again to update route geometry.': '行程改了。再规划一次就能更新路线。', 'No selected route yet.': '还没有选中的路线。',
 'No discovery request yet. Describe what you want, or add stops.': '还没有想去的地方。描述你想要什么，或者添加途经点。',
 'Step-free access cannot be verified with the current curb-ramp and elevator data. No route is recommended.': '现有的路缘坡道和电梯数据无法核实无台阶通行，因此不推荐路线。',
 'Step-free access needs verified curb-ramp and elevator data, which is not connected. No route recommendation will be returned.': '无台阶通行需要经过核实的路缘坡道和电梯数据，目前尚未接入，因此不会推荐路线。',
 'Step-free access cannot be verified, so no route is recommended.': '无法核实无台阶通行，因此不推荐路线。',
 'The route server has just woken up and is still warming up. Trying once more…': '路线服务器刚被唤醒，还在预热，正在自动再试一次…',
 'Waking the route server. The first request after a pause can take up to a minute…': '正在唤醒路线服务器，闲置后的第一次请求最多要等一分钟…',
 'The route server is not answering right now. Nothing was changed. Try again in a minute.': '路线服务器暂时没有响应，什么都没有改动。请一分钟后再试。',
 'The server took too long to answer. Please try again in a moment.': '服务器响应太慢，请稍后再试。',
 'The route server is not answering right now. Please try again in a moment.': '路线服务器暂时没有响应，请稍后再试。',
 'Something went wrong. Please try again in a moment.': '出了点问题，请稍后再试。',
 'Install STROLLANE on your home screen for a faster, full-screen view.': '把 STROLLANE 安装到手机主屏幕，像 App 一样打开。', 'Waterfront': '滨水',
 'Cafes': '咖啡馆', 'Restaurants': '餐厅', 'Bakeries': '面包甜点店', 'Bars': '酒吧',
});
for (const k of ['Clear', 'Cloudy', 'Fog', 'Rain', 'Snow', 'Showers', 'Storm', 'Variable']) I18N_ZH[k.toLowerCase()] = I18N_ZH[k];

/* Phrases with a number or a name in them. Each rule must match the WHOLE text (or the whole of one " · " part):
   anything else, such as a sentence built from data, stays as it is. A function returning null means "no match". */
const i18nTerm = (s) => I18N_ZH[i18nKey(String(s))] || String(s);
const i18nTermOnly = (s) => I18N_ZH[i18nKey(String(s))] || null;
const I18N_ZH_PATTERNS = [
 [/^Checking menus for (.+)…$/, (_, a) => `正在核对菜单上有没有${typeof i18nLabel === 'function' ? i18nLabel(a) : a}…`], [/^Checking menus…$/, '正在核对菜单…'],
 [/^(-?[\d.,]+) km$/, '$1 公里'], [/^(-?[\d.,]+) mi$/, '$1 英里'],
 // walker ratings and comments (feedback-ui.js)
 [/^(\d+) rated walks? · matched the request ([\d.]+|—) \/ 5$/, '$1 次评分 · 与要求相符 $2 / 5'], [/^(\d+) more comments?$/, '还有 $1 条评论'],
 [/^(Tourist|Curious Local|Leisure Walker|Your own priorities) walks \((\d+)\): ★ ([\d.]+|—)$/, (_, t, n, v) => `${{'Tourist': '游客', 'Curious Local': '好奇的本地人', 'Leisure Walker': '休闲散步者', 'Your own priorities': '自选偏好'}[t]}路线（${n}）：★ ${v}`],
 // navigation card
 [/^Then: (.+)$/, (_, a) => `然后：${a}`], [/^Next stop: (.+?)(?: · \+(\d+))?$/, (_, a, n) => `下一站：${i18nPlaceName(a) || a}${n ? ` · 另有 ${n} 站` : ''}`],
 [/^Next: (.+) · ([\d.,]+) (m|km|ft|mi)$/, (_, a, d, u) => `下一个：${i18nPlaceName(a) || a} · ${d} ${{m: '米', km: '公里', ft: '英尺', mi: '英里'}[u]}`],
 [/^Suggested visit (\d+) min \(estimate\)$/, '建议停留 $1 分钟（估计）'], [/^You are (.+) from the start of this route\.$/, (_, d) => `你离这条路线的起点还有 ${i18nPhrase(d) || d}。`],
 [/^Could not recalculate \((.+)\)\. Your last route is still shown\.$/, '无法重新规划（$1）。仍显示原来的路线。'], [/^(\d+) min$/, '$1 分钟'], [/^(\d+) min stay \(est\.\)$/, '停留约 $1 分钟（估计）'],
 [/^limit (\d+)$/, '上限 $1 分钟'], [/^(\d+) PLANNED$/, '已规划 $1 个'], [/^(\d+) STOPS?$/, '$1 个途经点'], [/^(\d+) WALKS?$/, '$1 条路线'],
 [/^(\d+) NEAR ROUTE$/, '沿途 $1 个'], [/^(\d+)\/12 MEASURED$/, '已测量 $1/12'], [/^(\d+) EDGES$/, '$1 条路段'], [/^Up to (\d+) min$/, '最长 $1 分钟'],
 [/^([A-Z][\w &/'’-]{0,40}) \+(\d+)$/, (m, a, n) => (i18nTermOnly(a) ? `${i18nTermOnly(a)} +${n}` : null)],
 [/^Wikipedia in (\d+) editions?$/, '维基百科 $1 种语言版本'], [/^entrance approx\. (\d+) m from mapped point$/, '入口距标注点约 $1 米'],
 [/^cuisine: (.+)$/, '菜系：$1'], [/^Arrive ~(.+)$/, '约 $1 到达'],
 [/^feels (-?[\d.]+) ?°(C?)$/, '体感 $1 °$2'], [/^Feels (-?[\d.]+) ?°C$/, '体感 $1 °C'], [/^feels up to (-?[\d.]+) ?°C$/, '体感最高 $1 °C'],
 [/^rain (\d+) ?%$/, '降雨概率 $1%'], [/^wind up to ([\d.]+) km\/h$/, '风速最高 $1 km/h'], [/^([\d.]+) km\/h wind$/, '风速 $1 km/h'],
 [/^Next (\d+) min$/, '未来 $1 分钟'], [/^During the walk \((\d+) min from now\)$/, '步行期间（$1 分钟后起）'], [/^(\d+) min ago$/, '$1 分钟前'],
 [/^valid (.+) \(New York\)$/, '有效时间 $1（纽约）'], [/^until (\w{3},? \d{1,2}:\d\d ?[AP]M)$/, '至 $1'],
 [/^weight (\d+)$/, '权重 $1'], [/^Your priority (\d+)$/, '你的优先级 $1'], [/^(\d+)% coverage$/, '覆盖率 $1%'], [/^this route (\d+)$/, '本路线 $1'],
 [/^([\d.]+) → fit ([\d.]+)$/, '$1 → 匹配 $2'], [/^Based on: (.+)$/, '依据：$1'],
 [/^([A-Z][\w &]+) (\d+(?:\.\d+)?)$/, (m, a, n) => (I18N_DIMENSIONS_ZH[a] ? `${I18N_ZH[a]} ${n}` : null)], [/^(\d+) datasets?$/, '$1 个数据集'], [/^ACTIVE DATASETS: (\d+) of (\d+)$/, '已启用的数据集：$1 / $2'],
 [/^WITHIN (\d+) M$/, '$1 米以内'], [/^(\d+) · Crashes (\S+) to (\S+) \((\d+) years?\)$/, '$1 · 事故 $2 至 $3（$4 年）'],
 [/^Real records within (\d+) m of the route's geometry \(map display corridor, not a scoring distance\)\.$/, '路线 $1 米以内的真实记录（仅用于地图显示，不参与评分）。'],
 [/^(\d\d) (.+)$/, (m, n, a) => (i18nTermOnly(a) ? `${n} ${i18nTermOnly(a)}` : null)],
 [/^for “(.+)”$/, (m, a) => `用于“${i18nTerm(a)}”`],
 [/^([^A-Za-z0-9\s]{1,2}) ([A-Z].*)$/, (m, icon, a) => (i18nTermOnly(a) ? `${icon} ${i18nTermOnly(a)}` : null)],
 [/^([A-Z][\w'’-]*(?: [A-Z][\w'’-]*){0,2}) \((café|restaurant|bakerie|bar)\)$/, (m, a, k) => `${i18nTerm(a)}（${{café: '咖啡馆', restaurant: '餐厅', bakerie: '面包甜点店', bar: '酒吧'}[k]}）`],
 [/^([A-Z][\w'’-]*(?: [A-Z][\w'’-]*)?) restaurant$/, (m, a) => `${i18nTerm(a)} 餐厅`],
 [/^(.+) \(rule-based \(no language model\)\)$/, (m, a) => `${a}（按规则判断，未用语言模型）`], [/^\(rule-based \(no language model\)\)$/, '（按规则判断，未用语言模型）'],
 [/^(\d+) stop\(s\), ([\d.]+) km on the OSM pedestrian graph, (\d+) min walking \+ (\d+) min visits\. Within your limits\.$/, '$1 个停留点，步行网络上 $2 公里，步行 $3 分钟 + 停留 $4 分钟。在你的限制范围内。'],
 [/^(\d+) stop\(s\), ([\d.]+) km on the OSM pedestrian graph, (\d+) min walking \+ (\d+) min visits\. Not feasible: (.+)$/, '$1 个停留点，步行网络上 $2 公里，步行 $3 分钟 + 停留 $4 分钟。无法满足：$5'],
 [/^Whether it serves (.+?): (.+)$/, '是否供应 $1：$2'], [/^rank (\d+)$/, '第 $1 名'],
 [/^shortest route$/, '最短路线'], [/^this is the shortest route$/, '这就是最短路线'], [/^([\d.]+)% longer$/, '长 $1%'],
 [/^shortest route ([\d.]+|N\/A)(?: \(([+-]?\d+)(, similar)?\))?$/, (m, v, d, sim) => `最短路线 ${v}${d ? `（${d}${sim ? '，相近' : ''}）` : ''}`],
 // the facts under a recommended café or restaurant (routing/recommend.py)
 [/^“(.+)” is on the official menu \((\S+)\); checked (\S+)\.$/, '官方菜单上有“$1”（$2）；查询时间 $3。'],
 [/^NYC Health inspection grade (\w+) \((\S+)\); last inspected (\S+)\.$/, '纽约市卫生检查等级 $1（$2）；最近一次检查 $3。'],
 [/^Official website: (\S+?)\.?$/, '官网：$1'], [/^Adds (\d+) m \/ (\d+) min of walking on the pedestrian network\.$/, '在步行网络上多走 $1 米 / $2 分钟。'],
 [/^Open at the estimated arrival (\S+) according to its mapped hours\.$/, '按记录的营业时间，预计 $1 到达时在营业。'],
];
/** Chinese for one phrase: the dictionary first, then the rules above. null when nothing applies. */
function i18nPhrase(text) {
 const key = i18nKey(String(text || ''));
 if (!key) return null;
 if (I18N_ZH[key]) return I18N_ZH[key];
 if (!/[A-Za-z]/.test(key)) return null;
 for (const [re, to] of I18N_ZH_PATTERNS) {
  const m = key.match(re); if (!m) continue;
  const out = typeof to === 'function' ? to(...m) : key.replace(re, to);
  if (out != null && out !== key) return out;
 }
 return i18nPlaceName(key);
}
/* Chinese names of places (data/places/names-zh.json: Wikidata labels, checked by scripts/curate_place_names_zh.py),
   loaded the first time the interface is in Chinese. A text that is exactly a place's name is shown as
   "熨斗大厦 Flatiron Building": the English name, which is what the street signs and the map say, stays beside it. */
const I18N_PLACES = {names: null, loading: null, url: './data/places/names-zh.json'};
function i18nPlaceName(key) {
 const n = I18N_PLACES.names;
 return n && Object.prototype.hasOwnProperty.call(n, key) ? `${n[key]} ${key}` : null;
}
function i18nLoadPlaces() {
 if (I18N_PLACES.names || I18N_PLACES.loading || typeof fetch !== 'function') return I18N_PLACES.loading;
 I18N_PLACES.loading = fetch(I18N_PLACES.url).then((r) => (r.ok ? r.json() : null)).then((d) => {
  I18N_PLACES.names = (d && d.names) || {};
  if (i18n.lang === 'zh' && typeof document !== 'undefined') { i18n.busy = true; try { i18nApply(document.body); } finally { i18n.busy = false; } }
 }).catch(() => { I18N_PLACES.names = {}; }); // no Chinese names: places keep their English names, as before
 return I18N_PLACES.loading;
}
/** Chinese for a text node's whole text: one phrase, or " · "-separated parts of which at least one is known (the
    others, usually names and addresses, are kept as they are). */
function i18nLookup(text) {
 const one = i18nPhrase(text);
 if (one) return one;
 const key = i18nKey(String(text || ''));
 // a text node that continues a line: " · shortest route 97" after a bold "Architecture 99"
 const lead = /^· (.+)$/.exec(key);
 if (lead) { const rest = i18nLookup(lead[1]); return rest ? `· ${rest}` : null; }
 if (!key.includes(' · ')) return null;
 let hit = false;
 const out = key.split(' · ').map((p) => { const z = i18nPhrase(p); if (z) { hit = true; return z; } return p; });
 return hit ? out.join(' · ') : null;
}
/** A label in the interface language (used by code that writes Chinese sentences around a data label). */
function i18nLabel(s) { return typeof i18n !== 'undefined' && i18n.lang === 'zh' ? (i18nPhrase(s) || s) : s; }
for (const [en, zh] of Object.entries(I18N_DIMENSIONS_ZH)) I18N_ZH[en] = `${zh} ${en}`; // gloss + the unchanged name

const I18N_ATTRS = ['placeholder', 'title', 'aria-label'];
const I18N_SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'CODE', 'PRE']);
const i18n = {lang: 'en', observer: null, busy: false};
const I18N_COVERAGE_NOTE = '界面已切换为中文。常见地名附中文名（来自 Wikidata），其他地名和技术细节（路段列表、评分公式、数据说明）保留英文；12 个维度保留英文原名并附中文注释。可以用中文描述偏好；起点和终点请在输入框里选择。';

const i18nKey = (s) => s.replace(/\s+/g, ' ').trim();
function i18nText(node) {
 if (node.parentNode && I18N_SKIP.has(node.parentNode.nodeName)) return;
 if (i18n.lang === 'zh') {
  if (node.__zh !== undefined && node.nodeValue === node.__zh) return; // already shown in Chinese
  const zh = i18nLookup(node.nodeValue);
  if (!zh) { node.__en = undefined; node.__zh = undefined; return; }
  node.__en = node.nodeValue; node.__zh = node.nodeValue.replace(node.nodeValue.trim(), zh); node.nodeValue = node.__zh;
 } else if (node.__en !== undefined) {
  if (node.nodeValue === node.__zh) node.nodeValue = node.__en; // untouched since translation: restore the original exactly
  node.__en = undefined; node.__zh = undefined;
 }
}
function i18nAttrs(el) {
 for (const a of I18N_ATTRS) {
  if (!el.hasAttribute || !el.hasAttribute(a)) continue;
  const store = 'data-i18n-en-' + a, shown = el.getAttribute(a);
  if (i18n.lang === 'zh') {
   const zh = i18nLookup(shown);
   if (zh && zh !== shown) { el.setAttribute(store, shown); el.setAttribute(a, zh); }
  } else if (el.hasAttribute(store)) {
   if (i18nLookup(el.getAttribute(store)) === shown) el.setAttribute(a, el.getAttribute(store));
   el.removeAttribute(store);
  }
 }
}
function i18nApply(root) {
 if (!root) return;
 if (root.nodeType === 3) return i18nText(root);
 if (root.nodeType !== 1 || I18N_SKIP.has(root.nodeName)) return;
 i18nAttrs(root);
 const walker = document.createTreeWalker(root, 5 /* SHOW_ELEMENT | SHOW_TEXT */);
 for (let n = walker.nextNode(); n; n = walker.nextNode()) { if (n.nodeType === 3) i18nText(n); else i18nAttrs(n); }
}

function setLanguage(lang, remember = true) {
 if (lang !== 'zh' && lang !== 'en') return i18n.lang;
 i18n.lang = lang;
 document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : 'en';
 i18n.busy = true; try { i18nApply(document.body); } finally { i18n.busy = false; }
 if (lang === 'zh') i18nLoadPlaces();
 if (typeof navFollowLanguage === 'function') navFollowLanguage(lang); // turn instructions and voice in the same language
 if (lang === 'zh' && !i18n.observer && typeof MutationObserver !== 'undefined') {
  i18n.observer = new MutationObserver((records) => {
   if (i18n.lang !== 'zh' || i18n.busy) return;
   i18n.busy = true;
   try {
    for (const r of records) {
     if (r.type === 'characterData') i18nText(r.target);
     else if (r.type === 'attributes') i18nAttrs(r.target);
     else r.addedNodes.forEach(i18nApply);
    }
   } finally { i18n.busy = false; }
  });
  i18n.observer.observe(document.body, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: I18N_ATTRS});
 }
 for (const b of document.querySelectorAll('[data-lang-toggle]')) {
  const label = b.querySelector('[data-lang-label]') || b;
  label.textContent = lang === 'zh' ? 'EN' : '中文';
  b.setAttribute('aria-label', lang === 'zh' ? 'Switch the interface to English' : '切换为中文界面');
  b.setAttribute('aria-pressed', String(lang === 'zh'));
 }
 if (remember) { try { localStorage.setItem('strollane.lang', lang); } catch (e) { /* private mode: the choice lasts for this visit */ } }
 // sentences built from data (walk descriptions, City Walk stops, map photo captions) are composed in the chosen
 // language, so draw them again
 try {
  if (typeof state !== 'undefined' && state.routes?.length && typeof renderRouteCards === 'function') { renderRouteCards(); if (typeof updateWhyRoute === 'function') updateWhyRoute(); }
  if (typeof journey !== 'undefined' && journey.plan && typeof renderCityWalk === 'function') renderCityWalk();
 } catch (e) { console.warn('[i18n] redraw', e); }
 return lang;
}
function toggleLanguage() {
 const next = setLanguage(i18n.lang === 'zh' ? 'en' : 'zh');
 if (next === 'zh' && typeof toast === 'function') toast(I18N_COVERAGE_NOTE);
 return next;
}
function setupI18n() {
 for (const b of document.querySelectorAll('[data-lang-toggle]')) b.addEventListener('click', toggleLanguage);
 let saved = null; try { saved = localStorage.getItem('strollane.lang'); } catch (e) { /* no storage: start in English */ }
 if (saved === 'zh') setLanguage('zh', false);
}
if (typeof window !== 'undefined') {
 Object.assign(window, {setLanguage, toggleLanguage, I18N_ZH, I18N_DIMENSIONS_ZH, I18N_PLACES, i18nLookup, i18nPhrase, i18nLabel, i18nLoadPlaces});
 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setupI18n); else setupI18n();
}
