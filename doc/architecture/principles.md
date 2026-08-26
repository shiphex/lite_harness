# lite_harness Architecture Principles

1. AgentRunner 只负责编排，不实现具体策略。
2. 所有外部副作用必须经过 ToolExecutor。
3. 核心模块只依赖内部数据类型和 Protocol。
4. 配置在程序启动时构造，运行期间默认不可变。
5. 每次状态转换都必须可以被观察和测试。
6. Context 必须有显式预算，任何注入内容都有成本。
7. 安全底线不能被项目配置或 Hook 放宽。
8. 高级组件必须可以禁用，失败时应尽可能降级。
9. Subagent 使用同一个 Runner，但拥有独立 State 和 RunPolicy。
10. 文件修改优先可逆，工具结果应描述产生的副作用。
11. Agent Teams 只新增协作平面；lead、subagent 和 teammate 必须复用同一执行内核。
